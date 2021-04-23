import unittest

from bespokeasm.utilities import parse_numeric_string

class TestUtilities(unittest.TestCase):

    def test_parse_numeric_string(self):
        self.assertEqual(parse_numeric_string("1234"), 1234, "straight integer test: 1234")
        self.assertEqual(parse_numeric_string("$4d2"), 1234, "$hex integer test: 1234")
        self.assertEqual(parse_numeric_string("0x4d2"), 1234, "0x hex integer test: 1234")
        self.assertEqual(parse_numeric_string("b0000010011010010"), 1234, "binary integer test: 1234")
        self.assertEqual(parse_numeric_string("-1212"), -1212, "signed interger: -1212")


if __name__ == '__main__':
    unittest.main()