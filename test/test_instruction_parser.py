import unittest

import bespokeasm
from bespokeasm.instruction_parser import MachineCodePart
from bespokeasm.packed_bits import PackedBits

instruction_model = {
    'address_size': 4,
    'instructions': [
        {
            'prefix': 'lda',
            'arguments': [
                {
                    'type': 'address',
                    'byte_align': False,
                }
            ],
            'bits': {
                'value': 1,
                'size': 4,
            }
        },
        {
            'prefix': 'add',
            'arguments': [
                {
                    'type': 'address',
                    'byte_align': False,
                }
            ],
            'bits': {
                'value': 2,
                'size': 4,
            }
        },
    ],
 }


class TestInstructionParser(unittest.TestCase):
    def test_PackedBits(self):
        ib1 = PackedBits()
        ib1.append_bits(0xd,4,False)
        ib1.append_bits(0xe,4,False)
        ib1.append_bits(0xad,8,False)
        self.assertEqual(ib1.get_bytes(), bytearray([0xde,0xad]))

        ib2 = PackedBits()
        ib2.append_bits(0xd,4,False)
        ib2.append_bits(0xe,4, byte_aligned=True)
        ib2.append_bits(0xad,8, byte_aligned=True)
        self.assertEqual(ib2.get_bytes(), bytearray([0xd0, 0xe0,0xad]))

        ib3 = PackedBits()
        ib3.append_bits(0x3,2,False)
        ib3.append_bits(0x5,3,False)
        ib3.append_bits(0xf,4, byte_aligned=True)
        self.assertEqual(ib3.get_bytes(), bytearray([0xe8, 0xf0]))

        ib4 = PackedBits()
        ib4.append_bits(0x1,4,False)
        ib4.append_bits(0xDEAD,16, byte_aligned=True)
        self.assertEqual(ib4.get_bytes(), bytearray([0x10, 0xde, 0xad]))

    def test_parse_instruction(self):
        test_str1 = 'LDA 0xA'
        parts_list1 = bespokeasm.instruction_parser.parse_instruction(test_str1, instruction_model)

        expected_list1 = [
            MachineCodePart('LDA', None, 1, 4, True),
            MachineCodePart('0xA', None, 10, 4, False),
        ]

        self.assertEqual(len(parts_list1), len(expected_list1), "results are expected size")
        self.assertEqual(parts_list1[0], expected_list1[0], "first element is the same")
        self.assertEqual(parts_list1[1], expected_list1[1], "second element is the same")

        test_str2 = 'add const_value'
        parts_list2 = bespokeasm.instruction_parser.parse_instruction(test_str2, instruction_model)
        expected_list2 = [
            MachineCodePart('ADD', None, 2, 4, True),
            MachineCodePart('const_value', 'const_value', None, 4, False),
        ]
        self.assertEqual(len(parts_list2), len(expected_list2), "results are expected size")
        self.assertEqual(parts_list2[0], expected_list2[0], "first element is the same")
        self.assertEqual(parts_list2[1], expected_list2[1], "second element is the same")


    def test_calc_byte_size_for_parts(self):
        parts_list1 = [
            MachineCodePart('LDA', None, 1, 4, True),
            MachineCodePart('0xA', None, 10, 4, False),
        ]
        self.assertEqual(
            bespokeasm.instruction_parser.calc_byte_size_for_parts(parts_list1),
            1,
            "instruction part byte size"
        )

        parts_list2 = [
            MachineCodePart('LDA', None, 1, 4, True),
            MachineCodePart('0xA', None, 10, 4, True),
        ]
        self.assertEqual(
            bespokeasm.instruction_parser.calc_byte_size_for_parts(parts_list2),
            2,
            "instruction part byte size"
        )

        parts_list3 = [
            MachineCodePart('TEST', None, 15, 4, True),
            MachineCodePart('0xFF', None, 255, 8, False),
            MachineCodePart('0x88', None, 136, 8, False),
       ]
        self.assertEqual(
            bespokeasm.instruction_parser.calc_byte_size_for_parts(parts_list3),
            3,
            f'instruction part byte size for {parts_list3}'
        )

if __name__ == '__main__':
    unittest.main()