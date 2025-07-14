import unittest
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.bytecode.word_slice import WordSlice


class TestWord(unittest.TestCase):

    def test_construction_from_integer(self):
        """Test Word construction from integer values."""
        # 8-bit word
        word = Word(100, 8)
        self.assertEqual(word.value, 100)
        self.assertEqual(word.bit_size, 8)
        self.assertEqual(word.segment_size, 8)  # default
        self.assertEqual(word.intra_word_endianness, 'big')  # default

        # 16-bit word with custom segment size
        word = Word(0x1234, 16, segment_size=4, intra_word_endianness='little')
        self.assertEqual(word.value, 0x1234)
        self.assertEqual(word.bit_size, 16)
        self.assertEqual(word.segment_size, 4)
        self.assertEqual(word.intra_word_endianness, 'little')

        # 4-bit word
        word = Word(5, 4, segment_size=4)
        self.assertEqual(word.value, 5)
        self.assertEqual(word.bit_size, 4)
        self.assertEqual(word.segment_size, 4)

    def test_construction_from_word_slices(self):
        """Test Word construction from WordSlice lists."""
        # 8-bit word from two 4-bit slices
        slices = [WordSlice(3, 4), WordSlice(5, 4)]
        word = Word.from_word_slices(slices, 8, segment_size=4)
        self.assertEqual(word.value, 0x35)  # 3 in upper 4 bits, 5 in lower 4 bits
        self.assertEqual(word.bit_size, 8)
        self.assertEqual(word.segment_size, 4)

        # 16-bit word from multiple slices
        slices = [WordSlice(1, 4), WordSlice(2, 4), WordSlice(3, 4), WordSlice(4, 4)]
        word = Word.from_word_slices(slices, 16, segment_size=4)
        self.assertEqual(word.value, 0x1234)
        self.assertEqual(word.bit_size, 16)

        # 12-bit word with padding
        slices = [WordSlice(5, 4), WordSlice(10, 4)]
        word = Word.from_word_slices(slices, 12, segment_size=4)
        self.assertEqual(word.value, 0x5A0)  # 5 in upper 4 bits, 10 in middle 4 bits, 0 in lower 4 bits
        self.assertEqual(word.bit_size, 12)

        # heterogeneous slices
        slices = [WordSlice(3, 3),  WordSlice(1, 2), WordSlice(0b11001100, 8), WordSlice(1, 3)]
        word = Word.from_word_slices(slices, 16, segment_size=8)
        self.assertEqual(word.value, 0b0110111001100001)  # 1 in upper 4 bits, 2 in lower 8 bits
        self.assertEqual(word.bit_size, 16)

    def test_construction_validation(self):
        """Test validation of Word construction parameters."""
        # Invalid bit_size
        with self.assertRaises(ValueError):
            Word(0, 0)

        with self.assertRaises(ValueError):
            Word(0, -1)

        # Invalid segment_size
        with self.assertRaises(ValueError):
            Word(0, 8, segment_size=0)

        with self.assertRaises(ValueError):
            Word(0, 8, segment_size=-1)

        # Segment size doesn't divide bit size
        with self.assertRaises(ValueError):
            Word(0, 8, segment_size=3)

        # Segment size greater than bit size
        with self.assertRaises(ValueError):
            Word(0, 4, segment_size=8)

        # Invalid endianness
        with self.assertRaises(ValueError):
            Word(0, 8, intra_word_endianness='invalid')

        # Value out of range
        with self.assertRaises(ValueError):
            Word(256, 8)  # 256 doesn't fit in 8 bits

        with self.assertRaises(ValueError):
            Word(-129, 8)  # -129 doesn't fit in 8 bits (signed)

    def test_word_slice_construction_validation(self):
        """Test validation of Word construction from WordSlices."""
        # Total bits exceed word size
        slices = [WordSlice(0, 8), WordSlice(0, 8)]  # 16 bits total
        with self.assertRaises(ValueError):
            Word.from_word_slices(slices, 8)  # Only 8 bits available

        # Invalid parameters
        with self.assertRaises(ValueError):
            Word.from_word_slices([], 0)

        with self.assertRaises(ValueError):
            Word.from_word_slices([], 8, segment_size=3)  # 3 doesn't divide 8

    def test_properties(self):
        """Test Word properties."""
        word = Word(0x1234, 16, segment_size=4, intra_word_endianness='little')

        self.assertEqual(word.value, 0x1234)
        self.assertEqual(word.bit_size, 16)
        self.assertEqual(word.segment_size, 4)
        self.assertEqual(word.intra_word_endianness, 'little')
        self.assertEqual(word.segment_count, 4)  # 16 bits / 4 bits per segment

    def test_to_bytes_big_endian(self):
        """Test byte conversion with big-endian intra-word endianness."""
        # 8-bit word, 8-bit segments, big-endian
        word = Word(0x12, 8, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.to_bytes(), b'\x12')

        # 16-bit word, 8-bit segments, big-endian
        word = Word(0x1234, 16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.to_bytes(), b'\x12\x34')

        # 16-bit word, 4-bit segments, big-endian
        word = Word(0x1234, 16, segment_size=4, intra_word_endianness='big')
        self.assertEqual(word.to_bytes(), b'\x12\x34')  # Same as 8-bit segments

        # 12-bit word, 4-bit segments, big-endian
        word = Word(0x123, 12, segment_size=4, intra_word_endianness='big')
        self.assertEqual(word.to_bytes(), b'\x12\x30')  # Padded to 2 bytes

    def test_to_bytes_little_endian(self):
        """Test byte conversion with little-endian intra-word endianness."""
        # 8-bit word, 8-bit segments, little-endian
        word = Word(0x12, 8, segment_size=8, intra_word_endianness='little')
        self.assertEqual(word.to_bytes(), b'\x12')  # No change for single segment

        # 16-bit word, 8-bit segments, little-endian
        word = Word(0x1234, 16, segment_size=8, intra_word_endianness='little')
        self.assertEqual(word.to_bytes(), b'\x34\x12')  # Segments swapped

        # 16-bit word, 4-bit segments, little-endian
        word = Word(0x1234, 16, segment_size=4, intra_word_endianness='little')
        self.assertEqual(word.to_bytes(), b'\x43\x21')  # All 4-bit segments reversed

        # 12-bit word, 4-bit segments, little-endian
        word = Word(0x123, 12, segment_size=4, intra_word_endianness='little')
        self.assertEqual(word.to_bytes(), b'\x32\x10')  # Segments reversed, padded

    def test_negative_values(self):
        """Test handling of negative values."""
        # 8-bit negative value
        word = Word(-1, 8, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, -1)
        self.assertEqual(word.to_bytes(), b'\xff')  # Two's complement

        # 16-bit negative value
        word = Word(-1000, 16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, -1000)
        # -1000 in 16-bit two's complement is 0xFC18
        self.assertEqual(word.to_bytes(), b'\xfc\x18')

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # 1-bit word
        word = Word(1, 1, segment_size=1, intra_word_endianness='big')
        self.assertEqual(word.value, 1)
        self.assertEqual(word.to_bytes(), b'\x80')  # 1 bit in MSB position

        # 4-bit word
        word = Word(15, 4, segment_size=4, intra_word_endianness='big')
        self.assertEqual(word.value, 15)
        self.assertEqual(word.to_bytes(), b'\xf0')  # 4 bits in MSB position

        # Maximum values
        word = Word(255, 8, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, 255)
        self.assertEqual(word.to_bytes(), b'\xff')

        word = Word(65535, 16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, 65535)
        self.assertEqual(word.to_bytes(), b'\xff\xff')

    def test_equality_and_hashing(self):
        """Test equality comparison and hashing."""
        word1 = Word(100, 8, segment_size=8, intra_word_endianness='big')
        word2 = Word(100, 8, segment_size=8, intra_word_endianness='big')
        word3 = Word(100, 8, segment_size=4, intra_word_endianness='big')
        word4 = Word(101, 8, segment_size=8, intra_word_endianness='big')

        self.assertEqual(word1, word2)
        self.assertNotEqual(word1, word3)  # Different segment size
        self.assertNotEqual(word1, word4)  # Different value
        self.assertNotEqual(word1, 'not a Word')

        # Test hashing
        self.assertEqual(hash(word1), hash(word2))
        self.assertNotEqual(hash(word1), hash(word3))

        # Test in sets
        word_set = {word1, word2, word3, word4}
        self.assertEqual(len(word_set), 3)  # word1 and word2 are equal

    def test_string_representations(self):
        """Test string representations."""
        word = Word(0x1234, 16, segment_size=4, intra_word_endianness='little')

        # __repr__ should show hex value
        repr_str = repr(word)
        self.assertIn('0x1234', repr_str)
        self.assertIn('16', repr_str)
        self.assertIn('4', repr_str)
        self.assertIn('little', repr_str)

        # __str__ should be readable
        str_str = str(word)
        self.assertIn('4660', str_str)  # 0x1234 in decimal
        self.assertIn('16 bits', str_str)
        self.assertIn('4-bit segments', str_str)
        self.assertIn('little', str_str)

    def test_int_conversion(self):
        """Test integer conversion."""
        word = Word(100, 8)
        self.assertEqual(int(word), 100)

        word = Word(-50, 8)
        self.assertEqual(int(word), -50)

    def test_from_bytes(self):
        """Test from_bytes method."""
        bytes = b'\x12\x34'
        words = Word.from_bytes(bytes, 16, 8, 'big')
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].value, 0x1234)
        self.assertEqual(words[0].bit_size, 16)
        self.assertEqual(words[0].segment_size, 8)

        bytes = b'\x12\x34'
        words = Word.from_bytes(bytes, 8, 8, 'big')
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].value, 0x12)
        self.assertEqual(words[1].value, 0x34)
        self.assertEqual(words[0].bit_size, 8)
        self.assertEqual(words[1].bit_size, 8)
        self.assertEqual(words[0].segment_size, 8)
        self.assertEqual(words[1].segment_size, 8)

        bytes = b'\x12\x34'
        words = Word.from_bytes(bytes, 8, 4, 'little')
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].value, 0x21)
        self.assertEqual(words[1].value, 0x43)
        self.assertEqual(words[0].bit_size, 8)
        self.assertEqual(words[1].bit_size, 8)
        self.assertEqual(words[0].segment_size, 4)
        self.assertEqual(words[1].segment_size, 4)
