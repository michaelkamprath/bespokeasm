import unittest

from bespokeasm.line_parser import LineParser, LineType

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
            'prefix': 'jmp',
            'arguments': [
                {
                    'type': 'address',
                    'byte_align': False,
                }
            ],
            'bits': {
                'value': 6,
                'size': 4,
            }
        },
    ],
 }

class TestLineParser(unittest.TestCase):
    def test_parser_creation(self):
        lp1 = LineParser('.test_label:    ; my comments', 27, instruction_model)
        self.assertEqual(lp1.label_name, '.test_label')
        self.assertEqual(lp1.label_value, None)
        self.assertEqual(lp1.line_num, 27)

    def test_byte_code_generation(self):
        label_dict = {'test1':15}

        lp1 = LineParser(' .byte $ff   ; my comments', 33, instruction_model)
        self.assertEqual(lp1.get_bytes(label_dict), bytearray([255]))
        self.assertEqual(lp1.byte_size(), 1, '.byte data is 1 byte')

        lp2 = LineParser(' jmp test1   ; my comments', 33, instruction_model)
        self.assertEqual(lp2.get_bytes(label_dict), bytearray([0x6F]))
        self.assertEqual(lp2.byte_size(), 1, 'test nstruction is 1 byte')


if __name__ == '__main__':
    unittest.main()