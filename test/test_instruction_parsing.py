import unittest
import importlib.resources as pkg_resources

from bespokeasm.assembler.bytecode.word import Word
from test import config_files

from bespokeasm.assembler.label_scope import GlobalLabelScope, LabelScope, LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject, LineWithWords
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


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

    def test_instruction_character_set_parsing(self):
        # test instructions with periods in them
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_periods.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )

        ins1 = InstructionLine.factory(
            22,
            '  ma.hl a,[hl+2]',
            'some comment!',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 2, 'has 2 words')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [
                Word(0x45, 8, 8, 'little'),
                Word(0x02, 8, 8, 'little')
            ],
            'instruction should match',
        )

    def test_instruction_variant_matching(self):
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
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
        self.assertEqual(ins1.word_count, 1, 'has 1 word')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [Word(0x00, 8, 8, 'little')],
            'instruction should match',
        )

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
        self.assertEqual(ins2.word_count, 2, 'has 2 words')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [Word(0x44, 8, 8, 'little'), Word(0x02, 8, 8, 'little')],
            'instruction should match',
        )

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
        self.assertEqual(ins3.word_count, 2, 'has 2 words')
        ins3.label_scope = TestInstructionParsing.label_values
        ins3.generate_words()
        self.assertEqual(
            ins3.get_words(),
            [Word(0x45, 8, 8, 'little'), Word(0x06, 8, 8, 'little')],
            'instruction should match',
        )

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
        self.assertEqual(ins4.word_count, 1, 'has 1 word')
        ins4.label_scope = TestInstructionParsing.label_values
        ins4.generate_words()
        self.assertEqual(
            ins4.get_words(),
            [Word(0x81, 8, 8, 'little')],
            'instruction should match',
        )

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
        self.assertEqual(ins5.word_count, 2, 'has 2 words')
        ins5.label_scope = TestInstructionParsing.label_values
        ins5.generate_words()
        self.assertEqual(
            ins5.get_words(),
            [Word(0x9F, 8, 8, 'little'), Word(0x88, 8, 8, 'little')],
            'instruction should match',
        )

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
        fp = pkg_resources.files(config_files).joinpath('test_indirect_indexed_register_operands.yaml')
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
        self.assertEqual(ins0.word_count, 2, 'has 2 words')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_words()
        self.assertEqual(
            ins0.get_words(),
            [
                Word(0xFF, 8, 8, isa_model.intra_word_endianness),
                Word(0x42, 8, 8, isa_model.intra_word_endianness)
            ],
            'instruction byte should match',
        )

        ins1 = InstructionLine.factory(
            22, 'mov [hl+7]+,i', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 3, 'has 3 words')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [
                Word(0xFF, 8, 8, isa_model.intra_word_endianness),
                Word(0x81, 8, 8, isa_model.intra_word_endianness),
                Word(0x07, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        ins2 = InstructionLine.factory(
            22, 'mov [sp+$1D],[mar+a]++', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.word_count, 3, 'has 3 words')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [
                Word(0xFF, 8, 8, isa_model.intra_word_endianness),
                Word(0x64, 8, 8, isa_model.intra_word_endianness),
                Word(0x1D, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

    def test_indexed_register_operands(self):
        fp = pkg_resources.files(config_files).joinpath('test_indirect_indexed_register_operands.yaml')
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
        self.assertEqual(ins0.word_count, 1, 'has 1 words')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_words()
        self.assertEqual(
            ins0.get_words(),
            [Word(0xC2, 8, 8, 'little')],
            'instruction byte should match',
        )

        ins1 = InstructionLine.factory(
            22, 'jmp hl+[sp+7]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 2, 'has 2 words')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [Word(0xC3, 8, 8, 'little'), Word(0x07, 8, 8, 'little')],
            'instruction byte should match',
        )

    def test_indirect_indexed_regsiter_operands(self):
        fp = pkg_resources.files(config_files).joinpath('test_indirect_indexed_register_operands.yaml')
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
        self.assertEqual(ins0.word_count, 1, 'has 1 words')
        ins0.label_scope = TestInstructionParsing.label_values
        ins0.generate_words()
        self.assertEqual(
            ins0.get_words(),
            [Word(0x81, 8, 8, 'little')],
            'instruction byte should match',
        )

        ins1 = InstructionLine.factory(
            22, 'mov [$2000], [hl+i]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr
        )
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 3, 'has 3 words')
        ins1.label_scope = TestInstructionParsing.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [Word(0xB1, 8, 8, 'little'), Word(0x00, 8, 8, 'little'), Word(0x20, 8, 8, 'little')],
            'instruction byte should match',
        )

        ins2: LineWithWords = InstructionLine.factory(
            22, 'mov [$2000], [hl+[sp+2]]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.word_count, 4, 'has 4 words')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [
                Word(0xB3, 8, 8, 'little'),
                Word(0x00, 8, 8, 'little'),
                Word(0x20, 8, 8, 'little'),
                Word(0x02, 8, 8, 'little'),
            ],
            'instruction byte should match',
        )

        ins2: LineWithWords = InstructionLine.factory(
            22, 'mov [mar + $44], [$8020]', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.word_count, 4, 'has 4 words')
        ins2.label_scope = TestInstructionParsing.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [
                Word(0xFE, 8, 8, 'little'),
                Word(0x20, 8, 8, 'little'),
                Word(0x80, 8, 8, 'little'),
                Word(0x44, 8, 8, 'little'),
            ],
            'instruction byte should match, operands reversed',
        )

        ins4: LineWithWords = InstructionLine.factory(
            22, 'cmp [hl+i],0', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
#        self.assertEqual(ins4.word_count, 3, 'has 3 words')
        ins4.label_scope = TestInstructionParsing.label_values
        ins4.generate_words()
        self.assertEqual(
            ins4.get_words(),
            [
                Word(0xFF, 8, 8, isa_model.intra_word_endianness),
                Word(0x8F, 8, 8, isa_model.intra_word_endianness),
                Word(0x00, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        ins5: LineWithWords = InstructionLine.factory(
            22, 'cmp [hl+[4]],0', 'some comment!',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        ins5.label_scope = TestInstructionParsing.label_values
        ins5.generate_words()
        self.assertEqual(
            ins5.get_words(),
            [
                Word(0xFF, 8, 8, isa_model.intra_word_endianness),
                Word(0xEF, 8, 8, isa_model.intra_word_endianness),
                Word(0x04, 8, 8, isa_model.intra_word_endianness),
                Word(0x00, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        with self.assertRaises(SystemExit, msg='no instruction  should match here'):
            bad1 = InstructionLine.factory(
                22, '  mov a, [sp+i]', 'some comment!',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            bad1.set_start_address(666)
            bad1.label_scope = TestInstructionParsing.label_values
            bad1.generate_words()

    def test_label_parsing(self):
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
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
            'LABEL = %00001111',
            isa_model,
            TestInstructionParsing.label_values,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConditionStack(),
            0,
        )[0]
        self.assertIsInstance(l1, LabelLine)
        self.assertTrue(l1.is_constant, )
        self.assertEqual(l1.get_value(), 0x0F, 'value should be right')

        l2: LineObject = LineOjectFactory.parse_line(
            lineid,
            '.local_label:',
            isa_model,
            TestInstructionParsing.label_values,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConditionStack(),
            0,
        )[0]
        l2.set_start_address(42)
        l2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(l2, LabelLine)
        self.assertFalse(l2.is_constant, )
        self.assertEqual(l2.get_value(), 42, 'value should be right')

        l3: LineObject = LineOjectFactory.parse_line(
            lineid,
            'old_style EQU 42H',
            isa_model,
            TestInstructionParsing.label_values,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConditionStack(),
            0,
        )[0]
        l3.set_start_address(42)
        l3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(l3, LabelLine)
        self.assertTrue(l3.is_constant, 'label should be a constant')
        self.assertEqual(l3.get_value(), 0x42, 'value should be right')

    def test_operand_bytecode_ordering(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b00010011, 8, 8, 'big'), Word(0xF0, 8, 8, 'big')],
            'instruction byte should match',
        )

        t2 = InstructionLine.factory(
            lineid, '  ld [$20], x', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 2, 'has 2 words')
        t2.generate_words()
        self.assertEqual(
            t2.get_words(),
            [Word(0b10011100, 8, 8, 'big'), Word(0x20, 8, 8, 'big')],
            'instruction byte should match',
        )

    def test_deferred_operands(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b00010101, 8, 8, 'big'), Word(0xF0, 8, 8, 'big')],
            'instruction byte should match',
        )

        t2 = InstructionLine.factory(
            lineid, '  ld [[my_val]],x', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 2, 'has 2 words')
        t2.generate_words()
        self.assertEqual(
            t2.get_words(),
            [Word(0b10011101, 8, 8, 'big'), Word(0x08, 8, 8, 'big')],
            'instruction byte should match',
        )

    def test_instruction_bytecode_suffixes(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b11010101, 8, 8, 'big'), Word(0xF0, 8, 8, 'big')],
            'instruction byte should match',
        )

    def test_enumeration_operand(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b00111001, 8, 8, 'big'), Word(0xBB, 8, 8, 'big')],
            'instruction byte should match',
        )

    def test_numeric_bytecode_operand(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 1, 'has 1 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b10011011, 8, 8, 'big')],
            'instruction byte should match',
        )

        t2 = InstructionLine.factory(
            lineid, '  tstb a, 7', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 1, 'has 1 words')
        t2.generate_words()
        self.assertEqual(
            t2.get_words(),
            [Word(0b00011111, 8, 8, 'big')],
            'instruction byte should match',
        )

        t3 = InstructionLine.factory(
            lineid, '  enumarg 6', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(1)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.word_count, 2, 'has 2 words')
        t3.generate_words()
        self.assertEqual(
            t3.get_words(),
            [Word(0xFE, 8, 8, 'big'), Word(0x40, 8, 8, 'big')],
            'instruction byte should match',
        )

        with self.assertRaises(SystemExit, msg='test bounds'):
            e1 = InstructionLine.factory(
                lineid, '  tstb b, 14', 'second argument is too large',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e1.label_scope = TestInstructionParsing.label_values
            e1.generate_words()

        with self.assertRaises(SystemExit, msg='test invalid enumerations'):
            e2 = InstructionLine.factory(
                lineid, '  enumarg 12', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e2.label_scope = TestInstructionParsing.label_values
            e2.generate_words()

    def test_numeric_enumeration_operand(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 1, 'has 1 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b10101000, 8, 8, 'big')],
            'instruction byte should match',
        )

        t2 = InstructionLine.factory(
            lineid, 'sftl a, 1', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 1, 'has 1 words')
        t2.generate_words()
        self.assertEqual(
            t2.get_words(),
            [Word(0b10001001, 8, 8, 'big')],
            'instruction byte should match',
        )

        with self.assertRaises(SystemExit, msg='test invalid enumeration values'):
            e1 = InstructionLine.factory(
                lineid, 'num 7', 'number 7 is not allowed',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e1.label_scope = TestInstructionParsing.label_values
            e1.generate_words()

    def test_expressions_in_operations(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b11010101, 8, 8, 'big'), Word(0x11, 8, 8, 'big')],
            'instruction byte should match',
        )

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
        fp = pkg_resources.files(config_files).joinpath('test_operand_features.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [Word(0b11010101, 8, 8, 'big'), Word(0x11, 8, 8, 'big')],
            'instruction byte should match',
        )

    def test_operand_order(self):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')
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
        self.assertEqual(t1.word_count, 3, 'has 3 words')
        t1.generate_words()
        self.assertEqual(
            list(t1.get_words()),
            [
                Word(0x80, 8, 8, isa_model.intra_word_endianness),
                Word(0x12, 8, 8, isa_model.intra_word_endianness),
                Word(0x30, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        t2 = InstructionLine.factory(
            lineid, 'ed aa,bb,cc', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(1)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 3, 'has 3 words')
        t2.generate_words()
        self.assertEqual(
            list(t2.get_words()),
            [Word(0x88, 8, 8, 'little'), Word(0x32, 8, 8, 'little'), Word(0x10, 8, 8, 'little')],
            'instruction byte should match',
        )

        t3 = InstructionLine.factory(
            lineid, 'mv a,b,c', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(1)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.word_count, 3, 'has 3 words')
        t3.generate_words()
        self.assertEqual(
            list(t3.get_words()),
            [
                Word(0x81, 8, 8, isa_model.intra_word_endianness),
                Word(0x32, 8, 8, isa_model.intra_word_endianness),
                Word(0x10, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

    def test_operand_expression(self):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        lineid = LineIdentifier(42, 'test_operand_order')

        t1 = InstructionLine.factory(
            lineid,
            'ADI var1w+0',
            'comment',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )

        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.word_count, 2, 'has 2 words')

    def test_relative_address_operand(self):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')
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
        self.assertEqual(t1.word_count, 3, 'has 3 words')
        t1.generate_words()
        self.assertEqual(
            list(t1.get_words()),
            [
                Word(0xE5, 8, 8, isa_model.intra_word_endianness),
                Word(0x20, 8, 8, isa_model.intra_word_endianness),
                Word(0x80, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        t2 = InstructionLine.factory(
            lineid, 'jmp {.loop}', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(0x8000)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 2, 'has 2 words')
        t2.generate_words()
        self.assertEqual(
            list(t2.get_words()),
            [Word(0xE6, 8, 8, 'little'), Word(0x20, 8, 8, 'little')],
            'instruction byte should match',
        )

        t3 = InstructionLine.factory(
            lineid, 'jmpr .loop', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(0x8000)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.word_count, 2, 'has 2 words')
        t3.generate_words()
        self.assertEqual(
            list(t3.get_words()),
            [Word(0xEE, 8, 8, 'little'), Word(0x20, 8, 8, 'little')],
            'instruction byte should match',
        )

        t4 = InstructionLine.factory(
            lineid, 'jmpre .loop', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t4.set_start_address(0x8000)
        t4.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t4, InstructionLine)
        self.assertEqual(t4.word_count, 2, 'has 2 words')
        t4.generate_words()
        self.assertEqual(
            list(t4.get_words()),
            [Word(0xEF, 8, 8, 'little'), Word(0x1F, 8, 8, 'little')],
            'instruction byte should match',
        )

        # test offsets that are too large or too small
        with self.assertRaises(SystemExit, msg='offset out of range'):
            bt1 = InstructionLine.factory(
                lineid, 'jmp {.loop}', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            bt1.set_start_address(0x7000)
            bt1.label_scope = TestInstructionParsing.label_values
            bt1.generate_words()

        with self.assertRaises(SystemExit, msg='offset out of range'):
            bt2 = InstructionLine.factory(
                lineid, 'jmp {.loop}', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            bt2.set_start_address(0x9000)
            bt2.label_scope = TestInstructionParsing.label_values
            bt2.generate_words()

    def test_valid_address_operand_enforcement(self):
        fp = pkg_resources.files(config_files).joinpath('test_valid_address_enforcement.yaml')
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
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            list(t1.get_words()),
            [Word(0xEE, 8, 8, 'little'), Word(0xF8, 8, 8, 'little')],
            'instruction byte should match',
        )

        with self.assertRaises(SystemExit, msg='address out of range'):
            # the GLOBAL memory zone starts at $2000. Relative jumping before it should fail.
            t1 = InstructionLine.factory(
                lineid, 'jmpr $1FF8', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            t1.set_start_address(memzone_mngr.global_zone.start)
            t1.label_scope = TestInstructionParsing.label_values
            self.assertIsInstance(t1, InstructionLine)
            self.assertEqual(t1.word_count, 2, 'has 2 words')
            t1.generate_words()

        with self.assertRaises(SystemExit, msg='address out of range'):
            # the GLOBAL memory zone starts at $2000. Relative jumping before it should fail.
            e2 = InstructionLine.factory(
                lineid, 'jmp $0500', 'comment',
                isa_model, memzone_mngr.global_zone, memzone_mngr,
            )
            e2.set_start_address(memzone_mngr.global_zone.start)
            e2.label_scope = TestInstructionParsing.label_values
            self.assertIsInstance(e2, InstructionLine)
            self.assertEqual(e2.word_count, 3, 'has 3 words')
            e2.generate_words()

    def test_address_operands(self):
        from bespokeasm.assembler.model.operand.types.address import AddressByteCodePart

        fp = pkg_resources.files(config_files).joinpath('test_valid_address_enforcement.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size, isa_model.default_origin, isa_model.predefined_memory_zones,
        )
        memzone_32bit_mngr = MemoryZoneManager(32, 0,)
        lineid = LineIdentifier(42, 'test_address_operands')

        # first, test argument value generation with no LSB slicing
        bc1 = AddressByteCodePart(
            '$2020',
            16,
            True,
            isa_model.multi_word_endianness,    # little endian
            isa_model.intra_word_endianness,
            lineid,
            memzone_mngr.global_zone,
            False,
            False,
            isa_model.word_size,
            isa_model.word_segment_size,
        )
        value1 = bc1.get_value(TestInstructionParsing.label_values, 0x2010, 32)
        self.assertEqual(value1, 0x2020, 'byte code should match')

        # now, test argument value generation with LSB slicing
        bc2 = AddressByteCodePart(
            '$2045',
            8,
            True,
            isa_model.multi_word_endianness,    # little endian
            isa_model.intra_word_endianness,
            lineid,
            memzone_mngr.global_zone,
            True,
            True,
            isa_model.word_size,
            isa_model.word_segment_size,
        )
        value2 = bc2.get_value(TestInstructionParsing.label_values, 0x2010, 32)
        self.assertEqual(value2, 0x45, 'byte code should match')

        with self.assertRaises(ValueError, msg="address MSBs don't match"):
            bc2.get_value(TestInstructionParsing.label_values, 0x2250, 32)

        # test 16-bit slize with a 32-bit address
        bc3 = AddressByteCodePart(
            '$19458899',
            16,
            True,
            isa_model.multi_word_endianness,    # little endian
            isa_model.intra_word_endianness,
            lineid,
            memzone_32bit_mngr.global_zone,
            True,
            True,
            isa_model.word_size,
            isa_model.word_segment_size,
        )
        value3 = bc3.get_value(TestInstructionParsing.label_values, 0x19451000, 32)
        self.assertEqual(value3, 0x8899, 'byte code should match')
        with self.assertRaises(ValueError, msg="address MSBs don't match"):
            bc3.get_value(TestInstructionParsing.label_values, 0x20241000, 32)

        #  test error conditions
        # error case: extraneous comparison operators ignored
        with self.assertRaises(SystemExit, msg='extraneous comparison operators should be ignored'):
            AddressByteCodePart(
                '<$2024',
                8,
                True,
                isa_model.multi_word_endianness,    # little endian
                isa_model.intra_word_endianness,
                lineid,
                memzone_mngr.global_zone,
                True,
                False,
                isa_model.word_size,
                isa_model.word_segment_size,
            )

        # Test byte code generation for sliced addresses
        t1 = InstructionLine.factory(
            lineid, 'jmp_local $2FF8', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(0x2F10)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            list(t1.get_words()),
            [
                Word(0xE0, 8, 8, isa_model.intra_word_endianness),
                Word(0xF8, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        # ensure MSBs match
        t1.set_start_address(0x3350)
        with self.assertRaises(ValueError, msg="address MSBs don't match"):
            t1.generate_words()

        # Test bye code generation for unsliced addresses
        t2 = InstructionLine.factory(
            lineid, 'jmpa $2FF8', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t2.set_start_address(0x2F10)
        t2.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t2, InstructionLine)
        self.assertEqual(t2.word_count, 3, 'has 3 words')
        t2.generate_words()
        self.assertEqual(
            list(t2.get_words()),
            [
                Word(0xE1, 8, 8, isa_model.intra_word_endianness),
                Word(0xF8, 8, 8, isa_model.intra_word_endianness),
                Word(0x2F, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        # test operand address is in target memory zone
        t3 = InstructionLine.factory(
            lineid, 'jmp_test1 $5150', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t3.set_start_address(0x2F10)
        t3.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t3, InstructionLine)
        self.assertEqual(t3.word_count, 3, 'has 3 words')
        t3.generate_words()
        self.assertEqual(
            list(t3.get_words()),
            [
                Word(0xE2, 8, 8, isa_model.intra_word_endianness),
                Word(0x50, 8, 8, isa_model.intra_word_endianness),
                Word(0x51, 8, 8, isa_model.intra_word_endianness),
            ],
            'instruction byte should match',
        )

        # enforce operand address is in target memory zone
        t4 = InstructionLine.factory(
            lineid, 'jmp_test1 $4425', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t4.set_start_address(0x2F10)
        t4.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t4, InstructionLine)
        self.assertEqual(t4.word_count, 3, 'has 3 words')
        with self.assertRaises(SystemExit, msg='address not in target memory zone'):
            t4.generate_words()

    def test_instruction_parsing_16bit_word(self):
        fp = pkg_resources.files(config_files).joinpath('test_16bit_data_words.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )
        lineid = LineIdentifier(1, 'test_instruction_parsing_16bit_word')

        t1 = InstructionLine.factory(
            lineid, 'mov a,[$1234]', 'comment',
            isa_model, memzone_mngr.global_zone, memzone_mngr,
        )
        t1.set_start_address(1)
        t1.label_scope = TestInstructionParsing.label_values
        self.assertIsInstance(t1, InstructionLine)
        self.assertEqual(t1.word_count, 2, 'has 2 words')
        t1.generate_words()
        self.assertEqual(
            t1.get_words(),
            [
                Word(0x0802, 16, 16, 'big'),
                Word(0x1234, 16, 16, 'big'),
            ],
            'instruction byte should match',
        )
