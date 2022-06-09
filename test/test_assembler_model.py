import importlib.resources as pkg_resources
import unittest
import yaml

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
import bespokeasm.assembler.model.operand as A
import bespokeasm.assembler.model.operand_set as AS
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser import InstructioParser

from test import config_files

#
# Tests
#

class TestConfigObject(unittest.TestCase):
    label_values = None

    @classmethod
    def setUpClass(cls):
        cls._register_argument_config_str = pkg_resources.read_text(config_files, 'register_argument_exmaple_config.yaml')
        cls._eater_sap1_config_str = pkg_resources.read_text(config_files, 'eater-sap1-isa.yaml')
        cls.label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        cls.label_values.set_label_value('label1', 2, 1)
        cls.label_values.set_label_value('LABEL2', 0xF0, 2)

    def test_argument_set_construction(self):
        conf1 = yaml.safe_load(self._eater_sap1_config_str)
        arg_collection1 = AS.OperandSetCollection(conf1['operand_sets'], 'big', set([]))
        self.assertEqual(len(arg_collection1),2, 'there are 2 argument sets')
        self.assertTrue('integer' in arg_collection1)
        self.assertTrue('address' in arg_collection1)

        conf2 = yaml.safe_load(self._register_argument_config_str)
        arg_collection2 = AS.OperandSetCollection(conf2['operand_sets'], 'little', set([ 'a', 'i', 'j', 'sp', 'ij',  'mar']))
        self.assertEqual(len(arg_collection2),4, 'there are 4 argument sets')
        self.assertTrue('8_bit_source' in arg_collection2)
        self.assertTrue('8_bit_destination' in arg_collection2)
        self.assertTrue('int8' in arg_collection2)
        self.assertTrue('int16' in arg_collection2)

    def test_instruction_parsing(self):
        with pkg_resources.path(config_files, 'eater-sap1-isa.yaml') as fp:
            model1 = AssemblerModel(str(fp), 0)

        test_line_id = LineIdentifier(1212, 'test_instruction_parsing')

        pi1 = InstructioParser.parse_instruction(model1, test_line_id, 'LDA $f')
        self.assertEqual(pi1.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(pi1.get_bytes(TestConfigObject.label_values), bytearray([0x1F]), 'assembled instruction')

        pi2 = InstructioParser.parse_instruction(model1, test_line_id, 'add label1+5')
        self.assertEqual(pi2.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(pi2.get_bytes(TestConfigObject.label_values), bytearray([0x27]), 'assembled instruction')

        pi3 = InstructioParser.parse_instruction(model1, test_line_id, 'out')
        self.assertEqual(pi3.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(pi3.get_bytes(TestConfigObject.label_values), bytearray([0xE0]), 'assembled instruction')

        with pkg_resources.path(config_files, 'register_argument_exmaple_config.yaml') as fp:
            model2 = AssemblerModel(str(fp), 0)

        piA = InstructioParser.parse_instruction(model2, LineIdentifier(1,'test_mov_a_i'), 'mov a, i')
        self.assertEqual(piA.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(list(piA.get_bytes(TestConfigObject.label_values)), [0b01000010], 'assembled instruction')

        piB = InstructioParser.parse_instruction(model2, test_line_id, 'mov a,[$1120 + label1]')
        self.assertEqual(piB.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piB.get_bytes(TestConfigObject.label_values), bytearray([0b01000110, 0x22, 0x11]), 'assembled instruction')

        piC = InstructioParser.parse_instruction(model2, test_line_id, 'add i')
        self.assertEqual(piC.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(piC.get_bytes(TestConfigObject.label_values), bytearray([0b10111010]), 'assembled instruction')

        piD = InstructioParser.parse_instruction(model2, test_line_id, 'mov [$110D + (label1 + LABEL2)] , 0x88')
        self.assertEqual(piD.byte_size, 4, 'assembled instruciton is 4 byte')
        self.assertEqual(piD.get_bytes(TestConfigObject.label_values), bytearray([0b01110111,  0x88, 0xFF, 0x11]), 'arguments should be in reverse order')

        piE = InstructioParser.parse_instruction(model2, test_line_id, 'mov [sp - label1] , 0x88')
        self.assertEqual(piE.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piE.get_bytes(TestConfigObject.label_values), bytearray([0b01101111, 0x88, 0b11111110]), 'arguments should be in reverse order')

        piF = InstructioParser.parse_instruction(model2, test_line_id, 'mov [sp+label1] , 0x88')
        self.assertEqual(piF.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piF.get_bytes(TestConfigObject.label_values), bytearray([0b01101111, 0x88, 2]), 'arguments should be in reverse order')

        piG = InstructioParser.parse_instruction(model2, test_line_id, 'mov [sp] , 0x88')
        self.assertEqual(piG.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piG.get_bytes(TestConfigObject.label_values), bytearray([0b01101111, 0x88, 0]), 'arguments should be in reverse order')

        piH = InstructioParser.parse_instruction(model2, test_line_id, 'mov [$8000], [label1]')
        self.assertEqual(piH.byte_size, 5, 'assembled instruciton is 5 byte')
        self.assertEqual(piH.get_bytes(TestConfigObject.label_values), bytearray([0b01110110, 2, 0, 0, 0x80]), 'arguments should be in reverse order')

        piI = InstructioParser.parse_instruction(model2, test_line_id, 'mov [mar], [label1]')
        self.assertEqual(piI.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piI.get_bytes(TestConfigObject.label_values), bytearray([0b01100110, 2, 0]), 'no offset should be emitted for [mar]')

        piJ = InstructioParser.parse_instruction(model2, test_line_id, 'swap [$8000], [label1]')
        self.assertEqual(piJ.byte_size, 5, 'assembled instruciton is 3 byte')
        self.assertEqual(piJ.get_bytes(TestConfigObject.label_values), bytearray([0b11110110, 0, 0x80, 2, 0]), 'arguments should NOT be in reverse order')

        piK = InstructioParser.parse_instruction(model2, test_line_id, 'mov [sp+2], [sp+4]')
        self.assertEqual(piK.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piK.get_bytes(TestConfigObject.label_values), bytearray([0b01101101, 4, 2]), 'arguments should be in reverse order')

        piL = InstructioParser.parse_instruction(model2, test_line_id, 'pop i')
        self.assertEqual(piL.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(list(piL.get_bytes(TestConfigObject.label_values)), [0b00001010], 'pop to i')

        piM = InstructioParser.parse_instruction(model2, LineIdentifier(158,'test_pop_empty_arg'), 'pop')
        self.assertEqual(piM.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(piM.get_bytes(TestConfigObject.label_values), bytearray([0b00001111]), 'just pop')

        piN = InstructioParser.parse_instruction(model2, test_line_id, 'mov a, [sp+2]')
        self.assertEqual(piN.byte_size, 2, 'assembled instruciton is 2 byte')
        self.assertEqual(piN.get_bytes(TestConfigObject.label_values), bytearray([0b01000101, 2]), 'just move [sp+2] into a')

        with self.assertRaises(SystemExit, msg='should error on unallowed operand combinations'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a, a')
        with self.assertRaises(SystemExit, msg='[mar] should have no offset'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov [mar+2], [label1]')
        with self.assertRaises(SystemExit, msg='should error due to too many operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a, i, j')
        with self.assertRaises(SystemExit, msg='should error due to too many operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'nop 123')
        with self.assertRaises(SystemExit, msg='should error due to too few operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a')

    def test_bad_registers_in_configuratin(self):
        with pkg_resources.path(config_files, 'test_bad_registers_in_configuratin.yaml') as fp:
            with self.assertRaises(SystemExit, msg='model configuration should not specify prohibited register names'):
                model = AssemblerModel(str(fp), 0)

    def test_min_required_version(self):
        with pkg_resources.path(config_files, 'test_min_required_version_config.yaml') as fp:
            with self.assertRaises(SystemExit, msg='the min version check should fail'):
                model = AssemblerModel(str(fp), 0)

    def test_predefined_entities(self):
        with pkg_resources.path(config_files, 'test_compiler_features.yaml') as fp:
            model = AssemblerModel(str(fp), 0)

        self.assertSetEqual(set(model.predefined_labels), set(['CONST1', 'CONST2', 'buffer']), 'label set should equal')

if __name__ == '__main__':
    unittest.main()