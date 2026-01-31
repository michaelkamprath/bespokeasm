import unittest

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.assembler.memory_zone import MemoryZone


class TestStringBytePacking(unittest.TestCase):
    def setUp(self):
        self.memzone = MemoryZone(32, 0, 2**32 - 1, 'GLOBAL')
        self.label_scope = GlobalLabelScope(set())
        self.diagnostic_reporter = DiagnosticReporter()

    def _make_data(
        self,
        line_str,
        word_size,
        intra_word_endianness,
        multi_word_endianness,
        cstr_terminator=0,
        string_byte_packing=True,
        string_byte_packing_fill=0,
    ):
        return DataLine.factory(
            1,
            line_str,
            '',
            self.memzone,
            word_size,
            8,
            intra_word_endianness,
            multi_word_endianness,
            cstr_terminator,
            string_byte_packing,
            string_byte_packing_fill,
            diagnostic_reporter=self.diagnostic_reporter,
        )

    def test_byte_directive_16bit_word_string_byte_packing(self):
        # 'Hello World' = 0x48 0x65 0x6c 0x6c 0x6f 0x20 0x57 0x6f 0x72 0x6c 0x64
        # Packed (big endian): 0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c, 0x6400
        d = self._make_data('.byte "Hello World"', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 6)
        self.assertEqual([w.value for w in words], [0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c, 0x6400])

    def test_byte_directive_16bit_word_string_byte_packing_little_endian(self):
        # Packed (little endian): 0x6548, 0x6c6c, 0x206f, 0x6f57, 0x6c72, 0x0064
        d = self._make_data('.byte "Hello World"', 16, 'little', 'little')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 6)
        self.assertEqual([w.value for w in words], [0x6548, 0x6c6c, 0x206f, 0x6f57, 0x6c72, 0x0064])

    def test_byte_directive_16bit_word_string_byte_packing_odd_length(self):
        # Use 'Hello Worl' (10 chars): 0x48 0x65 0x6c 0x6c 0x6f 0x20 0x57 0x6f 0x72 0x6c
        # Packed (big endian): 0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c
        d = self._make_data('.byte "Hello Worl"', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 5)
        self.assertEqual([w.value for w in words], [0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c])

    def test_cstr_directive_16bit_word_string_byte_packing(self):
        # 'Hello World' + 0x00 terminator
        # Packed (big endian): 0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c, 0x6400
        d = self._make_data('.cstr "Hello World"', 16, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 6)
        self.assertEqual([w.value for w in words], [0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c, 0x6400])

    def test_cstr_directive_16bit_word_string_byte_packing_little_endian(self):
        # Packed (little endian): 0x6548, 0x6c6c, 0x206f, 0x6f57, 0x6c72, 0x0064
        d = self._make_data('.cstr "Hello World"', 16, 'little', 'little')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 6)
        self.assertEqual([w.value for w in words], [0x6548, 0x6c6c, 0x206f, 0x6f57, 0x6c72, 0x0064])

    def test_byte_directive_32bit_word_string_byte_packing(self):
        # 'Hello World' = 0x48 0x65 0x6c 0x6c 0x6f 0x20 0x57 0x6f 0x72 0x6c 0x64
        # Packed (big endian): 0x48656c6c, 0x6f20576f, 0x726c6400
        d = self._make_data('.byte "Hello World"', 32, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 3)
        self.assertEqual([w.value for w in words], [0x48656c6c, 0x6f20576f, 0x726c6400])

    def test_byte_directive_32bit_word_string_byte_packing_little_endian(self):
        # Packed (little endian): 0x6c6c6548, 0x6f57206f, 0x00646c72
        d = self._make_data('.byte "Hello World"', 32, 'little', 'little')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 3)
        self.assertEqual([w.value for w in words], [0x6c6c6548, 0x6f57206f, 0x00646c72])

    def test_cstr_directive_32bit_word_string_byte_packing(self):
        # 'Hello World' + 0x00 terminator
        # Packed (big endian): 0x48656c6c, 0x6f20576f, 0x726c6400
        d = self._make_data('.cstr "Hello World"', 32, 'big', 'big')
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 3)
        self.assertEqual(
            [w.value for w in words],
            [0x48656c6c, 0x6f20576f, 0x726c6400]
        )

    def test_string_byte_packing_disabled(self):
        # Should behave as normal: one byte per word
        d = self._make_data('.byte "Hello World"', 16, 'big', 'big', string_byte_packing=False)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        self.assertEqual(len(words), 11)
        self.assertEqual(
            [w.value for w in words],
            [0x0048, 0x0065, 0x006c, 0x006c, 0x006f, 0x0020, 0x0057, 0x006f, 0x0072, 0x006c, 0x0064],
        )

    def test_byte_directive_16bit_word_string_byte_packing_fill(self):
        # 'Hello World' = 11 bytes, needs 1 byte of fill (0xFF) for 16-bit word packing
        d = self._make_data('.byte "Hello World"', 16, 'big', 'big', string_byte_packing_fill=0xFF)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Last word should be 0x64FF (0x64 = 'd', 0xFF = fill)
        self.assertEqual([w.value for w in words], [0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c, 0x64FF])

    def test_byte_directive_16bit_word_string_byte_packing_fill_little_endian(self):
        d = self._make_data('.byte "Hello World"', 16, 'little', 'little', string_byte_packing_fill=0xFF)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Last word should be 0xFF64 (0x64 = 'd', 0xFF = fill)
        self.assertEqual([w.value for w in words], [0x6548, 0x6c6c, 0x206f, 0x6f57, 0x6c72, 0xFF64])

    def test_cstr_directive_16bit_word_string_byte_packing_fill(self):
        # 'Hello World' + 0x00 terminator = 12 bytes, needs 0 fill for 16-bit word packing
        d = self._make_data('.cstr "Hello World"', 16, 'big', 'big', string_byte_packing_fill=0xFF)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Last word should be 0x6400 (no fill needed, terminator is 0x00)
        self.assertEqual([w.value for w in words], [0x4865, 0x6c6c, 0x6f20, 0x576f, 0x726c, 0x6400])

    def test_byte_directive_32bit_word_string_byte_packing_fill(self):
        # 'Hello World' = 11 bytes, needs 1 byte of fill (0xFF) for 32-bit word packing
        d = self._make_data('.byte "Hello World"', 32, 'big', 'big', string_byte_packing_fill=0xFF)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Last word should be 0x726c64FF (0x72 = 'r', 0x6c = 'l', 0x64 = 'd', 0xFF = fill)
        self.assertEqual([w.value for w in words], [0x48656c6c, 0x6f20576f, 0x726c64FF])

    def test_byte_directive_32bit_word_string_byte_packing_fill_little_endian(self):
        d = self._make_data('.byte "Hello World"', 32, 'little', 'little', string_byte_packing_fill=0xFF)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Last word should be 0xFF646c72 (0x72 = 'r', 0x6c = 'l', 0x64 = 'd', 0xFF = fill, little endian)
        self.assertEqual([w.value for w in words], [0x6c6c6548, 0x6f57206f, 0xFF646c72])

    def test_cstr_directive_32bit_word_string_byte_packing_fill(self):
        # 'Hello World' + 0x00 terminator = 12 bytes, no fill needed for 32-bit word packing
        d = self._make_data('.cstr "Hello World"', 32, 'big', 'big', string_byte_packing_fill=0xFF)
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Last word should be 0x726c6400 (no fill needed, terminator is 0x00)
        self.assertEqual(
            [w.value for w in words],
            [0x48656c6c, 0x6f20576f, 0x726c6400]
        )

        # Now test with a string that requires both terminator and fill ("Hello World!")
        # 'Hello World!' = 12 bytes, + 1 terminator = 13 bytes, needs 3 fill bytes for 32-bit word packing
        d2 = self._make_data('.cstr "Hello World!"', 32, 'big', 'big', string_byte_packing_fill=0xFF)
        d2.label_scope = self.label_scope
        d2.generate_words()
        words2 = d2.get_words()
        # Bytes: 0x48 0x65 0x6c 0x6c 0x6f 0x20 0x57 0x6f 0x72 0x6c 0x64 0x21 0x00 (terminator), then 3x0xFF
        # Packed: [0x48656c6c, 0x6f20576f, 0x726c6421, 0x00FFFFFF]
        self.assertEqual(
            [w.value for w in words2],
            [0x48656c6c, 0x6f20576f, 0x726c6421, 0x00FFFFFF]
        )

    def test_cstr_directive_32bit_word_string_byte_packing_fill_custom_terminator(self):
        # 'Hello World!' + 0xAA terminator = 13 bytes, needs 3 fill bytes for 32-bit word packing
        d = self._make_data(
            '.cstr "Hello World!"',
            32,
            'big',
            'big',
            cstr_terminator=0xAA,
            string_byte_packing_fill=0xFF,
        )
        d.label_scope = self.label_scope
        d.generate_words()
        words = d.get_words()
        # Bytes: 0x48 0x65 0x6c 0x6c 0x6f 0x20 0x57 0x6f 0x72 0x6c 0x64 0x21 0xAA, then 3x0xFF
        # Packed: [0x48656c6c, 0x6f20576f, 0x726c6421, 0xAAFFFFFF]
        self.assertEqual(
            [w.value for w in words],
            [0x48656c6c, 0x6f20576f, 0x726c6421, 0xAAFFFFFF]
        )


if __name__ == '__main__':
    unittest.main()
