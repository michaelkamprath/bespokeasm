import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction import InstructionVariant


class TestInstructionVariant(unittest.TestCase):
    def setUp(self):
        self.defaults = {
            'mnemonic': 'OP',
            # Use a MagicMock so variants can reference operand collection without invoking real parsing logic.
            'operand_sets': MagicMock(),
            'default_multi_word_endian': 'big',
            'default_intra_word_endian': 'little',
            'registers': set(),
            'word_size': 8,
            'word_segment_size': 8,
        }

    def _make_variant(self, config, variant_num=0):
        return InstructionVariant(
            self.defaults['mnemonic'],
            config,
            self.defaults['operand_sets'],
            self.defaults['default_multi_word_endian'],
            self.defaults['default_intra_word_endian'],
            self.defaults['registers'],
            variant_num,
            self.defaults['word_size'],
            self.defaults['word_segment_size'],
        )

    def test_variant_requires_bytecode_for_base(self):
        # Base variant must define bytecode or initialization aborts.
        with self.assertRaisesRegex(SystemExit, 'does not have a byte code configuration'):
            self._make_variant({}, variant_num=0)

    def test_variant_requires_bytecode_for_additional(self):
        # Non-zero variants also require bytecode definitions.
        with self.assertRaisesRegex(SystemExit, 'byte code configuration in variant 1'):
            self._make_variant({}, variant_num=1)

    def test_variant_initializes_operand_parser(self):
        # Valid operand config should create and validate an OperandParser.
        parser_instance = MagicMock()  # Stub parser so we can verify construction/validation calls.
        parser_instance.operand_count = 2
        with patch(
            'bespokeasm.assembler.model.instruction.OperandParser',
            return_value=parser_instance,
        ) as mock_parser:
            variant = self._make_variant({'bytecode': {'size': 1, 'value': 0x55}, 'operands': {'list': ['A']}})
        mock_parser.assert_called_once()
        parser_instance.validate.assert_called_once_with('OP')
        self.assertEqual(variant.operand_count, 2)
        self.assertIn('InstructionVariant<', str(variant))

    def test_variant_operand_parser_type_error(self):
        # Force OperandParser creation to raise so we can confirm the error is surfaced via SystemExit.
        with patch(
            'bespokeasm.assembler.model.instruction.OperandParser',
            side_effect=TypeError('bad config'),
        ):
            with self.assertRaisesRegex(SystemExit, 'bad config'):
                self._make_variant({'bytecode': {'size': 1, 'value': 0x55}, 'operands': {}})

    def test_variant_base_bytecode_properties(self):
        # Exercise bytecode size/value/suffix accessors and __str__.
        config = {'bytecode': {'size': 1, 'value': 0x33, 'suffix': {'size': 1, 'value': 0x44}}}
        variant = self._make_variant(config)
        self.assertEqual(variant.base_bytecode_size, 1)
        self.assertEqual(variant.base_bytecode_value, 0x33)
        self.assertTrue(variant.has_bytecode_suffix)
        self.assertEqual(variant.suffix_bytecode_size, 1)
        self.assertEqual(variant.suffix_bytecode_value, 0x44)
        self.assertIn('InstructionVariant<', str(variant))

    def test_variant_missing_size_and_value_raise(self):
        # Omitting size or value should exit with descriptive messages.
        variant = self._make_variant({'bytecode': {'value': 0x11}})
        with self.assertRaisesRegex(SystemExit, 'bytecode size'):
            _ = variant.base_bytecode_size
        variant = self._make_variant({'bytecode': {'size': 1}})
        with self.assertRaisesRegex(SystemExit, 'bytecode value'):
            _ = variant.base_bytecode_value


class TestInstruction(unittest.TestCase):
    def setUp(self):
        self.defaults = {
            'mnemonic': 'OP',
            # MagicMock lets Instruction pass an operand set collection without touching real data.
            'operand_sets': MagicMock(),
            'default_multi_word_endian': 'big',
            'default_intra_word_endian': 'little',
            'registers': set(),
            'word_size': 8,
            'word_segment_size': 8,
        }

    def _make_instruction(self, config):
        return Instruction(
            self.defaults['mnemonic'],
            config,
            self.defaults['operand_sets'],
            self.defaults['default_multi_word_endian'],
            self.defaults['default_intra_word_endian'],
            self.defaults['registers'],
            self.defaults['word_size'],
            self.defaults['word_segment_size'],
        )

    def test_instruction_collects_variants(self):
        # Verify base and additional variant configs are wrapped into InstructionVariant objects.
        # Patch InstructionVariant so we can record each instantiation without relying on its implementation.
        base_config = {'bytecode': {'size': 1, 'value': 0x10}}
        extra_variant = {'bytecode': {'size': 1, 'value': 0x11}}
        with patch('bespokeasm.assembler.model.instruction.InstructionVariant', side_effect=['base', 'alt']) as mock_variant:
            # side_effect list returns 'base' for the first (default) variant and 'alt' for the extra entry.
            instruction = self._make_instruction({**base_config, 'variants': [extra_variant]})
        self.assertEqual(instruction.variants, ['base', 'alt'])
        self.assertIn('Instruction<OP>', str(instruction))
        self.assertEqual(mock_variant.call_count, 2)

    def test_instruction_requires_variant(self):
        # If the instruction config supplies no bytecode/variants, construction should abort.
        with self.assertRaisesRegex(SystemExit, 'has no valid variant'):
            self._make_instruction({})
