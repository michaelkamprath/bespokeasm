import unittest
import importlib.resources as pkg_resources

from test import config_files

from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel


class TestInstructionParsing(unittest.TestCase):
    label_values = None
    @classmethod
    def setUpClass(cls):
        cls.label_values = GlobalLabelScope(set())
        cls.label_values.set_label_value('var1', 12, 1)
        cls.label_values.set_label_value('my_val', 8, 2)
        cls.label_values.set_label_value('the_two', 2, 3)

    def test_instruction_variant_matching(self):
        with pkg_resources.path(config_files, 'test_instructions_with_variants.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)

        # start simple
        ins1 = InstructionLine.factory(22, '  nop', 'some comment!', isa_model)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 1, 'has 1 byte')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_bytes()
        self.assertEqual(ins1.get_bytes(), bytearray([0x00]), 'instruction should match')

        # match default variant operand sets
        ins2 = InstructionLine.factory(22, '  mov a, [sp+2]', 'some comment!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 2, 'has 2 byte')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(ins2.get_bytes(), bytearray([0x44, 0x02]), 'instruction should match')

        # match default variant specific operand
        ins3 = InstructionLine.factory(22, '  mov a, [hl+6]', 'some comment!', isa_model)
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 2, 'has 2 byte')
        ins3.label_scope = TestInstructionParsing.label_values
        ins3.generate_bytes()
        self.assertEqual(ins3.get_bytes(), bytearray([0x45, 0x06]), 'instruction should match')

        # match first variant
        ins4 = InstructionLine.factory(22, '  mov a, h', 'some comment!', isa_model)
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.byte_size, 1, 'has 1 byte')
        ins4.label_scope = TestInstructionParsing.label_values
        ins4.generate_bytes()
        self.assertEqual(ins4.get_bytes(), bytearray([0x81]), 'instruction should match')

        # match second variant
        ins5 = InstructionLine.factory(22, '  mov h, $88', 'some comment!', isa_model)
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.byte_size, 2, 'has 2 byte')
        ins5.label_scope = TestInstructionParsing.label_values
        ins5.generate_bytes()
        self.assertEqual(ins5.get_bytes(), bytearray([0x9F, 0x88]), 'instruction should match')

        # match no variant
        with self.assertRaises(SystemExit, msg='no instruction variant should match here'):
            InstructionLine.factory(22, '  mov h, l', 'some comment!', isa_model)

        with self.assertRaises(SystemExit, msg='no instruction variant should match here'):
            InstructionLine.factory(22, '  mov 27', 'some comment!', isa_model)

    def test_indirect_indexed_regsiter_operands(self):
        with pkg_resources.path(config_files, 'test_indirect_indexed_register_operands.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)

        ins0 = InstructionLine.factory(22, 'mov a, [hl+i]', 'some comment!', isa_model)
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.byte_size, 1, 'has 1 bytes')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_bytes()
        self.assertEqual(list(ins0.get_bytes()), [0x81], 'instruction byte should match')

        ins1 = InstructionLine.factory(22, 'mov [$2000], [hl+i]', 'some comment!', isa_model)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 3, 'has 3 bytes')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_bytes()
        self.assertEqual(list(ins1.get_bytes()), [0xB1, 0x00, 0x20], 'instruction byte should match')

        ins2 = InstructionLine.factory(22, 'mov [$2000], [hl+[sp+2]]', 'some comment!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 4, 'has 4 bytes')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(list(ins2.get_bytes()), [0xB3, 0x00, 0x20, 0x02], 'instruction byte should match')

        ins2 = InstructionLine.factory(22, 'mov [mar + $44], [$8020]', 'some comment!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 4, 'has 4 bytes')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_bytes()
        self.assertEqual(list(ins2.get_bytes()), [0xFE, 0x20, 0x80, 0x44], 'instruction byte should match, operands reversed')

        with self.assertRaises(SystemExit, msg='no instruction  should match here'):
            bad1 = InstructionLine.factory(22, '  mov a, [sp+i]', 'some comment!', isa_model)
            bad1.set_start_address(666)
            bad1.label_scope = TestInstructionParsing.label_values
            bad1.generate_bytes()

    def test_label_parsing(self):
        with pkg_resources.path(config_files, 'test_instructions_with_variants.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        lineid = LineIdentifier(42, 'test_label_parsing')
        l1: LineObject = LineOjectFactory.parse_line(lineid, "LABEL = %00001111", isa_model)
        self.assertIsInstance(l1, LabelLine)
        self.assertTrue(l1.is_constant, )
        self.assertEqual(l1.get_value(), 0x0F, 'value should be right')

    def test_operand_bytecode_ordering(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        lineid = LineIdentifier(13, 'test_operand_bytecode_ordering')

        t1 = InstructionLine.factory(lineid, '  ld a, $F0', 'comment', isa_model)
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b00010011, 0xF0], 'instruction byte should match')

        t2 = InstructionLine.factory(lineid, '  ld [$20], x', 'comment', isa_model)
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 2, 'has 2 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b10011100, 0x20], 'instruction byte should match')

    def test_deferred_operands(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        lineid = LineIdentifier(13, 'test_deferred_operands')

        t1 = InstructionLine.factory(lineid, '  ld a, [[$F0]]', 'comment', isa_model)
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b00010101, 0xF0], 'instruction byte should match')

        t2 = InstructionLine.factory(lineid, '  ld [[my_val]],x', 'comment', isa_model)
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 2, 'has 2 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b10011101, 0x08], 'instruction byte should match')

    def test_instruction_byte_code_suffixes(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        lineid = LineIdentifier(13, 'test_instruction_byte_code_suffixes')

        t1 = InstructionLine.factory(lineid, '  foo [[$F0]]', 'comment', isa_model)
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b11010101, 0xF0], 'instruction byte should match')

    def test_enumeration_operand(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        lineid = LineIdentifier(21, 'test_enumeration_operand')

        t1 = InstructionLine.factory(lineid, '  tst bee', 'comment', isa_model)
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 2, 'has 2 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b00111001, 0xBB], 'instruction byte should match')

    def test_numeric_bytecode_operand(self):
        with pkg_resources.path(config_files, 'test_operand_features.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        lineid = LineIdentifier(33, 'test_numeric_bytecode_operand')

        t1 = InstructionLine.factory(lineid, '  tstb x, the_two+1', 'comment', isa_model)
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.byte_size, 1, 'has 1 bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes()), [0b10011011], 'instruction byte should match')

        t2 = InstructionLine.factory(lineid, '  tstb a, 7', 'comment', isa_model)
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.byte_size, 1, 'has 1 bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes()), [0b00011111], 'instruction byte should match')

        with self.assertRaises(SystemExit, msg='test bounds'):
            e1 = InstructionLine.factory(lineid, '  tstb b, 14', 'second argument is too large', isa_model)
            e1.label_scope = TestInstructionParsing.label_values
            e1.generate_bytes()