import importlib.resources as pkg_resources
import unittest
import yaml

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
import bespokeasm.assembler.model.operand_set as AS
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser import InstructioParser
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager

from test import config_files

#
# Tests
#


class TestConfigObject(unittest.TestCase):
    label_values = None

    @classmethod
    def setUpClass(cls):
        cls._register_argument_config_str = pkg_resources.files(config_files) \
            .joinpath('register_argument_exmaple_config.yaml').read_text()
        cls._eater_sap1_config_str = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml').read_text()
        cls.label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        cls.label_values.set_label_value('label1', 2, 1)
        cls.label_values.set_label_value('LABEL2', 0xF0, 2)

    def test_argument_set_construction(self):
        conf1 = yaml.safe_load(self._eater_sap1_config_str)
        arg_collection1 = AS.OperandSetCollection(conf1['operand_sets'], 'big', 'big', set(), 8, 8,)
        self.assertEqual(len(arg_collection1), 2, 'there are 2 argument sets')
        self.assertTrue('integer' in arg_collection1)
        self.assertTrue('address' in arg_collection1)

        conf2 = yaml.safe_load(self._register_argument_config_str)
        arg_collection2 = AS.OperandSetCollection(
            conf2['operand_sets'], 'little', 'little', {'a', 'i', 'j', 'sp', 'ij', 'mar'}, 8, 8,
        )
        self.assertEqual(len(arg_collection2), 4, 'there are 4 argument sets')
        self.assertTrue('8_bit_source' in arg_collection2)
        self.assertTrue('8_bit_destination' in arg_collection2)
        self.assertTrue('int8' in arg_collection2)
        self.assertTrue('int16' in arg_collection2)

    def test_instruction_parsing(self):
        fp = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        model1 = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(model1.address_size, model1.default_origin)

        test_line_id = LineIdentifier(1212, 'test_instruction_parsing')

        pi1 = InstructioParser.parse_instruction(
            model1, test_line_id, 'LDA $f', memzone_mngr,
        )
        self.assertEqual(pi1.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            pi1.get_words(TestConfigObject.label_values, 0x8000, pi1.word_count),
            [Word(0x1F, model1.word_size, model1.word_segment_size, model1.intra_word_endianness)],
            'assembled instruction',
        )

        pi2 = InstructioParser.parse_instruction(
            model1, test_line_id, 'add label1+5', memzone_mngr,
        )
        self.assertEqual(pi2.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            pi2.get_words(TestConfigObject.label_values, 0x8000, pi2.word_count),
            [Word(0x27, model1.word_size, model1.word_segment_size, model1.intra_word_endianness)],
            'assembled instruction',
        )

        pi3 = InstructioParser.parse_instruction(
            model1, test_line_id, 'out', memzone_mngr,
        )
        self.assertEqual(pi3.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            pi3.get_words(TestConfigObject.label_values, 0x8000, pi3.word_count),
            [Word(0xE0, model1.word_size, model1.word_segment_size, model1.intra_word_endianness)],
            'assembled instruction'
        )

        fp = pkg_resources.files(config_files).joinpath('register_argument_exmaple_config.yaml')
        model2 = AssemblerModel(str(fp), 0)
        memzone_mngr2 = MemoryZoneManager(model2.address_size, model2.default_origin)

        piA = InstructioParser.parse_instruction(
            model2, LineIdentifier(1, 'test_mov_a_i'), 'mov a, i', memzone_mngr2,
        )
        self.assertEqual(piA.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piA.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b01000010, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'assembled instruction'
        )

        piB = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov a,[$1120 + label1]', memzone_mngr2,
        )
        self.assertEqual(piB.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piB.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01000110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x22, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x11, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'assembled instruction'
        )

        piC = InstructioParser.parse_instruction(
            model2, test_line_id, 'add i', memzone_mngr2,
        )
        self.assertEqual(piC.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piC.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b10111010, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'assembled instruction'
        )

        piD = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [$110D + (label1 + LABEL2)] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piD.word_count, 4, 'assembled instruciton is 4 byte')
        self.assertEqual(
            piD.get_words(TestConfigObject.label_values, 0x8000, 4),
            [
                Word(0b01110111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0xFF, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x11, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piE = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp - label1] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piE.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piE.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0b11111110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piF = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp+label1] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piF.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piF.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piG = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piG.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piG.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piH = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [$8000], [label1]', memzone_mngr2,
        )
        self.assertEqual(piH.word_count, 5, 'assembled instruciton is 5 byte')
        self.assertEqual(
            piH.get_words(TestConfigObject.label_values, 0x8000, 5),
            [
                Word(0b01110110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x80, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piI = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [mar], [label1]', memzone_mngr2,
        )
        self.assertEqual(piI.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piI.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01100110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'no offset should be emitted for [mar]'
        )

        piJ = InstructioParser.parse_instruction(
            model2, test_line_id, 'swap [$8000], [label1]', memzone_mngr2,
        )
        self.assertEqual(piJ.word_count, 5, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piJ.get_words(TestConfigObject.label_values, 0x8000, 5),
            [
                Word(0b11110110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x80, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should NOT be in reverse order'
        )

        piK = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp+2], [sp+4]', memzone_mngr2,
        )
        self.assertEqual(piK.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piK.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101101, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x04, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piL = InstructioParser.parse_instruction(
            model2, test_line_id, 'pop i', memzone_mngr2,
        )
        self.assertEqual(piL.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piL.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b00001010, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'pop to i'
        )

        piM = InstructioParser.parse_instruction(
            model2, LineIdentifier(158, 'test_pop_empty_arg'), 'pop', memzone_mngr2,
        )
        self.assertEqual(piM.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piM.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b00001111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'just pop'
        )

        piN = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov a, [sp+2]', memzone_mngr2,
        )
        self.assertEqual(piN.word_count, 2, 'assembled instruciton is 2 byte')
        self.assertEqual(
            piN.get_words(TestConfigObject.label_values, 0x8000, 2),
            [
                Word(0b01000101, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'just move [sp+2] into a'
        )

        with self.assertRaises(SystemExit, msg='should error on unallowed operand combinations'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a, a', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='[mar] should have no offset'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov [mar+2], [label1]', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='should error due to too many operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a, i, j', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='should error due to too many operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'nop 123', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='should error due to too few operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a', memzone_mngr2)

    def test_bad_registers_in_configuratin(self):
        fp = pkg_resources.files(config_files).joinpath('test_bad_registers_in_configuratin.yaml')
        with self.assertRaises(SystemExit, msg='model configuration should not specify prohibited register names'):
            AssemblerModel(str(fp), 0)

    def test_min_required_version(self):
        fp = pkg_resources.files(config_files).joinpath('test_min_required_version_config.yaml')
        with self.assertRaises(SystemExit, msg='the min version check should fail'):
            AssemblerModel(str(fp), 0)

    def test_predefined_entities(self):
        fp = pkg_resources.files(config_files).joinpath('test_compiler_features.yaml')
        model = AssemblerModel(str(fp), 0)

        self.assertSetEqual(set(model.predefined_labels), {'CONST1', 'CONST2', 'buffer'}, 'label set should equal')

    def test_mnemonic_lists(self):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_macros.yaml')
        model = AssemblerModel(str(fp), 0)

        self.assertSetEqual(
            model.instruction_mnemonics,
            {'push', 'pop', 'mov', 'add', 'addc', 'ldar'},
            'instruction mnomonics should match'
        )
        self.assertSetEqual(
            model.macro_mnemonics,
            {'push2', 'mov2', 'add16', 'swap', 'incs'},
            'macro mnomonics should match'
        )
        self.assertListEqual(
            model.operation_mnemonics,
            [
                'push', 'pop', 'mov', 'add',
                'addc', 'ldar', 'push2', 'mov2',
                'add16', 'swap', 'incs',
            ],
            'instruction + macro mnomonics should match'
        )

    def test_word_size_and_segment_size(self):
        fp = pkg_resources.files(config_files).joinpath('test_16bit_data_words.yaml')
        model = AssemblerModel(str(fp), 0)
        self.assertEqual(model.word_size, 16, 'word size should match')
        self.assertEqual(model.word_segment_size, 16, 'word segment size should match')
        self.assertEqual(model.intra_word_endianness, 'big', 'intra-word endianness should match')
        self.assertEqual(model.multi_word_endianness, 'big', 'multi-word endianness should match')

    def test_predefined_data_creation(self):
        # TODO: add test for predefined data creation
        pass


if __name__ == '__main__':
    unittest.main()
