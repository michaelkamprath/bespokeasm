import unittest

from bespokeasm.assembler.bytecode.value import Value
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.bytecode.word_slice import WordSlice


class TestValue(unittest.TestCase):

    def test_construction_basic(self):
        """Test basic Value construction."""
        # 32-bit value in 8-bit words
        value = Value(0x01234567, word_bit_size=8)
        self.assertEqual(value.value, 0x01234567)
        self.assertEqual(value.word_bit_size, 8)
        self.assertEqual(value.segment_size, 8)  # default
        self.assertEqual(value.intra_word_endianness, 'big')  # default
        self.assertEqual(value.multi_word_endianness, 'big')  # default
        self.assertEqual(value.word_count, 4)

        # Check the generated words
        words = value.words
        self.assertEqual(len(words), 4)
        self.assertEqual(words[0].value, 0x01)
        self.assertEqual(words[1].value, 0x23)
        self.assertEqual(words[2].value, 0x45)
        self.assertEqual(words[3].value, 0x67)

    def test_construction_with_custom_params(self):
        """Test Value construction with custom parameters."""
        value = Value(
            0x12345678,
            word_bit_size=16,
            segment_size=4,
            intra_word_endianness='little',
            multi_word_endianness='little'
        )

        self.assertEqual(value.value, 0x12345678)
        self.assertEqual(value.word_bit_size, 16)
        self.assertEqual(value.segment_size, 4)
        self.assertEqual(value.intra_word_endianness, 'little')
        self.assertEqual(value.multi_word_endianness, 'little')
        self.assertEqual(value.word_count, 2)

        # Check the generated words
        words = value.words
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].value, 0x1234)
        self.assertEqual(words[1].value, 0x5678)

    def test_construction_validation(self):
        """Test validation of Value construction parameters."""
        # Invalid word_bit_size
        with self.assertRaises(ValueError):
            Value(0, word_bit_size=0)

        with self.assertRaises(ValueError):
            Value(0, word_bit_size=-1)

        # Invalid segment_size
        with self.assertRaises(ValueError):
            Value(0, word_bit_size=8, segment_size=0)

        with self.assertRaises(ValueError):
            Value(0, word_bit_size=8, segment_size=-1)

        # Segment size doesn't divide word bit size - should adjust segment_size to word_bit_size
        value = Value(0, word_bit_size=8, segment_size=3)
        self.assertEqual(value.segment_size, 8)  # Should be adjusted to word_bit_size

        # Test case: segment_size is not a divisor of word_bit_size (16-bit word, segment_size=5)
        value = Value(0, word_bit_size=16, segment_size=5)
        self.assertEqual(value.segment_size, 16)  # Adjusted to word_bit_size

        # Segment size greater than word bit size
        with self.assertRaises(ValueError):
            Value(0, word_bit_size=4, segment_size=8)

        # Invalid endianness values
        with self.assertRaises(ValueError):
            Value(0, word_bit_size=8, intra_word_endianness='invalid')

        with self.assertRaises(ValueError):
            Value(0, word_bit_size=8, multi_word_endianness='invalid')

    def test_word_count_calculation(self):
        """Test calculation of word count for different values."""
        # Zero value
        value = Value(0, word_bit_size=8)
        self.assertEqual(value.word_count, 1)

        # Small positive value
        value = Value(255, word_bit_size=8)
        self.assertEqual(value.word_count, 1)

        # Value requiring multiple words
        value = Value(0x12345678, word_bit_size=8)
        self.assertEqual(value.word_count, 4)

        # Large value
        value = Value(0x123456789ABCDEF0, word_bit_size=8)
        self.assertEqual(value.word_count, 8)

        # Negative value
        value = Value(-1000, word_bit_size=8)
        self.assertEqual(value.word_count, 2)  # -1000 needs 11 bits (10 + sign)

    def test_to_bytes_big_endian(self):
        """Test byte conversion with big-endian multi-word endianness."""
        # 32-bit value in 8-bit words, big-endian
        value = Value(0x01234567, word_bit_size=8, multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '01234567')

        # 32-bit value in 16-bit words, big-endian
        value = Value(0x12345678, word_bit_size=16, multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '12345678')

        # 16-bit value in 8-bit words, big-endian
        value = Value(0x1234, word_bit_size=8, multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '1234')

    def test_to_bytes_little_endian(self):
        """Test byte conversion with little-endian multi-word endianness."""
        # 32-bit value in 8-bit words, little-endian
        value = Value(0x01234567, word_bit_size=8, multi_word_endianness='little')
        self.assertEqual(value.to_bytes().hex(), '67452301')

        # 32-bit value in 16-bit words, little-endian
        value = Value(0x12345678, word_bit_size=16, multi_word_endianness='little')
        self.assertEqual(value.to_bytes().hex(), '56781234')

        # 16-bit value in 8-bit words, little-endian
        value = Value(0x1234, word_bit_size=8, multi_word_endianness='little')
        self.assertEqual(value.to_bytes().hex(), '3412')

    def test_to_bytes_with_intra_word_endianness(self):
        """Test byte conversion with different intra-word endianness."""
        # 16-bit value in 8-bit words, little-endian intra-word, big-endian multi-word
        # Since each word is 8-bit, there's only one segment per word, so intra-word endianness doesn't matter
        value = Value(0x1234, word_bit_size=8, intra_word_endianness='little', multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '1234')  # Multi-word big-endian

        # 16-bit value in 8-bit words, little-endian intra-word, little-endian multi-word
        value = Value(0x1234, word_bit_size=8, intra_word_endianness='little', multi_word_endianness='little')
        self.assertEqual(value.to_bytes().hex(), '3412')  # Multi-word little-endian

        # Test with 16-bit words and 8-bit segments to see intra-word endianness effect
        value = Value(0x1234, word_bit_size=16, segment_size=8, intra_word_endianness='little', multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '3412')  # Intra-word little-endian reverses segments

        value = Value(0x1234, word_bit_size=16, segment_size=8, intra_word_endianness='big', multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '1234')  # Intra-word big-endian keeps segments in order

    def test_to_bytes_left_packed(self):
        """Test byte conversion with left-packing for non-byte-aligned words."""
        # 12-bit value in 4-bit words (left-packed)
        value = Value(0x123, word_bit_size=4, segment_size=4, multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '1230')  # 3 words of 4 bits each = 12 bits in 2 bytes

        # 12-bit value in 4-bit words, little-endian multi-word
        value = Value(0x123, word_bit_size=4, segment_size=4, multi_word_endianness='little')
        self.assertEqual(value.to_bytes().hex(), '3210')  # Words reversed, left-packed

        # 6-bit value in 3-bit words (left-packed)
        value = Value(0x15, word_bit_size=3, segment_size=3, multi_word_endianness='big')
        self.assertEqual(value.to_bytes().hex(), '54')  # 2 words of 3 bits each = 6 bits in 1 byte

    def test_negative_values(self):
        """Test handling of negative values."""
        # Negative 8-bit value
        value = Value(-1, word_bit_size=8, multi_word_endianness='big')
        self.assertEqual(value.value, -1)
        self.assertEqual(value.word_count, 1)
        self.assertEqual(value.to_bytes().hex(), 'ff')  # Two's complement

        # Negative 16-bit value
        value = Value(-1000, word_bit_size=8, multi_word_endianness='big')
        self.assertEqual(value.value, -1000)
        self.assertEqual(value.word_count, 2)
        self.assertEqual(value.to_bytes().hex(), 'fc18')  # Two's complement

        # Negative value with little-endian multi-word
        value = Value(-1000, word_bit_size=8, multi_word_endianness='little')
        self.assertEqual(value.to_bytes().hex(), '18fc')  # Words reversed

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Single word, maximum value
        value = Value(255, word_bit_size=8, multi_word_endianness='big')
        self.assertEqual(value.word_count, 1)
        self.assertEqual(value.to_bytes().hex(), 'ff')

        # Single word, zero value
        value = Value(0, word_bit_size=8, multi_word_endianness='big')
        self.assertEqual(value.word_count, 1)
        self.assertEqual(value.to_bytes().hex(), '00')

        # Large value requiring many words
        value = Value(0x123456789ABCDEF0, word_bit_size=4, segment_size=4, multi_word_endianness='big')
        self.assertEqual(value.word_count, 16)  # 64 bits / 4 bits per word

        # Very small word size
        value = Value(0x7, word_bit_size=1, segment_size=1, multi_word_endianness='big')
        self.assertEqual(value.word_count, 3)  # 7 needs 3 bits
        self.assertEqual(value.to_bytes().hex(), 'e0')  # 3 bits left-aligned in 1 byte

    def test_equality_and_hashing(self):
        """Test equality comparison and hashing."""
        value1 = Value(0x1234, word_bit_size=8, multi_word_endianness='big')
        value2 = Value(0x1234, word_bit_size=8, multi_word_endianness='big')
        value3 = Value(0x1234, word_bit_size=16, multi_word_endianness='big')
        value4 = Value(0x1234, word_bit_size=8, multi_word_endianness='little')

        self.assertEqual(value1, value2)
        self.assertNotEqual(value1, value3)  # Different word bit size
        self.assertNotEqual(value1, value4)  # Different multi-word endianness
        self.assertNotEqual(value1, 'not a Value')

        # Test hashing
        self.assertEqual(hash(value1), hash(value2))
        self.assertNotEqual(hash(value1), hash(value3))
        self.assertNotEqual(hash(value1), hash(value4))

        # Test in sets
        value_set = {value1, value2, value3, value4}
        self.assertEqual(len(value_set), 3)  # value1 and value2 are equal

    def test_string_representations(self):
        """Test string representations."""
        value = Value(0x12345678, word_bit_size=8, multi_word_endianness='little')

        # __repr__ should show hex value
        repr_str = repr(value)
        self.assertIn('0x12345678', repr_str)
        self.assertIn('4x8bit', repr_str)
        self.assertIn('multi_endian=little', repr_str)

        # __str__ should be readable
        str_str = str(value)
        self.assertIn('305419896', str_str)  # 0x12345678 in decimal
        self.assertIn('4 words', str_str)
        self.assertIn('8 bits', str_str)
        self.assertIn('little', str_str)

    def test_int_conversion(self):
        """Test integer conversion."""
        value = Value(0x12345678, word_bit_size=8)
        self.assertEqual(int(value), 0x12345678)

        value = Value(-1000, word_bit_size=8)
        self.assertEqual(int(value), -1000)

    def test_words_property(self):
        """Test that the words property returns a copy."""
        value = Value(0x1234, word_bit_size=8)
        words1 = value.words
        words2 = value.words

        # Should be equal but not the same object
        self.assertEqual(words1, words2)
        self.assertIsNot(words1, words2)

        # Modifying the returned list shouldn't affect the original
        words1[0] = Word(0x99, 8)
        self.assertNotEqual(value.words[0].value, 0x99)

    def test_get_words_ordered(self):
        """Test the get_words_ordered method with different endianness options."""
        # Create a value with big-endian multi-word endianness
        value = Value(0x12345678, word_bit_size=8, multi_word_endianness='big')

        # Test using the Value's own endianness (big-endian)
        words_big = value.get_words_ordered()
        self.assertEqual(len(words_big), 4)
        self.assertEqual(words_big[0].value, 0x12)  # MSB first
        self.assertEqual(words_big[1].value, 0x34)
        self.assertEqual(words_big[2].value, 0x56)
        self.assertEqual(words_big[3].value, 0x78)  # LSB last

        # Test overriding with little-endian
        words_little = value.get_words_ordered('little')
        self.assertEqual(len(words_little), 4)
        self.assertEqual(words_little[0].value, 0x78)  # LSB first
        self.assertEqual(words_little[1].value, 0x56)
        self.assertEqual(words_little[2].value, 0x34)
        self.assertEqual(words_little[3].value, 0x12)  # MSB last

        # Test overriding with big-endian (should be same as default)
        words_big_override = value.get_words_ordered('big')
        self.assertEqual(words_big_override, words_big)

        # Test with None parameter (should use Value's endianness)
        words_none = value.get_words_ordered(None)
        self.assertEqual(words_none, words_big)

    def test_get_words_ordered_little_endian_value(self):
        """Test get_words_ordered with a Value that has little-endian multi-word endianness."""
        # Create a value with little-endian multi-word endianness
        value = Value(0x12345678, word_bit_size=8, multi_word_endianness='little')

        # Test using the Value's own endianness (little-endian)
        words_little = value.get_words_ordered()
        self.assertEqual(len(words_little), 4)
        self.assertEqual(words_little[0].value, 0x78)  # LSB first
        self.assertEqual(words_little[1].value, 0x56)
        self.assertEqual(words_little[2].value, 0x34)
        self.assertEqual(words_little[3].value, 0x12)  # MSB last

        # Test overriding with big-endian
        words_big = value.get_words_ordered('big')
        self.assertEqual(len(words_big), 4)
        self.assertEqual(words_big[0].value, 0x12)  # MSB first
        self.assertEqual(words_big[1].value, 0x34)
        self.assertEqual(words_big[2].value, 0x56)
        self.assertEqual(words_big[3].value, 0x78)  # LSB last

        # Test overriding with little-endian (should be same as default)
        words_little_override = value.get_words_ordered('little')
        self.assertEqual(words_little_override, words_little)

    def test_get_words_ordered_validation(self):
        """Test validation of get_words_ordered parameters."""
        value = Value(0x1234, word_bit_size=8)

        # Test with invalid endianness
        with self.assertRaises(ValueError):
            value.get_words_ordered('invalid')

        with self.assertRaises(ValueError):
            value.get_words_ordered('middle')

    def test_get_words_ordered_single_word(self):
        """Test get_words_ordered with a single word value."""
        value = Value(0x12, word_bit_size=8, multi_word_endianness='big')

        # Should return the same word regardless of endianness
        words_big = value.get_words_ordered('big')
        words_little = value.get_words_ordered('little')

        self.assertEqual(len(words_big), 1)
        self.assertEqual(len(words_little), 1)
        self.assertEqual(words_big, words_little)
        self.assertEqual(words_big[0].value, 0x12)

    def test_get_words_ordered_returns_copy(self):
        """Test that get_words_ordered returns a copy, not the original list."""
        value = Value(0x12345678, word_bit_size=8, multi_word_endianness='big')

        words1 = value.get_words_ordered()
        words2 = value.get_words_ordered()

        # Should be equal but not the same object
        self.assertEqual(words1, words2)
        self.assertIsNot(words1, words2)

        # Modifying the returned list shouldn't affect the original
        if len(words1) > 0:
            original_value = words1[0].value
            words1[0] = Word(0x99, 8)
            self.assertNotEqual(value.get_words_ordered()[0].value, 0x99)
            self.assertEqual(value.get_words_ordered()[0].value, original_value)

    def test_get_words_ordered_example(self):
        """Example demonstrating the get_words_ordered functionality."""
        # Create a 32-bit value (0x12345678) using 8-bit words with big-endian multi-word endianness
        value = Value(0x12345678, word_bit_size=8, multi_word_endianness='big')

        # Get words in the Value's native order (big-endian)
        words_native = value.get_words_ordered()
        self.assertEqual([w.value for w in words_native], [0x12, 0x34, 0x56, 0x78])

        # Get words in little-endian order (override the Value's endianness)
        words_little = value.get_words_ordered('little')
        self.assertEqual([w.value for w in words_little], [0x78, 0x56, 0x34, 0x12])

        # Get words in big-endian order (explicit override)
        words_big = value.get_words_ordered('big')
        self.assertEqual([w.value for w in words_big], [0x12, 0x34, 0x56, 0x78])

        # Create a value with little-endian multi-word endianness
        value_le = Value(0x12345678, word_bit_size=8, multi_word_endianness='little')

        # Get words in the Value's native order (little-endian)
        words_native_le = value_le.get_words_ordered()
        self.assertEqual([w.value for w in words_native_le], [0x78, 0x56, 0x34, 0x12])

        # Override to get big-endian order
        words_big_override = value_le.get_words_ordered('big')
        self.assertEqual([w.value for w in words_big_override], [0x12, 0x34, 0x56, 0x78])

    def test_from_words_basic(self):
        """Test construction from a list of Word objects."""
        # Create some Word objects
        word1 = Word(0x12, 8)
        word2 = Word(0x34, 8)
        word3 = Word(0x56, 8)
        word4 = Word(0x78, 8)

        # Create Value from words
        value = Value.from_words([word1, word2, word3, word4])

        self.assertEqual(value.value, 0x12345678)
        self.assertEqual(value.word_bit_size, 8)
        self.assertEqual(value.segment_size, 8)
        self.assertEqual(value.intra_word_endianness, 'big')
        self.assertEqual(value.multi_word_endianness, 'big')
        self.assertEqual(value.word_count, 4)

        # Check that the words are stored correctly
        words = value.words
        self.assertEqual(len(words), 4)
        self.assertEqual(words[0].value, 0x12)
        self.assertEqual(words[1].value, 0x34)
        self.assertEqual(words[2].value, 0x56)
        self.assertEqual(words[3].value, 0x78)

    def test_from_words_with_custom_endianness(self):
        """Test construction from words with custom multi-word endianness."""
        word1 = Word(0x12, 8)
        word2 = Word(0x34, 8)

        # Create Value with little-endian multi-word endianness
        value = Value.from_words([word1, word2], multi_word_endianness='little')

        self.assertEqual(value.value, 0x1234)
        self.assertEqual(value.multi_word_endianness, 'little')

        # Check that get_words_ordered respects the endianness
        words_ordered = value.get_words_ordered()
        self.assertEqual([w.value for w in words_ordered], [0x34, 0x12])  # Little-endian order

    def test_from_words_validation(self):
        """Test validation when constructing from words."""
        word1 = Word(0x12, 8)
        word2 = Word(0x34, 16)  # Different bit size

        # Empty list
        with self.assertRaises(ValueError):
            Value.from_words([])

        # Inconsistent bit sizes
        with self.assertRaises(ValueError):
            Value.from_words([word1, word2])

        # Inconsistent segment sizes
        word3 = Word(0x56, 8, segment_size=4)
        with self.assertRaises(ValueError):
            Value.from_words([word1, word3])

        # Inconsistent intra-word endianness
        word4 = Word(0x78, 8, intra_word_endianness='little')
        with self.assertRaises(ValueError):
            Value.from_words([word1, word4])

    def test_from_words_single_word(self):
        """Test construction from a single Word."""
        word = Word(0x12, 8)
        value = Value.from_words([word])

        self.assertEqual(value.value, 0x12)
        self.assertEqual(value.word_count, 1)
        self.assertEqual(value.words[0].value, 0x12)

    def test_from_words_negative_values(self):
        """Test construction from words with negative values."""
        word1 = Word(-1, 8)  # 0xFF in two's complement
        word2 = Word(0x34, 8)

        value = Value.from_words([word1, word2])

        # The total value should be 0xFF34
        self.assertEqual(value.value, 0xFF34)
        self.assertEqual(value.to_bytes().hex(), 'ff34')

    def test_from_word_slices_basic(self):
        """Test construction from a list of WordSlice objects."""
        # Create some WordSlice objects
        slice1 = WordSlice(0x12, 8)
        slice2 = WordSlice(0x34, 8)
        slice3 = WordSlice(0x56, 8)
        slice4 = WordSlice(0x78, 8)

        # Create Value from WordSlices
        value = Value.from_word_slices([slice1, slice2, slice3, slice4], word_bit_size=8)

        self.assertEqual(value.value, 0x12345678)
        self.assertEqual(value.word_bit_size, 8)
        self.assertEqual(value.segment_size, 8)
        self.assertEqual(value.word_count, 4)

        # Check that the words are created correctly
        words = value.words
        self.assertEqual(len(words), 4)
        self.assertEqual(words[0].value, 0x12)
        self.assertEqual(words[1].value, 0x34)
        self.assertEqual(words[2].value, 0x56)
        self.assertEqual(words[3].value, 0x78)

    def test_from_word_slices_with_custom_params(self):
        """Test construction from WordSlices with custom parameters."""
        slice1 = WordSlice(0x12, 8)
        slice2 = WordSlice(0x34, 8)

        value = Value.from_word_slices(
            [slice1, slice2],
            word_bit_size=16,
            segment_size=4,
            intra_word_endianness='little',
            multi_word_endianness='little'
        )

        self.assertEqual(value.value, 0x1234)
        self.assertEqual(value.word_bit_size, 16)
        self.assertEqual(value.segment_size, 4)
        self.assertEqual(value.intra_word_endianness, 'little')
        self.assertEqual(value.multi_word_endianness, 'little')
        self.assertEqual(value.word_count, 1)  # 16 bits fit in one 16-bit word

    def test_from_word_slices_validation(self):
        """Test validation when constructing from WordSlices."""
        slice1 = WordSlice(0x12, 8)

        # Invalid word_bit_size
        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=0)

        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=-1)

        # Invalid segment_size
        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=8, segment_size=0)

        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=8, segment_size=-1)

        # Segment size greater than word bit size
        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=4, segment_size=8)

        # Invalid endianness values
        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=8, intra_word_endianness='invalid')

        with self.assertRaises(ValueError):
            Value.from_word_slices([slice1], word_bit_size=8, multi_word_endianness='invalid')

    def test_from_word_slices_empty_list(self):
        """Test construction from an empty WordSlice list."""
        value = Value.from_word_slices([], word_bit_size=8)

        self.assertEqual(value.value, 0)
        self.assertEqual(value.word_bit_size, 8)
        self.assertEqual(value.word_count, 1)
        self.assertEqual(value.words[0].value, 0)

    def test_from_word_slices_packing(self):
        """Test packing of WordSlices into words."""
        # Create WordSlices that will be packed into multiple words
        slice1 = WordSlice(0x12, 8)
        slice2 = WordSlice(0x34, 8)
        slice3 = WordSlice(0x56, 8)
        slice4 = WordSlice(0x78, 8)

        # Pack into 16-bit words
        value = Value.from_word_slices([slice1, slice2, slice3, slice4], word_bit_size=16)

        self.assertEqual(value.value, 0x12345678)
        self.assertEqual(value.word_count, 2)  # 32 bits / 16 bits per word

        # Check that the words are created correctly
        words = value.words
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].value, 0x1234)  # First 16 bits
        self.assertEqual(words[1].value, 0x5678)  # Second 16 bits

    def test_from_word_slices_negative_values(self):
        """Test construction from WordSlices with negative values."""
        slice1 = WordSlice(-1, 8)  # 0xFF in two's complement
        slice2 = WordSlice(0x34, 8)

        value = Value.from_word_slices([slice1, slice2], word_bit_size=8)

        # The total value should be 0xFF34
        self.assertEqual(value.value, 0xFF34)
        self.assertEqual(value.to_bytes().hex(), 'ff34')

    def test_from_word_slices_variable_sizes(self):
        """Test construction from WordSlices of different sizes."""
        slice1 = WordSlice(0x1, 4)   # 4 bits
        slice2 = WordSlice(0x23, 8)  # 8 bits
        slice3 = WordSlice(0x4, 4)   # 4 bits

        # Pack into 8-bit words
        value = Value.from_word_slices([slice1, slice2, slice3], word_bit_size=8)

        self.assertEqual(value.value, 0x1234)  # 0x1 << 12 + 0x23 << 4 + 0x4
        self.assertEqual(value.word_count, 2)  # 16 bits / 8 bits per word

        # Check that the words are created correctly
        words = value.words
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].value, 0x12)  # 0x1 << 4 + 0x2
        self.assertEqual(words[1].value, 0x34)  # 0x3 << 4 + 0x4

    def test_from_word_slice_large_bit_size(self):
        """Test construction from WordSlices with a large bit size."""
        slice1 = WordSlice(0x12345678, 32)

        value = Value.from_word_slices(
            [slice1],
            word_bit_size=8,
            segment_size=8,
            intra_word_endianness='big',
            multi_word_endianness='little',
        )

        self.assertEqual(value.value, 0x12345678)
        self.assertEqual(value.word_count, 4)
        words = value.get_words_ordered()
        self.assertEqual(
            words,
            [
                Word(0x78, 8, 8, 'big'),
                Word(0x56, 8, 8, 'big'),
                Word(0x34, 8, 8, 'big'),
                Word(0x12, 8, 8, 'big'),
            ],
            'words should be in little-endian order'
        )
