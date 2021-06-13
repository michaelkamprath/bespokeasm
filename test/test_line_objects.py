import sys
import unittest

from bespokeasm.line_object import LineObject, LineWithBytes
from bespokeasm.line_object.data_line import DataLine
from bespokeasm.line_object.label_line import LabelLine
from bespokeasm.line_object.instruction_line import InstructionLine, MachineCodePart

class TestLineObject(unittest.TestCase):

    def test_data_line_creation(self):
        LABEL_DICT = {'test1': 0x1234}

        d1 = DataLine.factory(27, ' .byte $de, $ad, 0xbe, $ef', 'steak')
        d1.generate_bytes(LABEL_DICT)
        self.assertIsInstance(d1, DataLine)
        self.assertEqual(d1.byte_size(), 4, 'data line has 4 bytes')
        self.assertEqual(d1.get_bytes(), bytearray([0xde, 0xad, 0xbe, 0xef]), '$deadbeef')

        d2 = DataLine.factory(38, ' .byte test1, 12', 'label mania')
        d2.generate_bytes(LABEL_DICT)
        self.assertIsInstance(d2, DataLine)
        self.assertEqual(d2.byte_size(), 2, 'data line has 2 bytes')
        self.assertEqual(d2.get_bytes(), bytearray([0x34, 12]), 'should slice first byte')

        d3 = DataLine.factory(38, ' .byte test1, , 12', 'label mania')
        d3.generate_bytes(LABEL_DICT)
        self.assertIsInstance(d3, DataLine)
        self.assertEqual(d3.byte_size(), 2, 'data line has 2 bytes, ignore bad argument')
        self.assertEqual(d3.get_bytes(), bytearray([0x34, 12]), 'should slice first byte, ignore bad argument')

        d4 = DataLine.factory(38, ' .byte b1110', 'label mania')
        d4.generate_bytes(LABEL_DICT)
        self.assertIsInstance(d4, DataLine)
        self.assertEqual(d4.byte_size(), 1, 'data line has 1 bytes')
        self.assertEqual(d4.get_bytes(), bytearray([0x0E]), 'onsie')

        d5_values = [ord(c) for c in 'that\'s a test']
        d5_values.extend([0])
        d5 = DataLine.factory(42, ' .byte "that\'s a test"', 'string of bytes')
        d5.generate_bytes(LABEL_DICT)
        self.assertIsInstance(d5, DataLine)
        self.assertEqual(d5.byte_size(), 14, 'character string has 14 bytes')
        self.assertEqual(d5.get_bytes(), bytearray(d5_values), 'character string matches')

    def test_label_line_creation(self):
        l1 = LabelLine.factory(13, 'my_label:', 'cool comment')
        l1.set_start_address(1212)
        self.assertIsInstance(l1, LabelLine)
        self.assertEqual(l1.byte_size(), 0, 'has no bytes')
        self.assertEqual(l1.get_value(), 1212, 'label value is address')
        self.assertEqual(l1.address(), 1212, 'address value is address')
        self.assertEqual(l1.get_label(),'my_label', 'label string')

        l2 = LabelLine.factory(13, 'my_constant = 1945', 'cool comment')
        l2.set_start_address(1212)
        self.assertIsInstance(l2, LabelLine)
        self.assertEqual(l2.byte_size(), 0, 'has no bytes')
        self.assertEqual(l2.get_value(), 1945, 'constant value is assigned')
        self.assertEqual(l2.address(), 1212, 'address value is address')
        self.assertEqual(l2.get_label(),'my_constant', 'label string')

        # this should fail
        with self.assertRaises(SystemExit, msg='non-numeric constant assignments should fail'):
            l3 = LabelLine.factory(13, 'my_constant = some_string', 'bad constant')

    def test_instruction_line_creation(self):
        isa_model = {
            'general' : {
                'endian': 'big'
            },
            'argument_config': {
                '1byte_value': {
                    'type': 'numeric',
                    'byte_align': True,
                    'bit_size': 8
                },
                'address': {
                    'type': 'numeric',
                    'byte_align': False,
                    'bit_size': 4
                }
            },
            'instructions': {
                'lda': {
                    'arguments': [
                        'address'
                    ],
                    'byte_code': {
                        'value': 1,
                        'size': 4,
                    }
                },
                'add': {
                    'arguments': [
                        'address'
                    ],
                    'byte_code': {
                        'value': 2,
                        'size': 4,
                    }
                },
                'hlt': {
                    'byte_code': {
                        'value': 15,
                        'size': 4,
                    }
                },
           },
        }
        LABEL_DICT = {'test1': 0xA}

        ins1 = InstructionLine.factory(22, '  lda test1', 'some comment!', isa_model)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size(), 1, 'has 1 byte')
        ins1.generate_bytes(LABEL_DICT)
        self.assertEqual(ins1.get_bytes(), bytearray([0x1a]), 'instruction should match')

        ins2 = InstructionLine.factory(22, '  hlt', 'stop it!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size(), 1, 'has 1 byte')
        ins2.generate_bytes(LABEL_DICT)
        self.assertEqual(ins2.get_bytes(), bytearray([0xF0]), 'instruction should match')

    def test_instruction_line_creation_little_endian(self):
        isa_model = {
            'general' : {
                'endian': 'little'
            },
            'argument_config': {
                '2byte_value': {
                    'type': 'numeric',
                    'byte_align': True,
                    'bit_size': 16,
                    'endian': 'big'
                },
                'address': {
                    'type': 'numeric',
                    'byte_align': True,
                    'bit_size': 16
                }
            },
            'instructions': {
                'lda': {
                    'arguments': [
                        'address'
                    ],
                    'byte_code': {
                        'value': 1,
                        'size': 4,
                    }
                },
                'add': {
                    'arguments': [
                        'address'
                    ],
                    'byte_code': {
                        'value': 2,
                        'size': 4,
                    }
                },
                'set': {
                    'arguments': [
                        '2byte_value'
                    ],
                    'byte_code': {
                        'value': 3,
                        'size': 4,
                    }
                },
                'hlt': {
                    'arguments': [
                    ],
                    'byte_code': {
                        'value': 15,
                        'size': 4,
                    }
                },
           },
        }
        LABEL_DICT = {'test1': 0xABCD}
        ins1 = InstructionLine.factory(22, '  lda test1', 'some comment!', isa_model)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size(), 3, 'has 3 byte')
        ins1.generate_bytes(LABEL_DICT)
        self.assertEqual(ins1.get_bytes(), bytearray([0x10, 0xCD, 0xAB]), 'instruction should match')

        ins2 = InstructionLine.factory(22, 'set test1', 'set it!', isa_model)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size(), 3, 'has 3 byte')
        ins2.generate_bytes(LABEL_DICT)
        self.assertEqual(ins2.get_bytes(), bytearray([0x30, 0xAB, 0xCD]), 'instruction should match')

    def test_calc_byte_size_for_parts(self):
        parts_list1 = [
            MachineCodePart('LDA', None, 1, 4, True, 'big'),
            MachineCodePart('0xA', None, 10, 4, False, 'big'),
        ]
        self.assertEqual(
            InstructionLine._calc_byte_size_for_parts(parts_list1),
            1,
            "instruction part byte size"
        )

        parts_list2 = [
            MachineCodePart('LDA', None, 1, 4, True, 'big'),
            MachineCodePart('0xA', None, 10, 4, True, 'big'),
        ]
        self.assertEqual(
            InstructionLine._calc_byte_size_for_parts(parts_list2),
            2,
            "instruction part byte size"
        )

        parts_list3 = [
            MachineCodePart('TEST', None, 15, 4, True, 'big'),
            MachineCodePart('0xFF', None, 255, 8, False, 'big'),
            MachineCodePart('0x88', None, 136, 8, False, 'big'),
        ]
        self.assertEqual(
            InstructionLine._calc_byte_size_for_parts(parts_list3),
            3,
            f'instruction part byte size for {parts_list3}'
        )

if __name__ == '__main__':
    unittest.main()