import unittest

from bespokeasm.line_parser import LineParser, LineType

class TestLineParser(unittest.TestCase):
    def test_parser_creation(self):
        lp1 = LineParser('.test_label:    ; my comments', 27)
        self.assertEqual(lp1.label_name, '.test_label')
        self.assertEqual(lp1.label_value, None)
        self.assertEqual(lp1.line_num, 27)

if __name__ == '__main__':
    unittest.main()