import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter


class TestPrettyPrinting(unittest.TestCase):

    def test_listing_bytes_per_line(self):
        word_list = [
            Word(0x00, 8),
            Word(0x01, 8),
            Word(0x02, 8),
            Word(0x03, 8),
            Word(0x04, 8),
            Word(0x05, 8),
            Word(0x06, 8),
            Word(0x07, 8),
            Word(0x08, 8),
            Word(0x09, 8),
            Word(0x0a, 8),
            Word(0x0b, 8),
            Word(0x0c, 8),
            Word(0x0d, 8),
            Word(0x0e, 8),
            Word(0x0f, 8),
        ]
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                6,
                8
            ),
            ['00 01 02 03 04 05 ', '06 07 08 09 0a 0b ', '0c 0d 0e 0f       '],
        )

        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                3,
                8,
            ),
            ['00 01 02 ', '03 04 05 ', '06 07 08 ', '09 0a 0b ', '0c 0d 0e ', '0f       '],
        )

        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                16,
                8,
            ),
            ['00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f '],
        )

    def test_listing_16bit_words(self):
        word_list = [
            Word(0x0000, 16), Word(0x0001, 16), Word(0x00a2, 16), Word(0x0b03, 16),
            Word(0x1234, 16), Word(0xabcd, 16), Word(0xffff, 16), Word(0x8000, 16),
        ]
        # words_per_str = 4
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                4,
                16
            ),
            ['0000 0001 00a2 0b03 ', '1234 abcd ffff 8000 '],
        )
        # words_per_str = 2
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                2,
                16
            ),
            ['0000 0001 ', '00a2 0b03 ', '1234 abcd ', 'ffff 8000 '],
        )
        # words_per_str = 1
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                1,
                16
            ),
            ['0000 ', '0001 ', '00a2 ', '0b03 ', '1234 ', 'abcd ', 'ffff ', '8000 '],
        )
        # words_per_str = 8 (all in one line)
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                8,
                16
            ),
            ['0000 0001 00a2 0b03 1234 abcd ffff 8000 '],
        )
        # words_per_str = 3 (not an even divisor of 8)
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                3,
                16
            ),
            ['0000 0001 00a2 ', '0b03 1234 abcd ', 'ffff 8000      '],
        )
