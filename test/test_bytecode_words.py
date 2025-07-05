import unittest

from bespokeasm.assembler.bytecode.word import Word


class TestWord(unittest.TestCase):
    def test_fromByteArray(self):
        # Test with compact_bytes = False
        byte_array = bytes([0x12, 0x34, 0x56, 0x78])
        words = Word.fromByteArray(byte_array, bit_size=8, compact_bytes=False)
        self.assertEqual(len(words), 4)
        self.assertEqual(words[0].value, 0x12)
        self.assertEqual(words[0].bit_size, 8)
        self.assertEqual(words[1].value, 0x34)
        self.assertEqual(words[1].bit_size, 8)
        self.assertEqual(words[2].value, 0x56)
        self.assertEqual(words[2].bit_size, 8)
        self.assertEqual(words[3].value, 0x78)
        self.assertEqual(words[3].bit_size, 8)

        # Test with compact_bytes = True and bit_size = 4
        words = Word.fromByteArray(byte_array, bit_size=4, compact_bytes=True)
        self.assertEqual(len(words), 8)
        self.assertEqual(words[0].value, 0x1)
        self.assertEqual(words[0].bit_size, 4)
        self.assertEqual(words[1].value, 0x2)
        self.assertEqual(words[1].bit_size, 4)
        self.assertEqual(words[2].value, 0x3)
        self.assertEqual(words[2].bit_size, 4)
        self.assertEqual(words[3].value, 0x4)
        self.assertEqual(words[3].bit_size, 4)
        self.assertEqual(words[4].value, 0x5)
        self.assertEqual(words[4].bit_size, 4)
        self.assertEqual(words[5].value, 0x6)
        self.assertEqual(words[5].bit_size, 4)
        self.assertEqual(words[6].value, 0x7)
        self.assertEqual(words[6].bit_size, 4)
        self.assertEqual(words[7].value, 0x8)
        self.assertEqual(words[7].bit_size, 4)

        # test with compact_bytes = True and bit_size = 16
        words = Word.fromByteArray(byte_array, bit_size=16, compact_bytes=True)
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].value, 0x1234)
        self.assertEqual(words[0].bit_size, 16)
        self.assertEqual(words[1].value, 0x5678)
        self.assertEqual(words[1].bit_size, 16)

        # test with compact_bytes = True and bit_size = 6
        # support for bit sizes that are not a multiple of 8 are not implemented
        with self.assertRaises(NotImplementedError):
            Word.fromByteArray(byte_array, bit_size=6, compact_bytes=True)

    def test_fromInt(self):
        word = Word.fromInt(42, bit_size=8)
        self.assertEqual(word.value, 42)

    def test_toByteArray(self):
        # test 8 bit words
        words = [Word.fromInt(i, bit_size=8) for i in range(4)]
        byte_array = Word.generateByteArray(words, compact_bytes=False)
        self.assertEqual(byte_array, bytes([0, 1, 2, 3]))
        byte_array_compact = Word.generateByteArray(words, compact_bytes=True)
        self.assertEqual(byte_array_compact, bytes([0, 1, 2, 3]))

        # test 4 bit words
        words = [Word.fromInt(i, bit_size=4) for i in range(8)]
        byte_array = Word.generateByteArray(words, compact_bytes=False)
        self.assertEqual(byte_array, bytes([0, 1, 2, 3, 4, 5, 6, 7]))
        byte_array_compact = Word.generateByteArray(words, compact_bytes=True)
        self.assertEqual(byte_array_compact, bytes([0x01, 0x23, 0x45, 0x67, ]))

        # test 16 bit words
        words = [Word.fromInt(i, bit_size=16) for i in range(8)] + [Word.fromInt(0x1234, bit_size=16)]
        byte_array = Word.generateByteArray(words, compact_bytes=False)
        self.assertEqual(byte_array, bytes([0, 0, 0, 1, 0, 2, 0, 3, 0, 4, 0, 5, 0, 6, 0, 7, 0x12, 0x34]))
        byte_array_compact = Word.generateByteArray(words, compact_bytes=True)
        self.assertEqual(byte_array_compact, bytes([
                0x00, 0x00, 0x00, 0x01, 0x00, 0x02, 0x00, 0x03,
                0x00, 0x04, 0x00, 0x05, 0x00, 0x06, 0x00, 0x07,
                0x12, 0x34
            ]))

        # test 6 bit words
        words = [Word.fromInt(i, bit_size=6) for i in range(8)]
        byte_array = Word.generateByteArray(words, compact_bytes=False)
        self.assertEqual(byte_array, bytes([0, 1, 2, 3, 4, 5, 6, 7]))
        byte_array = Word.generateByteArray(words, compact_bytes=True)
        self.assertEqual(byte_array, bytes([0x00, 0x10, 0x83, 0x10, 0x51, 0x87]))

    def test_invalid_cases(self):
        # Test fromInt with invalid bit size
        with self.assertRaises(ValueError):
            Word.fromInt(42, bit_size=0)
        with self.assertRaises(ValueError):
            Word.fromInt(42, bit_size=-8)

        # Test fromByteArray with invalid bit size
        with self.assertRaises(ValueError):
            Word.fromByteArray(bytes([0x12, 0x34]), bit_size=0, compact_bytes=False)
        with self.assertRaises(ValueError):
            Word.fromByteArray(bytes([0x12, 0x34]), bit_size=-8, compact_bytes=False)

    def test_equality(self):
        word1 = Word.fromInt(42, bit_size=8)
        word2 = Word.fromInt(42, bit_size=8)
        word3 = Word.fromInt(43, bit_size=8)
        word4 = Word.fromInt(42, bit_size=16)
        self.assertEqual(word1, word2)
        self.assertNotEqual(word1, word3)
        self.assertNotEqual(word1, 'not a word')
        self.assertNotEqual(word1, word4)
