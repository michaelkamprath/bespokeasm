import unittest

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.predefined_data import PredefinedDataLine
from bespokeasm.assembler.memory_zone import MemoryZone


class TestPredefinedDataLine(unittest.TestCase):
    def setUp(self):
        self.line_id = LineIdentifier(1, 'test')
        self.memzone = MemoryZone(16, 0, 2**16 - 1, 'GLOBAL')

    def test_basic_generation(self):
        pd = PredefinedDataLine(
            line_id=self.line_id,
            word_count=4,
            value=0xAB,
            name='testdata',
            current_memzone=self.memzone,
            word_size=8,
            word_segment_size=8,
            intra_word_endianness='big',
            multi_word_endianness='big',
        )
        self.assertEqual(pd.word_count, 4)
        pd.generate_words()
        self.assertEqual(len(pd._words), 4)
        for w in pd._words:
            self.assertEqual(w.value, 0xAB)
            self.assertEqual(w.bit_size, 8)
            self.assertEqual(w.segment_size, 8)
            self.assertEqual(w.intra_word_endianness, 'big')

    def test_zero_word_count(self):
        pd = PredefinedDataLine(
            line_id=self.line_id,
            word_count=0,
            value=0xFF,
            name='empty',
            current_memzone=self.memzone,
            word_size=8,
            word_segment_size=8,
            intra_word_endianness='little',
            multi_word_endianness='little',
        )
        pd.generate_words()
        self.assertEqual(len(pd._words), 0)

    def test_large_value_masking(self):
        pd = PredefinedDataLine(
            line_id=self.line_id,
            word_count=2,
            value=0x1FF,  # 9 bits, should be masked to 8 bits
            name='mask',
            current_memzone=self.memzone,
            word_size=8,
            word_segment_size=8,
            intra_word_endianness='big',
            multi_word_endianness='big',
        )
        pd.generate_words()
        for w in pd._words:
            self.assertEqual(w.value, 0xFF)

    def test_endianness(self):
        pd = PredefinedDataLine(
            line_id=self.line_id,
            word_count=3,
            value=0x12,
            name='endian',
            current_memzone=self.memzone,
            word_size=8,
            word_segment_size=8,
            intra_word_endianness='little',
            multi_word_endianness='big',
        )
        pd.generate_words()
        for w in pd._words:
            self.assertEqual(w.intra_word_endianness, 'little')

    def test_str(self):
        pd = PredefinedDataLine(
            line_id=self.line_id,
            word_count=1,
            value=0x42,
            name='strtest',
            current_memzone=self.memzone,
            word_size=8,
            word_segment_size=8,
            intra_word_endianness='big',
            multi_word_endianness='big',
        )
        s = str(pd)
        self.assertIn('PredefinedDataLine', s)
        self.assertIn('strtest', s)


if __name__ == '__main__':
    unittest.main()
