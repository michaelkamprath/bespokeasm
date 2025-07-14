#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced Word class with proper endianness support.
"""

from src.bespokeasm.assembler.bytecode.word import Word


def test_basic_endianness():
    """Test basic endianness functionality."""
    print('=== Basic Endianness Tests ===')

    # Test 16-bit word with 8-bit segments (bytes)
    word_16bit = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='big')
    print(f'16-bit word 0x1234 (big-endian bytes): {word_16bit.to_bytes().hex()}')

    word_16bit_le = Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='little')
    print(f'16-bit word 0x1234 (little-endian bytes): {word_16bit_le.to_bytes().hex()}')

    # Test 32-bit word with 8-bit segments
    word_32bit = Word(0x12345678, bit_size=32, segment_size=8, intra_word_endianness='big')
    print(f'32-bit word 0x12345678 (big-endian bytes): {word_32bit.to_bytes().hex()}')

    word_32bit_le = Word(0x12345678, bit_size=32, segment_size=8, intra_word_endianness='little')
    print(f'32-bit word 0x12345678 (little-endian bytes): {word_32bit_le.to_bytes().hex()}')


def test_arbitrary_segment_sizes():
    """Test arbitrary segment sizes."""
    print('\n=== Arbitrary Segment Size Tests ===')

    # Test 12-bit word with 4-bit segments (nibbles)
    word_12bit_4bit = Word(0x123, bit_size=12, segment_size=4, intra_word_endianness='big')
    print(f'12-bit word 0x123 (4-bit segments, big-endian): {word_12bit_4bit.to_bytes().hex()}')

    word_12bit_4bit_le = Word(0x123, bit_size=12, segment_size=4, intra_word_endianness='little')
    print(f'12-bit word 0x123 (4-bit segments, little-endian): {word_12bit_4bit_le.to_bytes().hex()}')

    # Test 24-bit word with 6-bit segments
    word_24bit_6bit = Word(0x123456, bit_size=24, segment_size=6, intra_word_endianness='big')
    print(f'24-bit word 0x123456 (6-bit segments, big-endian): {word_24bit_6bit.to_bytes().hex()}')

    word_24bit_6bit_le = Word(0x123456, bit_size=24, segment_size=6, intra_word_endianness='little')
    print(f'24-bit word 0x123456 (6-bit segments, little-endian): {word_24bit_6bit_le.to_bytes().hex()}')

    # Test 16-bit word with 16-bit segments (no segmentation)
    word_16bit_16bit = Word(0x1234, bit_size=16, segment_size=16, intra_word_endianness='big')
    print(f'16-bit word 0x1234 (16-bit segments, big-endian): {word_16bit_16bit.to_bytes().hex()}')


def test_multi_word_endianness():
    """Test multi-word endianness."""
    print('\n=== Multi-Word Endianness Tests ===')

    # Create multiple words with different intra-word endianness
    words = [
        Word(0x1234, bit_size=16, segment_size=8, intra_word_endianness='big'),
        Word(0x5678, bit_size=16, segment_size=8, intra_word_endianness='little'),
        Word(0x9ABC, bit_size=16, segment_size=8, intra_word_endianness='big')
    ]

    # Generate byte array with big-endian multi-word ordering
    byte_array_be = Word.generateByteArray(words, multi_word_endianness='big')
    print(f'Multi-word array (big-endian): {byte_array_be.hex()}')

    # Generate byte array with little-endian multi-word ordering
    byte_array_le = Word.generateByteArray(words, multi_word_endianness='little')
    print(f'Multi-word array (little-endian): {byte_array_le.hex()}')


def test_segment_extraction():
    """Test segment extraction and combination."""
    print('\n=== Segment Extraction Tests ===')

    # Test 16-bit word with 4-bit segments
    word = Word(0x1234, bit_size=16, segment_size=4, intra_word_endianness='big')
    segments = word._extract_segments(word.value)
    print(f'16-bit word 0x1234 with 4-bit segments: {[hex(s) for s in segments]}')

    # Test 24-bit word with 6-bit segments
    word_24 = Word(0x123456, bit_size=24, segment_size=6, intra_word_endianness='big')
    segments_24 = word_24._extract_segments(word_24.value)
    print(f'24-bit word 0x123456 with 6-bit segments: {[hex(s) for s in segments_24]}')

    # Test segment combination
    combined = word_24._combine_segments(segments_24)
    print(f'Combined segments back to value: 0x{combined:x}')


def test_compact_bytes():
    """Test compact byte packing with endianness."""
    print('\n=== Compact Bytes Tests ===')

    # Test compact packing with different endianness
    words = [
        Word(0x12, bit_size=8, segment_size=8, intra_word_endianness='big'),
        Word(0x34, bit_size=8, segment_size=8, intra_word_endianness='little'),
        Word(0x56, bit_size=8, segment_size=8, intra_word_endianness='big')
    ]

    compact_bytes = Word.generateByteArray(words, compact_bytes=True, multi_word_endianness='big')
    print(f'Compact bytes (big-endian): {compact_bytes.hex()}')

    compact_bytes_le = Word.generateByteArray(words, compact_bytes=True, multi_word_endianness='little')
    print(f'Compact bytes (little-endian): {compact_bytes_le.hex()}')


def test_validation():
    """Test parameter validation."""
    print('\n=== Validation Tests ===')

    try:
        # This should fail - bit_size not divisible by segment_size
        Word(0x1234, bit_size=15, segment_size=4)
        print('ERROR: Should have failed for non-divisible bit_size')
    except ValueError as e:
        print(f'Correctly caught error: {e}')

    try:
        # This should fail - invalid segment_size
        Word(0x1234, bit_size=16, segment_size=0)
        print('ERROR: Should have failed for zero segment_size')
    except ValueError as e:
        print(f'Correctly caught error: {e}')


if __name__ == '__main__':
    test_basic_endianness()
    test_arbitrary_segment_sizes()
    test_multi_word_endianness()
    test_segment_extraction()
    test_compact_bytes()
    test_validation()

    print('\n=== All tests completed ===')
