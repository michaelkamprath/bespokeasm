import unittest

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.assembler.memory_zone import MemoryZone


class TestDataLineWordSizes(unittest.TestCase):
    def setUp(self):
        self.memzone = MemoryZone(32, 0, 2**32 - 1, 'GLOBAL')
        self.label_scope = GlobalLabelScope(set())
        self.diagnostic_reporter = DiagnosticReporter()

    def _make_data(self, line_str, word_size, intra_word_endianness, multi_word_endianness):
        return DataLine.factory(
            1,
            line_str,
            '',
            self.memzone,
            word_size,
            8,
            intra_word_endianness,
            multi_word_endianness,
            0,
            diagnostic_reporter=self.diagnostic_reporter,
        )

    def test_byte_directive_16bit_word(self):
        d = self._make_data('.byte $01, $02, $03, $04', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 4)
        self.assertEqual([w.value for w in words], [0x0001, 0x0002, 0x0003, 0x0004])

    def test_byte_directive_16bit_word_little_endian(self):
        d = self._make_data('.byte $01, $02, $03, $04', 16, 'little', 'little')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 4)
        self.assertEqual([w.value for w in words], [0x0001, 0x0002, 0x0003, 0x0004])

    def test_2byte_directive_16bit_word(self):
        d = self._make_data('.2byte $1234, $beef', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 2)
        self.assertEqual([w.value for w in words], [0x1234, 0xbeef])

    def test_4byte_directive_16bit_word(self):
        d = self._make_data('.4byte $01020304', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 2)
        self.assertEqual([w.value for w in words], [0x0102, 0x0304])

    def test_4byte_directive_16bit_word_little_endian(self):
        d = self._make_data('.4byte $01020304', 16, 'little', 'little')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 2)
        self.assertEqual([w.value for w in words], [0x0304, 0x0102])

    def test_4byte_directive_16bit_word_multiword_big_endian(self):
        # .4byte $01020304 on 16-bit word, multi-word big-endian
        d = self._make_data('.4byte $01020304', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Should be [0x0102, 0x0304] (high bytes first)
        self.assertEqual(len(words), 2)
        self.assertEqual([w.value for w in words], [0x0102, 0x0304])

    def test_4byte_directive_16bit_word_multiword_little_endian(self):
        # .4byte $01020304 on 16-bit word, multi-word little-endian
        d = self._make_data('.4byte $01020304', 16, 'big', 'little')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Should be [0x0304, 0x0102] (low words first)
        self.assertEqual(len(words), 2)
        self.assertEqual([w.value for w in words], [0x0304, 0x0102])

    def test_byte_directive_32bit_word(self):
        d = self._make_data('.byte $01, $02, $03, $04', 32, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 4)
        self.assertEqual([w.value for w in words], [0x00000001, 0x00000002, 0x00000003, 0x00000004])

    def test_cstr_directive_16bit_word(self):
        d = self._make_data('.cstr "AB"', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 3)
        self.assertEqual([w.value for w in words], [0x0041, 0x0042, 0x0000])

    def test_padding_behavior(self):
        d = self._make_data('.4byte $010203', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 2)
        self.assertEqual([w.value for w in words], [0x0001, 0x0203])

    def test_data_line_word_count(self):
        # .byte $01, $02, $03 on 16-bit word, should have word_count == 3
        d = self._make_data('.byte $01, $02, $03', 16, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 3)

        # .byte $01, $02, $03 on 8-bit word, should have word_count == 3
        d = self._make_data('.byte $01, $02, $03', 8, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 3)

        # .2byte $1234, $beef on 8-bit word, should have word_count == 4
        d = self._make_data('.2byte $1234, $beef', 8, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 4)  # Each 2byte splits into 2 8-bit words

        # .2byte $1234, $beef on 16-bit word, should have word_count == 2
        d = self._make_data('.2byte $1234, $beef', 16, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 2)

        # .4byte $01020304 on 8-bit word, should have word_count == 4
        d = self._make_data('.4byte $01020304', 8, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 4)

        # .4byte $01020304 on 16-bit word, should have word_count == 2
        d = self._make_data('.4byte $01020304', 16, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 2)

        # .4byte $01020304 on 32-bit word, should have word_count == 1
        d = self._make_data('.4byte $01020304', 32, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 1)

        # .cstr "AB" on 8-bit word, should have word_count == 3
        d = self._make_data('.cstr "AB"', 8, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 3)  # 'A', 'B', terminator

        # .cstr "AB" on 16-bit word, should have word_count == 3
        d = self._make_data('.cstr "AB"', 16, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 3)

        # .cstr "A" on 3
        d = self._make_data('.cstr "A"', 32, 'big', 'big')
        d.label_scope = self.label_scope
        self.assertEqual(d.word_count, 2)  # 'A', terminator


if __name__ == '__main__':
    unittest.main()
