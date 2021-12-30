import unittest
import importlib.resources as pkg_resources

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType, GlobalLabelScope
from bespokeasm.assembler.line_object import LineObject, LineWithBytes
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.assembler.line_object.label_line import LabelLine, is_valid_label
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel

from test import config_files

class TestLineObject(unittest.TestCase):

    def test_data_line_creation(self):
        label_values = GlobalLabelScope(set())
        label_values.set_label_value('test1', 0x1234, 1)

        d1 = DataLine.factory(27, ' .byte $de, $ad, 0xbe, $ef', 'steak', 'big')
        d1.label_scope = label_values
        d1.generate_bytes()
        self.assertIsInstance(d1, DataLine)
        self.assertEqual(d1.byte_size, 4, 'data line has 4 bytes')
        self.assertEqual(d1.get_bytes(), bytearray([0xde, 0xad, 0xbe, 0xef]), '$deadbeef')

        d2 = DataLine.factory(38, ' .byte test1, 12', 'label mania', 'big')
        d2.label_scope = label_values
        d2.generate_bytes()
        self.assertIsInstance(d2, DataLine)
        self.assertEqual(d2.byte_size, 2, 'data line has 2 bytes')
        self.assertEqual(d2.get_bytes(), bytearray([0x34, 12]), 'should slice first byte')

        d3 = DataLine.factory(38, ' .byte test1, , 12', 'label mania', 'big')
        d3.label_scope = label_values
        d3.generate_bytes()
        self.assertIsInstance(d3, DataLine)
        self.assertEqual(d3.byte_size, 2, 'data line has 2 bytes, ignore bad argument')
        self.assertEqual(d3.get_bytes(), bytearray([0x34, 12]), 'should slice first byte, ignore bad argument')

        d4 = DataLine.factory(38, ' .byte b1110', 'label mania', 'big')
        d4.label_scope = label_values
        d4.generate_bytes()
        self.assertIsInstance(d4, DataLine)
        self.assertEqual(d4.byte_size, 1, 'data line has 1 bytes')
        self.assertEqual(d4.get_bytes(), bytearray([0x0E]), 'onsie')

        test_str = 'that\'s a test'
        d5_values = [ord(c) for c in test_str]
        d5 = DataLine.factory(42, f' .byte "{test_str}"', 'string of bytes', 'big')
        d5.label_scope = label_values
        d5.generate_bytes()
        self.assertIsInstance(d5, DataLine)
        self.assertEqual(d5.byte_size, 13, 'byte string has 13 bytes')
        self.assertEqual(d5.get_bytes(), bytearray(d5_values), 'character string matches')

        d5a_values = [ord(c) for c in test_str]
        d5a_values.extend([0])
        d5a = DataLine.factory(42, f' .cstr "{test_str}"', 'string of bytes', 'big')
        d5a.label_scope = label_values
        d5a.generate_bytes()
        self.assertIsInstance(d5a, DataLine)
        self.assertEqual(d5a.byte_size, 14, 'character string has 14 bytes')
        self.assertEqual(d5a.get_bytes(), bytearray(d5a_values), 'character string matches')

        d6 = DataLine.factory(38, ' .2byte test1, 12', '2 byte label mania', 'little')
        d6.label_scope = label_values
        d6.generate_bytes()
        self.assertIsInstance(d6, DataLine)
        self.assertEqual(d6.byte_size, 4, 'data line has 4 bytes')
        self.assertEqual(d6.get_bytes(), bytearray([0x34, 0x12, 12, 0]), 'should slice first two bytes')

        d7 = DataLine.factory(38, '.4byte %11110111011001010100001100100001, $1945', '4 byte label mania', 'little')
        d7.label_scope = label_values
        d7.generate_bytes()
        self.assertIsInstance(d7, DataLine)
        self.assertEqual(d7.byte_size, 8, 'data line has 8 bytes')
        self.assertEqual(d7.get_bytes(), bytearray([0x21, 0x43, 0x65, 0xf7, 0x45, 0x19, 0, 0]), 'should have each 4 byte numbe in litle endian')

        d8 = DataLine.factory(38, '.4byte %11110111011001010100001100100001, $1945', '4 byte label mania', 'big')
        d8.label_scope = label_values
        d8.generate_bytes()
        self.assertIsInstance(d8, DataLine)
        self.assertEqual(d8.byte_size, 8, 'data line has 8 bytes')
        self.assertEqual(d8.get_bytes(), bytearray([0xf7, 0x65, 0x43, 0x21, 0, 0, 0x19, 0x45]), 'should have each 4 byte numbe in big endian')

        d9 = DataLine.factory(38, '.4byte 0x0123456789abcdef', 'data masked!', 'little')
        d9.label_scope = label_values
        d9.generate_bytes()
        self.assertIsInstance(d9, DataLine)
        self.assertEqual(d9.byte_size, 4, 'data line has 4 bytes')
        self.assertEqual(d9.get_bytes(), bytearray([0xef, 0xcd, 0xab, 0x89]), 'should slice first four bytes')

        #ensure spaces in strings aren't truncated
        test_str2 = ' space '
        d10_values = [ord(c) for c in test_str2]
        d10 = DataLine.factory(42, f' .byte "{test_str2}"', 'string of bytes', 'big')
        d10.label_scope = label_values
        d10.generate_bytes()
        self.assertIsInstance(d10, DataLine)
        self.assertEqual(d10.byte_size, 7, 'byte string has 7 bytes')
        self.assertEqual(d10.get_bytes(), bytearray(d10_values), 'character string matches')

    def test_label_line_creation(self):
        register_set = set(['a', 'b', 'sp', 'mar'])
        l1 = LabelLine.factory(13, 'my_label:', 'cool comment', register_set)
        l1.set_start_address(1212)
        self.assertIsInstance(l1, LabelLine)
        self.assertEqual(l1.byte_size, 0, 'has no bytes')
        self.assertEqual(l1.get_value(), 1212, 'label value is address')
        self.assertEqual(l1.address, 1212, 'address value is address')
        self.assertEqual(l1.get_label(),'my_label', 'label string')

        l2 = LabelLine.factory(13, 'my_constant = 1945', 'cool comment', register_set)
        l2.set_start_address(1212)
        self.assertIsInstance(l2, LabelLine)
        self.assertEqual(l2.byte_size, 0, 'has no bytes')
        self.assertEqual(l2.get_value(), 1945, 'constant value is assigned')
        self.assertEqual(l2.address, 1212, 'address value is address')
        self.assertEqual(l2.get_label(),'my_constant', 'label string')

        l3 = LabelLine.factory(13, 'myLabelIsCool:', 'cool comment', register_set)
        l3.set_start_address(2001)
        self.assertIsInstance(l3, LabelLine)
        self.assertEqual(l3.byte_size, 0, 'has no bytes')
        self.assertEqual(l3.get_value(), 2001, 'label value is address')
        self.assertEqual(l3.address, 2001, 'address value is address')
        self.assertEqual(l3.get_label(),'myLabelIsCool', 'label string')

        # this should fail
        with self.assertRaises(SystemExit, msg='non-numeric constant assignments should fail'):
            l_fail= LabelLine.factory(13, 'my_constant = some_string', 'bad constant', register_set)

        with self.assertRaises(SystemExit, msg='labels should not be registers'):
            l_fail = LabelLine.factory(13, 'mar = $1234', 'bad label', register_set)
        with self.assertRaises(SystemExit, msg='labels should not be registers'):
            l_fail = LabelLine.factory(13, 'sp:', 'bad label', register_set)

    def test_valid_labels(self):
        self.assertTrue(is_valid_label('a_str'),'valid label')
        self.assertTrue(is_valid_label('a_str_with_123'),'valid label')
        self.assertTrue(is_valid_label('.start_with_dot'),'valid label')
        self.assertTrue(is_valid_label('_start_with_line'),'valid label')

        self.assertFalse(is_valid_label('12_monkeys'),'valid label')
        self.assertFalse(is_valid_label('8675309'),'invalid label: only numbers')
        self.assertFalse(is_valid_label('m+g'),'invalid label: operators')
        self.assertFalse(is_valid_label('final frontier'),'invalid label: contains space')

    def test_instruction_line_creation(self):
        with pkg_resources.path(config_files, 'test_instruction_list_creation_isa.json') as fp:
            isa_model = AssemblerModel(str(fp), 0)

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('test1', 0xA, 1)
        label_values.set_label_value('high_de', 0xde00, 1)

        ins1 = InstructionLine.factory(22, '  lda test1', 'some comment!', isa_model)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 1, 'has 1 byte')
        ins1.label_scope = label_values
        ins1.generate_bytes()
        self.assertEqual(ins1.get_bytes(), bytearray([0x1a]), 'instruction should match')

        ins2 = InstructionLine.factory(22, '  hlt', 'stop it!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 1, 'has 1 byte')
        ins2.label_scope = label_values
        ins2.generate_bytes()
        self.assertEqual(ins2.get_bytes(), bytearray([0xF0]), 'instruction should match')

        ins3 = InstructionLine.factory(22, '  seta (high_de + $00AD)', 'is it alive?', isa_model)
        ins3.set_start_address(1313)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 3, 'has 3 bytes')
        ins3.label_scope = label_values
        ins3.generate_bytes()
        self.assertEqual(ins3.get_bytes(), bytearray([0x30, 0xAD, 0xDE]), 'instruction should match')

        ins4 = InstructionLine.factory(22, '  lda test1+2', 'load it', isa_model)
        ins4.set_start_address(1313)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.byte_size, 1, 'has 1 byte')
        ins4.label_scope = label_values
        ins4.generate_bytes()
        self.assertEqual(ins4.get_bytes(), bytearray([0x1c]), 'instruction should match')

        ins5 = InstructionLine.factory(22, '  plus 8', 'plus it', isa_model)
        ins5.set_start_address(888)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.byte_size, 2, 'has 2 bytes')
        ins5.label_scope = label_values
        ins5.generate_bytes()
        self.assertEqual(ins5.get_bytes(), bytearray([0x40, 0x08]), 'instruction should match')

        ins6 = InstructionLine.factory(22, '  lda test1-2', 'load it', isa_model)
        ins6.set_start_address(888)
        self.assertIsInstance(ins6, InstructionLine)
        self.assertEqual(ins6.byte_size, 1, 'has 1 byte1')
        ins6.label_scope = label_values
        ins6.generate_bytes()
        self.assertEqual(ins6.get_bytes(), bytearray([0x18]), 'instruction should match')

    def test_bad_instruction_lines(self):
        with pkg_resources.path(config_files, 'register_argument_exmaple_config.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        label_values = GlobalLabelScope(isa_model.registers)

        # this instruction should fail because register A is not configured to be an
        # indirect register, so the parser assumes this is a indirect numeric expression
        # and then sees a register used there.
        with self.assertRaises(SystemExit, msg='this instruction should fail'):
            InstructionLine.factory(22, '  mov [a+2],5', 'move it', isa_model)

        # this instruction should fail because register i is being used in a numeric
        # expression
        with self.assertRaises(SystemExit, msg='this instruction should fail'):
            InstructionLine.factory(22, '  add i+5', 'add it', isa_model)

    def test_instruction_line_creation_little_endian(self):
        with pkg_resources.path(config_files, 'test_instruction_line_creation_little_endian.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('test1', 0xABCD, 1)

        ins1 = InstructionLine.factory(22, '  lda test1', 'some comment!', isa_model)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 3, 'has 3 byte')
        ins1.label_scope = label_values
        ins1.generate_bytes()
        self.assertEqual(ins1.get_bytes(), bytearray([0x10, 0xCD, 0xAB]), 'instruction should match')

        ins2 = InstructionLine.factory(22, 'set test1', 'set it!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 3, 'has 3 byte')
        ins2.label_scope = label_values
        ins2.generate_bytes()
        self.assertEqual(ins2.get_bytes(), bytearray([0x30, 0xAB, 0xCD]), 'instruction should match')

        ins3 = InstructionLine.factory(22, 'big $f', 'big money', isa_model)
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 2, 'has 2 byte')
        ins3.label_scope = label_values
        ins3.generate_bytes()
        self.assertEqual(ins3.get_bytes(), bytearray([0xFF, 0x3C]), 'instruction should match')

    def test_specifc_configured_operands(self):
        with pkg_resources.path(config_files, 'register_argument_exmaple_config.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('test1', 0xABCD, 1)

        ins1 = InstructionLine.factory(22, 'mov i,[mar]', 'specific operands', isa_model)
        ins1.set_start_address(1234)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 1, 'has 1 byte')
        ins1.label_scope = label_values
        ins1.generate_bytes()
        self.assertEqual(ins1.get_bytes(), bytearray([0x52]), 'instruction should match')

        ins2 = InstructionLine.factory(22, 'mov [sp+8],[mar]', 'specific operands', isa_model)
        ins2.set_start_address(1234)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 2, 'has 2 byte')
        ins2.label_scope = label_values
        ins2.generate_bytes()
        self.assertEqual(ins2.get_bytes(), bytearray([0x6D, 0x08]), 'instruction should match')

        # ensure operand sets operands still work when instruction has specific operands configured
        ins3 = InstructionLine.factory(22, 'mov a,[sp+8]', 'specific operands', isa_model)
        ins3.set_start_address(1234)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 2, 'has 2 byte')
        ins3.label_scope = label_values
        ins3.generate_bytes()
        self.assertEqual(ins3.get_bytes(), bytearray([0x45, 0x08]), 'instruction should match')


if __name__ == '__main__':
    unittest.main()