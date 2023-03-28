import unittest

from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter


class TestPrettyPrinting(unittest.TestCase):

    def test_listing_bytes_per_line(self):
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f',
                6
            ),
            ['00 01 02 03 04 05 ', '06 07 08 09 0a 0b ', '0c 0d 0e 0f       '],
        )

        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f',
                3
            ),
            ['00 01 02 ', '03 04 05 ', '06 07 08 ', '09 0a 0b ', '0c 0d 0e ', '0f       '],
        )

        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f',
                16
            ),
            ['00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f '],
        )
