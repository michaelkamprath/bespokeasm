import unittest

from bespokeasm.assembler.bytecode.word_slice import WordSlice


class TestWordSlice(unittest.TestCase):

    def test_valid_positive_values(self):
        """Test that valid positive values are accepted."""
        # 4-bit: range -8 to 15 (signed -8 to 7, unsigned 0 to 15)
        ws = WordSlice(0, 4)
        self.assertEqual(ws.value, 0)
        self.assertEqual(ws.bit_size, 4)

        ws = WordSlice(7, 4)
        self.assertEqual(ws.value, 7)
        self.assertEqual(ws.bit_size, 4)

        ws = WordSlice(8, 4)   # unsigned
        self.assertEqual(ws.value, 8)
        self.assertEqual(ws.bit_size, 4)

        ws = WordSlice(15, 4)  # unsigned
        self.assertEqual(ws.value, 15)
        self.assertEqual(ws.bit_size, 4)

        # 8-bit: range -128 to 255 (signed -128 to 127, unsigned 0 to 255)
        ws = WordSlice(0, 8)
        self.assertEqual(ws.value, 0)
        self.assertEqual(ws.bit_size, 8)

        ws = WordSlice(127, 8)
        self.assertEqual(ws.value, 127)
        self.assertEqual(ws.bit_size, 8)

        ws = WordSlice(128, 8)  # unsigned
        self.assertEqual(ws.value, 128)
        self.assertEqual(ws.bit_size, 8)

        ws = WordSlice(255, 8)  # unsigned
        self.assertEqual(ws.value, 255)
        self.assertEqual(ws.bit_size, 8)

        # 16-bit: range -32768 to 65535 (signed -32768 to 32767, unsigned 0 to 65535)
        ws = WordSlice(0, 16)
        self.assertEqual(ws.value, 0)
        self.assertEqual(ws.bit_size, 16)

        ws = WordSlice(32767, 16)
        self.assertEqual(ws.value, 32767)
        self.assertEqual(ws.bit_size, 16)

        ws = WordSlice(32768, 16)  # unsigned
        self.assertEqual(ws.value, 32768)
        self.assertEqual(ws.bit_size, 16)

        ws = WordSlice(65535, 16)  # unsigned
        self.assertEqual(ws.value, 65535)
        self.assertEqual(ws.bit_size, 16)

    def test_valid_negative_values(self):
        """Test that valid negative values are accepted."""
        # 4-bit: range -8 to 7
        ws = WordSlice(-8, 4)
        self.assertEqual(ws.value, -8)
        self.assertEqual(ws.bit_size, 4)

        ws = WordSlice(-1, 4)
        self.assertEqual(ws.value, -1)
        self.assertEqual(ws.bit_size, 4)

        # 8-bit: range -128 to 127
        ws = WordSlice(-128, 8)
        self.assertEqual(ws.value, -128)
        self.assertEqual(ws.bit_size, 8)

        ws = WordSlice(-1, 8)
        self.assertEqual(ws.value, -1)
        self.assertEqual(ws.bit_size, 8)

        # 16-bit: range -32768 to 32767
        ws = WordSlice(-32768, 16)
        self.assertEqual(ws.value, -32768)
        self.assertEqual(ws.bit_size, 16)

        ws = WordSlice(-1, 16)
        self.assertEqual(ws.value, -1)
        self.assertEqual(ws.bit_size, 16)

    def test_invalid_positive_values(self):
        """Test that values too large are rejected."""
        # 4-bit: max value is 15
        with self.assertRaises(ValueError):
            WordSlice(16, 4)

        # 8-bit: max value is 255
        with self.assertRaises(ValueError):
            WordSlice(256, 8)

        # 16-bit: max value is 65535
        with self.assertRaises(ValueError):
            WordSlice(65536, 16)

    def test_invalid_negative_values(self):
        """Test that values too small are rejected."""
        # 4-bit: min value is -8
        with self.assertRaises(ValueError):
            WordSlice(-9, 4)

        # 8-bit: min value is -128
        with self.assertRaises(ValueError):
            WordSlice(-129, 8)

        # 16-bit: min value is -32768
        with self.assertRaises(ValueError):
            WordSlice(-32769, 16)

    def test_edge_cases(self):
        """Test edge cases for various bit sizes."""
        # 1-bit: range -1 to 1 (signed -1 to 0, unsigned 0 to 1)
        ws = WordSlice(-1, 1)
        self.assertEqual(ws.value, -1)
        self.assertEqual(ws.bit_size, 1)
        self.assertEqual(ws.get_raw_bits(), 1)

        ws = WordSlice(0, 1)
        self.assertEqual(ws.value, 0)
        self.assertEqual(ws.bit_size, 1)
        self.assertEqual(ws.get_raw_bits(), 0)

        ws = WordSlice(1, 1)  # unsigned
        self.assertEqual(ws.value, 1)
        self.assertEqual(ws.bit_size, 1)
        self.assertEqual(ws.get_raw_bits(), 1)

        with self.assertRaises(ValueError):
            WordSlice(2, 1)
        with self.assertRaises(ValueError):
            WordSlice(-2, 1)

        # 2-bit: range -2 to 3 (signed -2 to 1, unsigned 0 to 3)
        ws = WordSlice(-2, 2)
        self.assertEqual(ws.value, -2)
        self.assertEqual(ws.bit_size, 2)
        self.assertEqual(ws.get_raw_bits(), 2)

        ws = WordSlice(-1, 2)
        self.assertEqual(ws.value, -1)
        self.assertEqual(ws.bit_size, 2)
        self.assertEqual(ws.get_raw_bits(), 3)

        ws = WordSlice(0, 2)
        self.assertEqual(ws.value, 0)
        self.assertEqual(ws.bit_size, 2)
        self.assertEqual(ws.get_raw_bits(), 0)

        ws = WordSlice(1, 2)
        self.assertEqual(ws.value, 1)
        self.assertEqual(ws.bit_size, 2)
        self.assertEqual(ws.get_raw_bits(), 1)

        ws = WordSlice(2, 2)  # unsigned
        self.assertEqual(ws.value, 2)
        self.assertEqual(ws.bit_size, 2)
        self.assertEqual(ws.get_raw_bits(), 2)

        ws = WordSlice(3, 2)  # unsigned
        self.assertEqual(ws.value, 3)
        self.assertEqual(ws.bit_size, 2)
        self.assertEqual(ws.get_raw_bits(), 3)

        with self.assertRaises(ValueError):
            WordSlice(4, 2)
        with self.assertRaises(ValueError):
            WordSlice(-3, 2)

        # 3-bit: range -4 to 7 (signed -4 to 3, unsigned 0 to 7)
        ws = WordSlice(-4, 3)
        self.assertEqual(ws.value, -4)
        self.assertEqual(ws.bit_size, 3)
        self.assertEqual(ws.get_raw_bits(), 4)

        ws = WordSlice(3, 3)
        self.assertEqual(ws.value, 3)
        self.assertEqual(ws.bit_size, 3)
        self.assertEqual(ws.get_raw_bits(), 3)

        ws = WordSlice(4, 3)  # unsigned
        self.assertEqual(ws.value, 4)
        self.assertEqual(ws.bit_size, 3)
        self.assertEqual(ws.get_raw_bits(), 4)

        ws = WordSlice(7, 3)  # unsigned
        self.assertEqual(ws.value, 7)
        self.assertEqual(ws.bit_size, 3)
        self.assertEqual(ws.get_raw_bits(), 7)

        with self.assertRaises(ValueError):
            WordSlice(8, 3)
        with self.assertRaises(ValueError):
            WordSlice(-5, 3)

    def test_zero_bit_size(self):
        """Test that 0-bit slices work correctly as placeholders."""
        # Valid 0-bit slice
        zero_slice = WordSlice(0, 0)
        self.assertEqual(zero_slice.value, 0)
        self.assertEqual(zero_slice.bit_size, 0)

        # Invalid 0-bit slice (non-zero value)
        with self.assertRaises(ValueError):
            WordSlice(1, 0)

        with self.assertRaises(ValueError):
            WordSlice(-1, 0)

    def test_invalid_bit_size(self):
        """Test that invalid bit sizes are rejected."""
        with self.assertRaises(ValueError):
            WordSlice(0, -1)

    def test_properties(self):
        """Test that properties return correct values."""
        slice_4bit = WordSlice(-5, 4)
        self.assertEqual(slice_4bit.value, -5)
        self.assertEqual(slice_4bit.bit_size, 4)

        slice_8bit = WordSlice(100, 8)
        self.assertEqual(slice_8bit.value, 100)
        self.assertEqual(slice_8bit.bit_size, 8)

    def test_equality(self):
        """Test equality comparison."""
        slice1 = WordSlice(5, 4)
        slice2 = WordSlice(5, 4)
        slice3 = WordSlice(5, 8)
        slice4 = WordSlice(6, 4)

        self.assertEqual(slice1, slice2)
        self.assertNotEqual(slice1, slice3)
        self.assertNotEqual(slice1, slice4)
        self.assertNotEqual(slice1, 'not a WordSlice')

        # Test 0-bit slices
        zero1 = WordSlice(0, 0)
        zero2 = WordSlice(0, 0)
        self.assertEqual(zero1, zero2)
        self.assertNotEqual(zero1, slice1)

    def test_hash(self):
        """Test that WordSlice objects are hashable."""
        slice1 = WordSlice(5, 4)
        slice2 = WordSlice(5, 4)
        slice3 = WordSlice(5, 8)

        # Same objects should have same hash
        self.assertEqual(hash(slice1), hash(slice2))

        # Different objects should have different hashes
        self.assertNotEqual(hash(slice1), hash(slice3))

        # Should be able to use in sets
        word_slice_set = {slice1, slice2, slice3}
        self.assertEqual(len(word_slice_set), 2)  # slice1 and slice2 are equal

        # Test 0-bit slices
        zero1 = WordSlice(0, 0)
        zero2 = WordSlice(0, 0)
        self.assertEqual(hash(zero1), hash(zero2))

        # 0-bit slices should be distinct from other slices
        word_slice_set_with_zero = {slice1, zero1, zero2}
        self.assertEqual(len(word_slice_set_with_zero), 2)  # slice1 and zero1 (zero2 equals zero1)

    def test_get_raw_bits(self):
        """Test raw bits retrieval."""
        # 0-bit slices
        ws = WordSlice(0, 0)
        self.assertEqual(ws.get_raw_bits(), 0)

        # 1-bit slices
        ws = WordSlice(0, 1)
        self.assertEqual(ws.get_raw_bits(), 0)
        ws = WordSlice(1, 1)
        self.assertEqual(ws.get_raw_bits(), 1)
        ws = WordSlice(-1, 1)
        self.assertEqual(ws.get_raw_bits(), 1)  # two's complement: 1

        # 2-bit slices
        ws = WordSlice(0, 2)
        self.assertEqual(ws.get_raw_bits(), 0)
        ws = WordSlice(1, 2)
        self.assertEqual(ws.get_raw_bits(), 1)
        ws = WordSlice(2, 2)
        self.assertEqual(ws.get_raw_bits(), 2)
        ws = WordSlice(3, 2)
        self.assertEqual(ws.get_raw_bits(), 3)
        ws = WordSlice(-1, 2)
        self.assertEqual(ws.get_raw_bits(), 3)  # two's complement: 11
        ws = WordSlice(-2, 2)
        self.assertEqual(ws.get_raw_bits(), 2)  # two's complement: 10

        # 4-bit slices
        ws = WordSlice(5, 4)
        self.assertEqual(ws.get_raw_bits(), 5)  # 0101
        ws = WordSlice(10, 4)
        self.assertEqual(ws.get_raw_bits(), 10)  # 1010
        ws = WordSlice(-1, 4)
        self.assertEqual(ws.get_raw_bits(), 15)  # two's complement: 1111
        ws = WordSlice(-5, 4)
        self.assertEqual(ws.get_raw_bits(), 11)  # two's complement: 1011
        ws = WordSlice(-8, 4)
        self.assertEqual(ws.get_raw_bits(), 8)   # two's complement: 1000

        # 8-bit slices
        ws = WordSlice(100, 8)
        self.assertEqual(ws.get_raw_bits(), 100)
        ws = WordSlice(255, 8)
        self.assertEqual(ws.get_raw_bits(), 255)
        ws = WordSlice(-1, 8)
        self.assertEqual(ws.get_raw_bits(), 255)  # two's complement: 11111111
        ws = WordSlice(-128, 8)
        self.assertEqual(ws.get_raw_bits(), 128)  # two's complement: 10000000

        # Test masking behavior for values that are at the boundary
        ws = WordSlice(15, 4)  # 15 in 4 bits (max unsigned value)
        self.assertEqual(ws.get_raw_bits(), 15)
        ws = WordSlice(255, 8)  # 255 in 8 bits (max unsigned value)
        self.assertEqual(ws.get_raw_bits(), 255)

    def test_string_representations(self):
        """Test string representations."""
        slice_obj = WordSlice(-5, 4)

        # __repr__ should show hex value
        self.assertIn('0x', repr(slice_obj))
        self.assertIn('4', repr(slice_obj))

        # __str__ should be readable
        str_repr = str(slice_obj)
        self.assertIn('-5', str_repr)
        self.assertIn('4', str_repr)
        self.assertIn('bits', str_repr)

        # Test 0-bit slice string representations
        zero_slice = WordSlice(0, 0)
        self.assertIn('0x', repr(zero_slice))
        self.assertIn('0', repr(zero_slice))
        str_zero = str(zero_slice)
        self.assertIn('0', str_zero)
        self.assertIn('0 bits', str_zero)


if __name__ == '__main__':
    unittest.main()
