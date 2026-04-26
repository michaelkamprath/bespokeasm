import os
import tempfile
import unittest

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.model import AssemblerModel
from ruamel.yaml import YAML


class TestAssemblerModelDefaults(unittest.TestCase):
    def setUp(self):
        # Minimal config with only required fields
        self.minimal_config = {
            'general': {
                'address_size': 16,
                'min_version': '0.7.0',
                'instructions': {},
                'operand_sets': {},
            },
            'instructions': {},
            'operand_sets': {},
        }
        # Save to YAML for AssemblerModel
        self.yaml = YAML()
        self.tempfile = tempfile.NamedTemporaryFile('w+', delete=False, suffix='.yaml')
        self.yaml.dump(self.minimal_config, self.tempfile)
        self.tempfile.flush()
        self.diagnostic_reporter = DiagnosticReporter()

    def tearDown(self):
        self.tempfile.close()
        os.unlink(self.tempfile.name)

    def test_defaults(self):
        model = AssemblerModel(self.tempfile.name, 0, self.diagnostic_reporter)
        self.assertFalse(model.string_byte_packing, 'string_byte_packing should default to False')
        self.assertEqual(model.string_byte_packing_fill, 0, 'string_byte_packing_fill should default to 0')
        self.assertEqual(model.cstr_terminator, 0, 'cstr_terminator should default to 0')
        self.assertEqual(model.word_size, 8, 'word_size should default to 8')
        self.assertEqual(model.word_segment_size, 8, 'word_segment_size should default to word_size (8)')
        self.assertEqual(model.multi_word_endianness, 'big', 'multi_word_endianness should default to big')
        self.assertEqual(model.intra_word_endianness, 'big', 'intra_word_endianness should default to big')
        self.assertEqual(model.page_size, 1, 'page_size should default to 1')
        self.assertFalse(model.allow_embedded_strings, 'allow_embedded_strings should default to False')
        self.assertEqual(model.default_numeric_base, 'decimal', 'default_numeric_base should default to decimal')
        # min_version should exist in config
        self.assertIn('min_version', model._config['general'], 'min_version should be set in config')

    def test_set_values_for_string_byte_packing(self):
        # Write config with all options set
        config = {
            'general': {
                'address_size': 16,
                'word_size': 16,  # Added to satisfy string_byte_packing validation
                'string_byte_packing': True,
                'string_byte_packing_fill': 0xAB,
                'cstr_terminator': 0x55,
                'min_version': '0.7.0',
            },
            'instructions': {},
            'operand_sets': {},
        }
        temp = tempfile.NamedTemporaryFile('w+', delete=False, suffix='.yaml')
        self.yaml.dump(config, temp)
        temp.flush()
        model = AssemblerModel(temp.name, 0, self.diagnostic_reporter)
        self.assertTrue(model.string_byte_packing, 'string_byte_packing should be True when set')
        self.assertEqual(model.string_byte_packing_fill, 0xAB, 'string_byte_packing_fill should match config')
        self.assertEqual(model.cstr_terminator, 0x55, 'cstr_terminator should match config')
        temp.close()
        os.unlink(temp.name)

    def test_default_numeric_base_aliases(self):
        config = {
            'general': {
                'address_size': 16,
                'min_version': '0.7.0',
                'default_numeric_base': 'base16',
            },
            'instructions': {},
            'operand_sets': {},
        }
        temp = tempfile.NamedTemporaryFile('w+', delete=False, suffix='.yaml')
        self.yaml.dump(config, temp)
        temp.flush()
        model = AssemblerModel(temp.name, 0, self.diagnostic_reporter)
        self.assertEqual(model.default_numeric_base, 'hex', 'default_numeric_base aliases normalize to canonical values')
        temp.close()
        os.unlink(temp.name)

    def test_default_numeric_base_rejects_ambiguous_register_names(self):
        config = {
            'general': {
                'address_size': 16,
                'min_version': '0.7.0',
                'default_numeric_base': 'hex',
                'registers': ['b'],
            },
            'instructions': {},
            'operand_sets': {},
        }
        temp = tempfile.NamedTemporaryFile('w+', delete=False, suffix='.yaml')
        self.yaml.dump(config, temp)
        temp.flush()
        with self.assertRaisesRegex(SystemExit, 'ambiguous with a bare hex numeric literal'):
            AssemblerModel(temp.name, 0, self.diagnostic_reporter)
        temp.close()
        os.unlink(temp.name)

    def test_default_numeric_base_rejects_ambiguous_predefined_names(self):
        test_cases = [
            (
                {
                    'general': {
                        'address_size': 16,
                        'min_version': '0.7.0',
                        'default_numeric_base': 'hex',
                    },
                    'predefined': {
                        'constants': [{'name': 'face', 'value': 1}],
                    },
                    'instructions': {},
                    'operand_sets': {},
                },
                'predefined constant name "face"',
            ),
            (
                {
                    'general': {
                        'address_size': 16,
                        'min_version': '0.7.0',
                        'default_numeric_base': 'binary',
                    },
                    'predefined': {
                        'data': [{'name': '1010', 'address': 0, 'size': 1}],
                    },
                    'instructions': {},
                    'operand_sets': {},
                },
                'predefined data label "1010"',
            ),
            (
                {
                    'general': {
                        'address_size': 16,
                        'min_version': '0.7.0',
                        'default_numeric_base': 'octal',
                    },
                    'predefined': {
                        'symbols': [{'name': '17', 'value': 'ENABLED'}],
                    },
                    'instructions': {},
                    'operand_sets': {},
                },
                'predefined preprocessor symbol name "17"',
            ),
        ]

        for config, expected_error in test_cases:
            with self.subTest(expected_error=expected_error):
                temp = tempfile.NamedTemporaryFile('w+', delete=False, suffix='.yaml')
                self.yaml.dump(config, temp)
                temp.flush()
                with self.assertRaisesRegex(SystemExit, expected_error):
                    AssemblerModel(temp.name, 0, self.diagnostic_reporter)
                temp.close()
                os.unlink(temp.name)


if __name__ == '__main__':
    unittest.main()
