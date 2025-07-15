import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.bytecode.assembled import AssembledInstruction
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart, ExpressionByteCodePart, CompositeByteCodePart
from bespokeasm.assembler.label_scope import GlobalLabelScope


class TestBytecodeObjects(unittest.TestCase):

    def test_bytecode_assembly(self):
        test_line_id = LineIdentifier(88, 'test_bytecode_assembly')
        register_labels = {'a', 'i'}
        label_values = GlobalLabelScope(register_labels)
        label_values.set_label_value('var1', 2, 1)
        label_values.set_label_value('var2', 0xF0, 2)

        test_line_id = LineIdentifier(42, 'test_bytecode_assembly')
        parts1 = [
            NumericByteCodePart(15, 4, True, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(3, 2, False, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(3, 2, False, 'big', 'big', test_line_id, 8, 8),
        ]

        ai1 = AssembledInstruction(123, parts1, 8, 8, 'big', 'big')
        self.assertEqual(ai1.word_count, 1)
        words1 = ai1.get_words(label_values, 0x8000, 1)
        self.assertEqual(words1, [Word(0xff, 8, 8, 'big')], 'generated words should match')

        parts2 = [
            NumericByteCodePart(8, 4, True, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(0x1122, 16, True, 'little', 'little', test_line_id, 8, 8),
            NumericByteCodePart(0x11223344, 32, True, 'little', 'little', test_line_id, 8, 8),
            NumericByteCodePart(0x8, 4, False, 'big', 'big', test_line_id, 8, 8),
        ]

        ai2 = AssembledInstruction(456, parts2, 8, 8, 'big', 'big')
        self.assertEqual(ai2.word_count, 8)
        words2 = ai2.get_words(label_values, 0x8000, 8)
        self.assertEqual(
            words2,
            [
                Word(0x80, 8, 8, 'big'),
                Word(0x22, 8, 8, 'little'),
                Word(0x11, 8, 8, 'little'),
                Word(0x44, 8, 8, 'little'),
                Word(0x33, 8, 8, 'little'),
                Word(0x22, 8, 8, 'little'),
                Word(0x11, 8, 8, 'little'),
                Word(0x80, 8, 8, 'big'),
            ],
            'generated words should match'
        )

    def test_composite_bytecode_part(self):
        test_line_id = LineIdentifier(88, 'test_composite_bytecode_part')
        register_labels = {'a', 'i'}
        label_values = GlobalLabelScope(register_labels)
        label_values.set_label_value('var1', 2, 1)
        label_values.set_label_value('var2', 0xF0, 2)

        p1 = NumericByteCodePart(1, 3, True, 'big', 'big', test_line_id, 8, 8)
        p2 = NumericByteCodePart(3, 2, True, 'big', 'big', test_line_id, 8, 8)
        p3 = ExpressionByteCodePart('var1+13', 4, True, 'big', 'big', test_line_id, 8, 8)

        c1 = CompositeByteCodePart([p1, p2], False, 'big', 'big', test_line_id, 8, 8)
        self.assertEqual(5, c1.value_size, 'bit size should match')
        self.assertEqual(7, c1.get_value(label_values, 0x8000, 5), 'value should match')

        c2 = CompositeByteCodePart([p2, p1], False, 'big', 'big', test_line_id, 8, 8)
        self.assertEqual(5, c2.value_size, 'bit size should match')
        self.assertEqual(25, c2.get_value(label_values, 0x8000, 5), 'value should match')

        c3 = CompositeByteCodePart([p1, p2, p3], False, 'big', 'big', test_line_id, 8, 8)
        self.assertEqual(9, c3.value_size, 'bit size should match')
        self.assertEqual(127, c3.get_value(label_values, 0x8000, 9), 'value should match')

        c4 = CompositeByteCodePart([p1, p2, p1], False, 'big', 'big', test_line_id, 8, 8)
        self.assertEqual(8, c4.value_size, 'bit size should match')
        self.assertEqual(57, c4.get_value(label_values, 0x8000, 8), 'value should match')

    def test_compact_parts_to_words(self):
        test_line_id = LineIdentifier(1, 'test_compact_parts_to_words')
        register_labels = {'a', 'i'}
        label_values = GlobalLabelScope(register_labels)

        parts = [
            NumericByteCodePart(1, 4, False, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(2, 4, False, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(3, 4, False, 'big', 'big', test_line_id, 8, 8),
        ]

        words = CompositeByteCodePart.compact_parts_to_words(parts, 8, 8, 'big', label_values, 0x8000, 1)
        self.assertEqual(
            words,
            [Word(0x12, 8, 8, 'big'), Word(0x30, 8, 8, 'big')],
            'words should match',
        )

        # 16 bit version
        test_line_id = LineIdentifier(2, 'test_compact_parts_to_words')
        parts = [
            NumericByteCodePart(1, 4, False, 'big', 'big', test_line_id, 16, 8),
            NumericByteCodePart(2, 8, False, 'big', 'big', test_line_id, 16, 8),
            NumericByteCodePart(3, 4, False, 'big', 'big', test_line_id, 16, 8),
        ]
        words = CompositeByteCodePart.compact_parts_to_words(parts, 16, 8, 'big', label_values, 0x8000, 1)
        self.assertEqual(
            words,
            [Word(0x1023, 16, 8, 'big')],
            'words should match',
        )

        # 32 bit version
        test_line_id = LineIdentifier(3, 'test_compact_parts_to_words')
        parts = [
            NumericByteCodePart(1, 4, False, 'big', 'big', test_line_id, 32, 8),
            NumericByteCodePart(2, 16, False, 'big', 'big', test_line_id, 32, 8),
            NumericByteCodePart(3, 8, False, 'big', 'big', test_line_id, 32, 8),
        ]
        words = CompositeByteCodePart.compact_parts_to_words(parts, 32, 8, 'big', label_values, 0x8000, 1)
        self.assertEqual(
            words,
            [Word(0x10002030, 32, 8, 'big')],
            'words should match',
        )

    def test_bytecode_assembly_16bit_word(self):
        register_labels = {'a', 'i'}
        label_values = GlobalLabelScope(register_labels)
        label_values.set_label_value('var1', 2, 1)
        label_values.set_label_value('var2', 0xF0, 2)

        test_line_id = LineIdentifier(1, 'test_bytecode_assembly_16bit_word')
        parts1 = [
            NumericByteCodePart(15, 4, True, 'big', 'big', test_line_id, 16, 8),
            NumericByteCodePart(3, 2, False, 'big', 'big', test_line_id, 16, 8),
            NumericByteCodePart(3, 2, False, 'big', 'big', test_line_id, 16, 8),
        ]

        ai1 = AssembledInstruction(
            test_line_id,
            parts1,
            16,
            8,
            'big',
            'big',
        )
        self.assertEqual(ai1.word_count, 1)
        words1 = ai1.get_words(label_values, 0x8000, 1)
        self.assertEqual(words1, [Word(0xff00, 16, 8, 'big')], 'generated words should match')

        test_line_id = LineIdentifier(2, 'test_bytecode_assembly_16bit_word')
        parts2 = [
            NumericByteCodePart(8, 4, True, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(0x1122, 16, True, 'big', 'big', test_line_id, 8, 8),
            NumericByteCodePart(0x11223344, 32, True, 'little', 'little', test_line_id, 8, 8),
            NumericByteCodePart(0x8, 4, False, 'little', 'little', test_line_id, 8, 8),
        ]

        ai2 = AssembledInstruction(
            test_line_id,
            parts2,
            16,
            8,
            'big',
            'big',
        )
        self.assertEqual(ai2.word_count, 5)
        words2 = ai2.get_words(label_values, 0x8000, 8)
        self.assertEqual(
            words2,
            [
                # These are Word values, so intra-word segment endian is not shown here
                Word(0x8000, 16, 8, 'big'),
                Word(0x1122, 16, 8, 'big'),
                Word(0x3344, 16, 8, 'little'),
                Word(0x1122, 16, 8, 'little'),
                Word(0x8000, 16, 8, 'little'),
            ],
            'generated words should match'
        )
        self.assertEqual(
            # this is where intra-word segment endian is honored
            Word.words_to_bytes(words2, False, 'big'),
            b'\x80\x00\x11\x22\x44\x33\x22\x11\x00\x80',
            'ensure segment endian is honored when converting to bytes'
        )
