import unittest

from bespokeasm.utilities import parse_numeric_string, is_string_numeric
from bespokeasm.packed_bits import PackedBits

class TestUtilities(unittest.TestCase):

    def test_parse_numeric_string(self):
        self.assertEqual(parse_numeric_string('1234'), 1234, 'straight integer test: 1234')
        self.assertEqual(parse_numeric_string('$4d2'), 1234, '$hex integer test: 1234')
        self.assertEqual(parse_numeric_string('0x4d2'), 1234, '0x hex integer test: 1234')
        self.assertEqual(parse_numeric_string('b0000010011010010'), 1234, 'binary integer test: 1234')
        self.assertEqual(parse_numeric_string('-1212'), -1212, 'signed interger: -1212')

    def test_is_string_numeric(self):
        self.assertTrue(is_string_numeric('8675309'), 'string is numeric')
        self.assertTrue(is_string_numeric('0x845FED'), 'string is numeric')
        self.assertTrue(is_string_numeric('$845FED'), 'string is numeric')
        self.assertTrue(is_string_numeric('b10000100111111101101'), 'string is numeric')
        self.assertFalse(is_string_numeric('Jenny'), 'string is not numeric')
        self.assertFalse(is_string_numeric('test1'), 'string is not numeric')
        self.assertFalse(is_string_numeric(' '), 'string is not numeric')

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

if __name__ == '__main__':
    unittest.main()