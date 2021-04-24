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

if __name__ == '__main__':
    unittest.main()