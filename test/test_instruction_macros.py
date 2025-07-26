import importlib.resources as pkg_resources
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel

from test import config_files


class TestInstructionMacros(unittest.TestCase):
    label_values = None
    isa_model = None
    memory_zone_manager = None
    memzone = None

    @classmethod
    def setUpClass(cls):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_macros.yaml')
        cls.isa_model = AssemblerModel(str(fp), 0)

        global_scope = cls.isa_model.global_label_scope
        global_scope.set_label_value('var1', 0x4589, 1)
        global_scope.set_label_value('my_val', 8, 2)
        global_scope.set_label_value('the_two', 2, 3)
        local_scope = LabelScope(LabelScopeType.LOCAL, global_scope, 'TestInstructionParsing')
        local_scope.set_label_value('.local_var', 10, 3)
        cls.label_values = local_scope
        cls.memory_zone_manager = MemoryZoneManager(
            TestInstructionMacros.isa_model.address_size,
            TestInstructionMacros.isa_model.default_origin,
        )
        cls.memzone = cls.memory_zone_manager.global_zone

    def setUp(self) -> None:
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None

    def test_macro_parsing_numeric_args(self):
        isa_model = self.isa_model
        memzone = self.memzone
        memzone_mngr = self.memory_zone_manager

        line_id = LineIdentifier(1, 'test_macro_parsing_numeric_args')

        ins0: LineWithWords = InstructionLine.factory(
            line_id, 'push2 $1234', 'some comment!', isa_model, memzone, memzone_mngr,
        )
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.word_count, 4, 'has 4 words')
        ins0.label_scope = TestInstructionMacros.label_values
        ins0.generate_words()
        self.assertEqual(
            ins0.get_words(),
            [
                Word(0x0F, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x0F, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction bytes should match'
        )

        ins1 = InstructionLine.factory(line_id, 'mov2 [$2000],[$1234]', 'some comment!', isa_model, memzone, memzone_mngr)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 10, 'has 10 words')
        ins1.label_scope = TestInstructionMacros.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [
                Word(0b01110110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x20, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01110110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(1, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x20, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x35, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins2 = InstructionLine.factory(line_id, 'add16 [$1234], $5678', 'some comment!', isa_model, memzone, memzone_mngr)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.word_count, 16, 'has 16 words')
        ins2.label_scope = TestInstructionMacros.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [
                Word(0b01000110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00010111, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x78, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01110000, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01000110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x35, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00011111, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x56, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01110000, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x35, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins3 = InstructionLine.factory(line_id, 'add16 [$1234], [var1+7]', 'some comment!', isa_model, memzone, memzone_mngr)
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.word_count, 18, 'has 18 words')
        ins3.label_scope = TestInstructionMacros.label_values
        ins3.generate_words()
        self.assertEqual(
            ins3.get_words(),
            [
                Word(0b01000110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00010110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x90, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x45, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01110000, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01000110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x35, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00011110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x91, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x45, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01110000, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x35, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

    def test_macro_parsing_registers(self):
        isa_model = self.isa_model
        memzone = self.memzone
        memzone_mngr = self.memory_zone_manager

        line_id = LineIdentifier(1, 'test_macro_parsing_registers')

        ins4: LineWithWords = InstructionLine.factory(
            line_id, 'push2 [ij + 4]', 'some comment!', isa_model, memzone, memzone_mngr,
        )
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.word_count, 4, 'has 4 words')
        ins4.label_scope = TestInstructionMacros.label_values
        ins4.generate_words()
        self.assertEqual(
            ins4.get_words(),
            [
                Word(0b00001100, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(5, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00001100, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(4, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins5: LineWithWords = InstructionLine.factory(
            line_id, 'push2 [sp + 8]', 'some comment!', isa_model, memzone, memzone_mngr,
        )
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.word_count, 4, 'has 4 words')
        ins5.label_scope = TestInstructionMacros.label_values
        ins5.generate_words()
        self.assertEqual(
            ins5.get_words(),
            [
                Word(0b00001101, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(9, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00001101, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(9, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

    def test_macro_parsing_operands(self):
        isa_model = self.isa_model
        memzone = self.memzone
        memzone_mngr = self.memory_zone_manager

        line_id = LineIdentifier(1, 'test_macro_parsing_operands')

        ins1: LineWithWords = InstructionLine.factory(line_id, 'swap a,j', 'some comment!', isa_model, memzone, memzone_mngr)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 3, 'has 3 words')
        ins1.label_scope = TestInstructionMacros.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [
                Word(0b00001000, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01000011, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00000011, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins2: LineWithWords = InstructionLine.factory(line_id, 'swap i,j', 'some comment!', isa_model, memzone, memzone_mngr)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.word_count, 3, 'has 3 words')
        ins2.label_scope = TestInstructionMacros.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [
                Word(0b00001010, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01010011, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00000011, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins3: LineWithWords = InstructionLine.factory(
            line_id, 'swap a,[ij + 4]', 'some comment!', isa_model, memzone, memzone_mngr,
        )
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.word_count, 5, 'has 5 words')
        ins3.label_scope = TestInstructionMacros.label_values
        ins3.generate_words()
        self.assertEqual(
            ins3.get_words(),
            [
                Word(0b00001000, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01000100, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(4, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00000100, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(4, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins4: LineWithWords = InstructionLine.factory(
            line_id, 'swap [sp+10],[ij + 4]', 'some comment!', isa_model, memzone, memzone_mngr,
        )
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.word_count, 7, 'has 7 words')
        ins4.label_scope = TestInstructionMacros.label_values
        ins4.generate_words()
        self.assertEqual(
            ins4.get_words(),
            [
                Word(0b00001101, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(10, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01101100, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(11, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(4, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00000100, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(4, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins5: LineWithWords = InstructionLine.factory(
            line_id, 'swap [sp+10],[sp+predefined_value1]', 'some comment!',
            isa_model, memzone, memzone_mngr,
        )
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.word_count, 7, 'has 7 words')
        ins5.label_scope = TestInstructionMacros.label_values
        ins5.generate_words()
        self.assertEqual(
            ins5.get_words(),
            [
                Word(0b00001101, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(10, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01101101, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(11, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(21, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b00000101, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(21, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins6: LineWithWords = InstructionLine.factory(
            line_id, 'mov2 [$8008],$1234', 'some comment!', isa_model, memzone, memzone_mngr,
        )
        ins6.set_start_address(1212)
        self.assertIsInstance(ins6, InstructionLine)
        self.assertEqual(ins6.word_count, 8, 'has 8 words')
        ins6.label_scope = TestInstructionMacros.label_values
        ins6.generate_words()
        self.assertEqual(
            ins6.get_words(),
            [
                Word(0b01110111, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x08, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x80, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x34, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0b01110111, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x09, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x80, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
                Word(0x12, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

    def test_macro_with_variants(self):
        isa_model = self.isa_model
        memzone = self.memzone
        memzone_mngr = self.memory_zone_manager

        line_id = LineIdentifier(1, 'test_macro_with_variants')

        ins1: LineWithWords = InstructionLine.factory(line_id, 'incs sp', 'some comment!', isa_model, memzone, memzone_mngr)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.word_count, 1, 'has 1 words')
        ins1.label_scope = TestInstructionMacros.label_values
        ins1.generate_words()
        self.assertEqual(
            ins1.get_words(),
            [
                Word(0b00100110, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )

        ins2: LineWithWords = InstructionLine.factory(line_id, 'incs 3', 'some comment!', isa_model, memzone, memzone_mngr)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.word_count, 1, 'has 1 words')
        ins2.label_scope = TestInstructionMacros.label_values
        ins2.generate_words()
        self.assertEqual(
            ins2.get_words(),
            [
                Word(0b00100011, isa_model.word_size, isa_model.word_segment_size, isa_model.intra_word_endianness),
            ],
            'instruction words should match'
        )
