#!/usr/bin/env python3
"""
Test cases for the enhanced Word class with proper endianness support.
"""

import unittest
from src.bespokeasm.assembler.bytecode.word import Word


class TestWordEndianness(unittest.TestCase):
    """Test cases for Word class endianness functionality."""

    def setUp(self):
        pass

    def test_basic_endianness(self):
        """Test basic endianness functionality."""
        # Test 16-bit word with 8-bit segments (bytes)
        word_16bit = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word_16bit.to_bytes().hex(), '1234')

        word_16bit_le = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='little')
        self.assertEqual(word_16bit_le.to_bytes().hex(), '3412')

        # Test 32-bit word with 8-bit segments
        word_32bit = Word(0x12345678, bit_size=32, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word_32bit.to_bytes().hex(), '12345678')

        word_32bit_le = Word(0x12345678, bit_size=32, segment_size=8, intra_word_endianness='little')
        self.assertEqual(word_32bit_le.to_bytes().hex(), '78563412')

    def test_arbitrary_segment_sizes(self):
        """Test arbitrary segment sizes."""
        # Test 12-bit word with 4-bit segments (nibbles)
        word_12bit_4bit = Word(0x123, bit_size=12, segment_size=4, intra_word_endianness='big')
        self.assertEqual(word_12bit_4bit.to_bytes().hex(), '1230')  # Left-aligned in 2 bytes

        word_12bit_4bit_le = Word(0x123, bit_size=12, segment_size=4, intra_word_endianness='little')
        self.assertEqual(word_12bit_4bit_le.to_bytes().hex(), '3210')  # Segments reversed, left-aligned

        # Test 24-bit word with 6-bit segments
        word_24bit_6bit = Word(0x123456, bit_size=24, segment_size=6, intra_word_endianness='big')
        self.assertEqual(word_24bit_6bit.to_bytes().hex(), '123456')

        word_24bit_6bit_le = Word(0x123456, bit_size=24, segment_size=6, intra_word_endianness='little')
        self.assertEqual(word_24bit_6bit_le.to_bytes().hex(), '5918c4')

        # Test 16-bit word with 16-bit segments (no segmentation)
        word_16bit_16bit = Word(0x1234, bit_size=16, segment_size=16, intra_word_endianness='big')
        self.assertEqual(word_16bit_16bit.to_bytes().hex(), '1234')

    def test_segment_extraction(self):
        """Test segment extraction and combination."""
        # Test 16-bit word with 4-bit segments
        word = Word(0x1234, bit_size=16, segment_size=4, intra_word_endianness='big')
        segments = word._extract_segments()
        expected_segments = [0x1, 0x2, 0x3, 0x4]
        self.assertEqual(segments, expected_segments)

        # Test 24-bit word with 6-bit segments
        word_24 = Word(0x123456, bit_size=24, segment_size=6, intra_word_endianness='big')
        segments_24 = word_24._extract_segments()
        expected_segments_24 = [0x4, 0x23, 0x11, 0x16]
        self.assertEqual(segments_24, expected_segments_24)

        # Test segment combination
        combined = word_24._combine_segments(segments_24)
        self.assertEqual(combined, 0x123456)

    def test_validation(self):
        """Test parameter validation."""
        # Test bit_size not divisible by segment_size
        with self.assertRaises(ValueError) as context:
            Word(0x1234, bit_size=15, segment_size=4)
        self.assertIn('bit_size 15 must be divisible by segment_size 4', str(context.exception))

        # Test invalid segment_size
        with self.assertRaises(ValueError) as context:
            Word(0x1234, bit_size=16, segment_size=0)
        self.assertIn('segment_size must be greater than 0', str(context.exception))

    def test_properties(self):
        """Test Word object properties."""
        word = Word(0x1234, bit_size=16, segment_size=4, intra_word_endianness='little')

        self.assertEqual(word.value, 0x1234)
        self.assertEqual(word.bit_size, 16)
        self.assertEqual(word.segment_size, 4)
        self.assertEqual(word.intra_word_endianness, 'little')
        self.assertEqual(word.segment_count, 4)

    def test_equality_and_hash(self):
        """Test Word object equality and hashing."""
        word1 = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='big')
        word2 = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='big')
        word3 = Word(0x1234, bit_size=16, segment_size=4, intra_word_endianness='big')
        word4 = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='little')

        self.assertEqual(word1, word2)
        self.assertNotEqual(word1, word3)  # Different segment_size
        self.assertNotEqual(word1, word4)  # Different intra_word_endianness

        # Test hash consistency
        self.assertEqual(hash(word1), hash(word2))
        self.assertNotEqual(hash(word1), hash(word3))
        self.assertNotEqual(hash(word1), hash(word4))

    def test_repr(self):
        """Test string representation."""
        word = Word(0x1234, bit_size=16, segment_size=4, intra_word_endianness='little')
        repr_str = repr(word)

        self.assertIn('Word<', repr_str)
        self.assertIn('bit_size=16', repr_str)
        self.assertIn('segment_size=4', repr_str)
        self.assertIn('intra_word_endianness=little', repr_str)

    def test_int_conversion(self):
        """Test integer conversion."""
        word = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(int(word), 0x1234)

    def test_negative_values(self):
        """Test negative values with endianness."""
        # Test 8-bit negative value
        word = Word(-1, bit_size=8, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, -1)
        self.assertEqual(word.to_bytes().hex(), 'ff')  # Two's complement

        # Test 16-bit negative value
        word = Word(-1000, bit_size=16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, -1000)
        # -1000 in 16-bit two's complement is 0xFC18
        self.assertEqual(word.to_bytes().hex(), 'fc18')

        # Test little-endian negative value
        word_le = Word(-1000, bit_size=16, segment_size=8, intra_word_endianness='little')
        self.assertEqual(word_le.to_bytes().hex(), '18fc')  # Segments swapped

    def test_edge_cases(self):
        """Test edge cases with endianness."""
        # 1-bit word
        word = Word(1, bit_size=1, segment_size=1, intra_word_endianness='big')
        self.assertEqual(word.value, 1)
        self.assertEqual(word.to_bytes().hex(), '80')  # 1 bit in MSB position

        # 4-bit word
        word = Word(15, bit_size=4, segment_size=4, intra_word_endianness='big')
        self.assertEqual(word.value, 15)
        self.assertEqual(word.to_bytes().hex(), 'f0')  # 4 bits in MSB position

        # Maximum values
        word = Word(255, bit_size=8, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, 255)
        self.assertEqual(word.to_bytes().hex(), 'ff')

        word = Word(65535, bit_size=16, segment_size=8, intra_word_endianness='big')
        self.assertEqual(word.value, 65535)
        self.assertEqual(word.to_bytes().hex(), 'ffff')


if __name__ == '__main__':
    unittest.main()
