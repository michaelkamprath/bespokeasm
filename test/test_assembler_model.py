import importlib.resources as pkg_resources
import unittest
import yaml

import bespokeasm.assembler.model.operand as A
import bespokeasm.assembler.model.operand_set as AS
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.byte_code.assembled import AssembledInstruction

from test import config_files

#
# Tests
#

class TestConfigObject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._register_argument_config_str = pkg_resources.read_text(config_files, 'register_argument_exmaple_config.yaml')
        cls._eater_sap1_config_str = pkg_resources.read_text(config_files, 'eater-sap1-isa.yaml')

    def test_argument_set_construction(self):
        conf1 = yaml.safe_load(self._eater_sap1_config_str)
        arg_collection1 = AS.OperandSetCollection(conf1['operand_sets'], 'big')
        self.assertEqual(len(arg_collection1),2, 'there are 2 argument sets')
        self.assertTrue('integer' in arg_collection1)
        self.assertTrue('address' in arg_collection1)

        conf2 = yaml.safe_load(self._register_argument_config_str)
        arg_collection2 = AS.OperandSetCollection(conf2['operand_sets'], 'little')
        self.assertEqual(len(arg_collection2),4, 'there are 4 argument sets')
        self.assertTrue('8_bit_source' in arg_collection2)
        self.assertTrue('8_bit_destination' in arg_collection2)
        self.assertTrue('int8' in arg_collection2)
        self.assertTrue('int16' in arg_collection2)

    def test_instruction_parsing(self):
        with pkg_resources.path(config_files, 'eater-sap1-isa.yaml') as fp:
            model1 = AssemblerModel(str(fp))

        label_dict = {
            'label1': 2,
            'LABEL2': 0xF0,
        }

        pi1 = model1.parse_instruction(1212, 'LDA $f')
        self.assertEqual(pi1.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(pi1.get_bytes(label_dict), bytearray([0x1F]), 'assembled instruction')

        pi2 = model1.parse_instruction(1212, 'add label1+5')
        self.assertEqual(pi2.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(pi2.get_bytes(label_dict), bytearray([0x27]), 'assembled instruction')

        pi3 = model1.parse_instruction(1212, 'out')
        self.assertEqual(pi3.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(pi3.get_bytes(label_dict), bytearray([0xE0]), 'assembled instruction')

        with pkg_resources.path(config_files, 'register_argument_exmaple_config.yaml') as fp:
            model2 = AssemblerModel(str(fp))

        piA = model2.parse_instruction(1234, 'mov a, i')
        self.assertEqual(piA.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(piA.get_bytes(label_dict), bytearray([0b01000010]), 'assembled instruction')

        piB = model2.parse_instruction(1234, 'mov a,[$1120 + label1]')
        self.assertEqual(piB.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piB.get_bytes(label_dict), bytearray([0b01000110, 0x22, 0x11]), 'assembled instruction')

        piC = model2.parse_instruction(888, 'add i')
        self.assertEqual(piC.byte_size, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(piC.get_bytes(label_dict), bytearray([0b10111010]), 'assembled instruction')

        piD = model2.parse_instruction(1234, 'mov [$110D + (label1 + LABEL2)] , 0x88')
        self.assertEqual(piD.byte_size, 4, 'assembled instruciton is 4 byte')
        self.assertEqual(piD.get_bytes(label_dict), bytearray([0b01110111,  0x88, 0xFF, 0x11]), 'arguments should be in reverse order')

        piE = model2.parse_instruction(1234, 'mov [sp - label1] , 0x88')
        self.assertEqual(piE.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piE.get_bytes(label_dict), bytearray([0b01101111, 0x88, 0b11111110]), 'arguments should be in reverse order')

        piF = model2.parse_instruction(1234, 'mov [sp+label1] , 0x88')
        self.assertEqual(piF.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piF.get_bytes(label_dict), bytearray([0b01101111, 0x88, 2]), 'arguments should be in reverse order')

        piG = model2.parse_instruction(1234, 'mov [sp] , 0x88')
        self.assertEqual(piG.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piG.get_bytes(label_dict), bytearray([0b01101111, 0x88, 0]), 'arguments should be in reverse order')

        piH = model2.parse_instruction(1234, 'mov [$8000], [label1]')
        self.assertEqual(piH.byte_size, 5, 'assembled instruciton is 5 byte')
        self.assertEqual(piH.get_bytes(label_dict), bytearray([0b01110110, 2, 0, 0, 0x80]), 'arguments should be in reverse order')

        piI = model2.parse_instruction(1234, 'mov [mar], [label1]')
        self.assertEqual(piI.byte_size, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(piI.get_bytes(label_dict), bytearray([0b01100110, 2, 0]), 'no offset should be emitted for [mar]')

        with self.assertRaises(SystemExit, msg='should error on unallowed operand combinations'):
            model2.parse_instruction(1234, 'mov a, a')
        with self.assertRaises(SystemExit, msg='should error on unallowed operand combinations'):
            model2.parse_instruction(1234, 'mov [sp+2], [sp+4]')
        with self.assertRaises(SystemExit, msg='[mar] should have no offset'):
            model2.parse_instruction(1234, 'mov [mar+2], [label1]')

    def test_bad_registers_in_configuratin(self):
         with pkg_resources.path(config_files, 'test_bad_registers_in_configuratin.yaml') as fp:
            with self.assertRaises(SystemExit, msg='model configuration should not specify prohibited register names'):
                model = AssemblerModel(str(fp))

if __name__ == '__main__':
    unittest.main()