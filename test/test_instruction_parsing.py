import unittest
import importlib.resources as pkg_resources

from test import config_files

from bespokeasm.assembler.label_scope import GlobalLabelScope, LabelScope, LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConsitionStack


class TestInstructionParsing(unittest.TestCase):
    label_values = None

    @classmethod
    def setUpClass(cls):
        global_scope = GlobalLabelScope(set())
        global_scope.set_label_value('var1', 12, 1)
        global_scope.set_label_value('my_val', 8, 2)
        global_scope.set_label_value('the_two', 2, 3)
        local_scope = LabelScope(LabelScopeType.LOCAL, global_scope, 'TestInstructionParsing')
        local_scope.set_label_value('.local_var', 10, 3)
        local_scope.set_label_value('.loop', 0x8020, 3)
        cls.label_values = local_scope

    def setUp(self):
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None

    def test_instruction_variant_matching(self):
        with pkg_resources.path(config_files, 'test_instructions_with_variants.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        # start simple
        ins1 = InstructionLine.factory(
            22,
            '  nop',
            'some comment!',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 1, 'has 1 byte')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_bytes()
        self.assertEqual(ins1.get_bytes(), bytearray([0x00]), 'instruction should match')

        # match default variant operand sets
        ins2 = InstructionLine.factory(
            22,
            '  mov a, [sp+2]',
            'some comment!',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 2, 'has 2 byte')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(ins2.get_bytes(), bytearray([0x44, 0x02]), 'instruction should match')

        # match default variant specific operand
        ins3 = InstructionLine.factory(
            22,
            '  mov a, [hl+6]',
            'some comment!',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 2, 'has 2 byte')
        ins3.label_scope = TestInstructionParsing.label_values
        ins3.generate_bytes()
        self.assertEqual(ins3.get_bytes(), bytearray([0x45, 0x06]), 'instruction should match')

        # match first variant
        ins4 = InstructionLine.factory(
            22,
            '  mov a, h',
            'some comment!',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.byte_size, 1, 'has 1 byte')
        ins4.label_scope = TestInstructionParsing.label_values
        ins4.generate_bytes()
        self.assertEqual(ins4.get_bytes(), bytearray([0x81]), 'instruction should match')

        # match second variant
        ins5 = InstructionLine.factory(
            22,
            '  mov h, $88',
            'some comment!',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.byte_size, 2, 'has 2 byte')
        ins5.label_scope = TestInstructionParsing.label_values
        ins5.generate_bytes()
        self.assertEqual(ins5.get_bytes(), bytearray([0x9F, 0x88]), 'instruction should match')

        # match no variant
        with self.assertRaises(SystemExit, msg='no instruction variant should match here'):
            InstructionLine.factory(
                22,
                '  mov h, l',
                'some comment!',
                isa_model,
                memzone_mngr.global_zone,
                memzone_mngr,
            )

        with self.assertRaises(SystemExit, msg='no instruction variant should match here'):
            InstructionLine.factory(
                22,
                '  mov 27',
                'some comment!',
                isa_model,
                memzone_mngr.global_zone,
                memzone_mngr,
            )

    def test_operand_decorators(self):
        with pkg_resources.path(config_files, 'test_indirect_indexed_register_operands.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        ins0 = InstructionLine.factory(
            22, 'mov a, +i', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.byte_size, 2, 'has 2 bytes')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_bytes()
        self.assertEqual(list(ins0.get_bytes()), [0xFF, 0x42], 'instruction byte should match')

        ins1 = InstructionLine.factory(
            22, 'mov [hl+7]+,i', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 3, 'has 3 bytes')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_bytes()
        self.assertEqual(list(ins1.get_bytes()), [0xFF, 0x81, 0x07], 'instruction byte should match')

        ins2 = InstructionLine.factory(
            22, 'mov [sp+$1D],[mar+a]++', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 3, 'has 3 bytes')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(list(ins2.get_bytes()), [0xFF, 0x64, 0x1D], 'instruction byte should match')

    def test_indexed_regsiter_operands(self):
        with pkg_resources.path(config_files, 'test_indirect_indexed_register_operands.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        ins0 = InstructionLine.factory(
            22, 'jmp hl+j', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.byte_size, 1, 'has 1 bytes')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_bytes()
        self.assertEqual(list(ins0.get_bytes()), [0xC2], 'instruction byte should match')

        ins1 = InstructionLine.factory(
            22, 'jmp hl+[sp+7]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 2, 'has 2 bytes')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_bytes()
        self.assertEqual(list(ins1.get_bytes()), [0xC3, 0x07], 'instruction byte should match')

    def test_indirect_indexed_regsiter_operands(self):
        with pkg_resources.path(config_files, 'test_indirect_indexed_register_operands.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        ins0 = InstructionLine.factory(
            22, 'mov a, [hl+i]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.byte_size, 1, 'has 1 bytes')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_bytes()
        self.assertEqual(list(ins0.get_bytes()), [0x81], 'instruction byte should match')

        ins1 = InstructionLine.factory(
            22, 'mov [$2000], [hl+i]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 3, 'has 3 bytes')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_bytes()
        self.assertEqual(list(ins1.get_bytes()), [0xB1, 0x00, 0x20], 'instruction byte should match')

        ins2 = InstructionLine.factory(
            22, 'mov [$2000], [hl+[sp+2]]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 4, 'has 4 bytes')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(list(ins2.get_bytes()), [0xB3, 0x00, 0x20, 0x02], 'instruction byte should match')

        ins2 = InstructionLine.factory(
            22, 'mov [mar + $44], [$8020]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 4, 'has 4 bytes')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(list(ins2.get_bytes()), [0xFE, 0x20, 0x80, 0x44], 'instruction byte should match, operands reversed')

        ins4 = InstructionLine.factory(
            22, 'cmp [hl+i],0', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
#        self.assertEqual(ins4.byte_size, 3, 'has 3 bytes')
        ins4.label_scope = TestInstructionParsing.label_values
        ins4.generate_bytes()
        self.assertEqual(list(ins4.get_bytes()), [0xFF, 0x8F, 0], 'instruction byte should match')

        with self.assertRaises(SystemExit, msg='no instruction  should match here'):
            bad1 = InstructionLine.factory(
                22, '  mov a, [sp+i]', 'some comment!',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            bad1.set_start_address(666)
            bad1.label_scope = TestInstructionParsing.label_values
            bad1.generate_bytes()

    def test_label_parsing(self):
        with pkg_resources.path(config_files, 'test_instructions_with_variants.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(42, 'test_label_parsing')
        preprocessor = Preprocessor()

        l1: LineObject = LineOjectFactory.parse_line(
            lineid,
            "LABEL = %00001111",
            isa_model,
            TestInstructionParsing.label_values,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConsitionStack(),
            0,
        )[0]
        self.assertIsInstance(l1, LabelLine)
        self.assertTrue(l1.is_constant, )
        self.assertEqual(l1.get_value(), 0x0F, 'value should be right')

        l2: LineObject = LineOjectFactory.parse_line(
            lineid,
            ".local_label:",
            isa_model,
            TestInstructionParsing.label_values,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConsitionStack(),
            0,
        )[0]
        l2.set_start_address(42)
        l2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(l2, LabelLine)
        self.assertFalse(l2.is_constant, )
        self.assertEqual(l2.get_value(), 42, 'value should be right')

        l3: LineObject = LineOjectFactory.parse_line(
            lineid,
            "old_style EQU 42H",
            isa_model,
            TestInstructionParsing.label_values,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConsitionStack(),
            0,
        )[0]
        l3.set_start_address(42)
        l3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(l3, LabelLine)
        self.assertTrue(l3.is_constant, "label should be a constant")
        self.assertEqual(l3.get_value(), 0x42, 'value should be right')

    def test_operand_bytecode_ordering(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(13, 'test_operand_bytecode_ordering')

        t1 = InstructionLine.factory(
            lineid, '  ld a, $F0', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b00010011, 0xF0], 'instruction byte should match')

        t2 = InstructionLine.factory(
            lineid, '  ld [$20], x', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 2, 'has 2 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b10011100, 0x20], 'instruction byte should match')

    def test_deferred_operands(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(13, 'test_deferred_operands')

        t1 = InstructionLine.factory(
            lineid, '  ld a, [[$F0]]', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b00010101, 0xF0], 'instruction byte should match')

        t2 = InstructionLine.factory(
            lineid, '  ld [[my_val]],x', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 2, 'has 2 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b10011101, 0x08], 'instruction byte should match')

    def test_instruction_bytecode_suffixes(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(13, 'test_instruction_bytecode_suffixes')

        t1 = InstructionLine.factory(
            lineid, '  foo [[$F0]]', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b11010101, 0xF0], 'instruction byte should match')

    def test_enumeration_operand(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(21, 'test_enumeration_operand')

        t1 = InstructionLine.factory(
            lineid, '  tst bee', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b00111001, 0xBB], 'instruction byte should match')

    def test_numeric_bytecode_operand(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(33, 'test_numeric_bytecode_operand')

        t1 = InstructionLine.factory(
            lineid, '  tstb x, the_two+1', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 1, 'has 1 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b10011011], 'instruction byte should match')

        t2 = InstructionLine.factory(
            lineid, '  tstb a, 7', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 1, 'has 1 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b00011111], 'instruction byte should match')

        t3 = InstructionLine.factory(
            lineid, '  enumarg 6', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(1)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.byte_size, 2, 'has 2 bytes')
        t3.generate_bytes()
        self.assertEqual(list(t3.get_bytes()), [254, 64], 'instruction byte should match')

        with self.assertRaises(SystemExit, msg='test bounds'):
            e1 = InstructionLine.factory(
                lineid, '  tstb b, 14', 'second argument is too large',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e1.label_scope = TestInstructionParsing.label_values
            e1.generate_bytes()

        with self.assertRaises(SystemExit, msg='test invalid enumerations'):
            e2 = InstructionLine.factory(
                lineid, '  enumarg 12', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e2.label_scope = TestInstructionParsing.label_values
            e2.generate_bytes()

    def test_numeric_enumeration_operand(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(33, 'test_numeric_enumeration_operand')

        t1 = InstructionLine.factory(
            lineid, 'num my_val+7', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 1, 'has 1 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b10101000], 'instruction byte should match')

        t2 = InstructionLine.factory(
            lineid, 'sftl a, 1', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 1, 'has 1 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b10001001], 'instruction byte should match')

        with self.assertRaises(SystemExit, msg='test invalid enumeration values'):
            e1 = InstructionLine.factory(
                lineid, 'num 7', 'number 7 is not allowed',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e1.label_scope = TestInstructionParsing.label_values
            e1.generate_bytes()

    def test_expressions_in_operations(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(42, 'test_expressions_in_operations')

        t1 = InstructionLine.factory(
            lineid, 'add .local_var+7', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b11010101, 17], 'instruction byte should match')

        # no addressing punction for numeric expression operands
        with self.assertRaises(SystemExit, msg='there should be no addressing punctuation in numeric expression operands'):
            InstructionLine.factory(
                lineid, 'add [.local_var+7]', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
        with self.assertRaises(SystemExit, msg='there should be no addressing punctuation in numeric expression operands'):
            InstructionLine.factory(
                lineid, 'add {.local_var+7}', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )

    def test_case_insentive_instructions(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(42, 'test_case_insentive_instructions')

        t1 = InstructionLine.factory(
            lineid, 'ADD .local_var+7', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b11010101, 17], 'instruction byte should match')

    def test_operand_order(self):
        with pkg_resources.path(config_files, 'test_instruction_operands.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(42, 'test_operand_order')

        t1 = InstructionLine.factory(
            lineid, 'ld a,b,c', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 3, 'has 3 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0x80, 0x12, 0x30], 'instruction byte should match')

        t2 = InstructionLine.factory(
            lineid, 'ed aa,bb,cc', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 3, 'has 3 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0x88, 0x32, 0x10], 'instruction byte should match')

        t3 = InstructionLine.factory(
            lineid, 'mv a,b,c', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(1)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.byte_size, 3, 'has 3 bytes')
        t3.generate_bytes()
        self.assertEqual(list(t3.get_bytes()), [0x81, 0x32, 0x10], 'instruction byte should match')

    def test_relative_address_operand(self):
        with pkg_resources.path(config_files, 'test_instruction_operands.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        lineid = LineIdentifier(66, 'test_relative_address_operand')

        t1 = InstructionLine.factory(
            lineid, 'jmp .loop', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(0x8000)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 3, 'has 3 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0xE5, 0x20, 0x80], 'instruction byte should match')

        t2 = InstructionLine.factory(
            lineid, 'jmp {.loop}', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(0x8000)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 2, 'has 2 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0xE6, 0x20], 'instruction byte should match')

        t3 = InstructionLine.factory(
            lineid, 'jmpr .loop', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(0x8000)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.byte_size, 2, 'has 2 bytes')
        t3.generate_bytes()
        self.assertEqual(list(t3.get_bytes()), [0xEE, 0x20], 'instruction byte should match')

        t4 = InstructionLine.factory(
            lineid, 'jmpre .loop', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t4.set_start_address(0x8000)
        t4.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t4, InstructionLine)
        self.assertEqual(t4.byte_size, 2, 'has 2 bytes')
        t4.generate_bytes()
        self.assertEqual(list(t4.get_bytes()), [0xEF, 0x1F], 'instruction byte should match')

        # test offsets that are too large or too small
        with self.assertRaises(SystemExit, msg='offset out of range'):
            bt1 = InstructionLine.factory(
                lineid, 'jmp {.loop}', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            bt1.set_start_address(0x7000)
            bt1.label_scope = TestInstructionParsing.label_values
            bt1.generate_bytes()

        with self.assertRaises(SystemExit, msg='offset out of range'):
            bt2 = InstructionLine.factory(
                lineid, 'jmp {.loop}', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            bt2.set_start_address(0x9000)
            bt2.label_scope = TestInstructionParsing.label_values
            bt2.generate_bytes()

    def test_valid_address_operand_enforcement(self):
        with pkg_resources.path(config_files, 'test_valid_address_enforcement.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )
        lineid = LineIdentifier(37, 'test_valid_address_operand_enforcement')

        t1 = InstructionLine.factory(
            lineid, 'jmpr $2FF8', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(0x3000)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0xEE, 0xF8], 'instruction byte should match')

        with self.assertRaises(SystemExit, msg='address out of range'):
            # the GLOBAL memory zone starts at $2000. Relative jumping before it should fail.
            t1 = InstructionLine.factory(
                lineid, 'jmpr $1FF8', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            t1.set_start_address(memzone_mngr.global_zone.start)
            t1.label_scope = TestInstructionParsing.label_values
            self.assertIsInstance(t1, InstructionLine)
            self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
            t1.generate_bytes()

        with self.assertRaises(SystemExit, msg='address out of range'):
            # the GLOBAL memory zone starts at $2000. Relative jumping before it should fail.
            e2 = InstructionLine.factory(
                lineid, 'jmp $0500', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e2.set_start_address(memzone_mngr.global_zone.start)
            e2.label_scope = TestInstructionParsing.label_values
            self.assertIsInstance(e2, InstructionLine)
            self.assertEqual(e2.byte_size, 3, 'has 3 bytes')
            e2.generate_bytes()
