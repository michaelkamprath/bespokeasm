import unittest
from unittest.mock import Mock

from bespokeasm.docsgen.markdown_generator import MarkdownGenerator


class TestMarkdownGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        # Mock documentation model
        self.mock_doc_model = Mock()
        self.mock_doc_model.isa_name = 'test-isa'
        self.mock_doc_model.isa_description = 'Test ISA Description'
        self.mock_doc_model.isa_identifier_name = None  # Explicitly set to None for tests

        # Default empty documentation with full structure expected by generator
        self.mock_doc_model.general_docs = {
            'description': None,
            'details': None,
            'addressing_modes': [],
            'flags': [],
            'examples': [],
            'hardware': {},
            'endianness': {},
            'string_config': {},
            'registers': [],
            'min_version': None
        }
        self.mock_doc_model.instruction_docs = {}
        self.mock_doc_model.operand_sets = []

    def test_generate_header_only(self):
        """Test generating document with only header."""
        self.mock_doc_model.isa_description = None
        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)

        result = generator.generate()

        # Should include general information section per new requirements
        self.assertIn('# test-isa', result)
        self.assertIn('## General Information', result)

    def test_generate_header_with_description(self):
        """Test generating document header with description."""
        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)

        result = generator.generate()

        # Should include general information section per new requirements
        self.assertIn('# test-isa', result)
        self.assertIn('Test ISA Description', result)
        self.assertIn('## General Information', result)

    def test_generate_with_general_documentation(self):
        """Test generating document with general documentation."""
        self.mock_doc_model.general_docs = {
            'description': 'Test ISA Description',
            'details': 'This is a detailed description\nwith multiple lines.',
            'addressing_modes': [
                {
                    'name': 'immediate',
                    'description': 'Immediate addressing',
                    'details': 'Load value directly'
                },
                {
                    'name': 'register',
                    'description': 'Register addressing',
                    'details': None
                }
            ],
            'flags': [
                {
                    'name': 'carry',
                    'symbol': 'C',
                    'description': 'Carry flag',
                    'details': 'Set on overflow'
                },
                {
                    'name': 'zero',
                    'symbol': None,
                    'description': 'Zero flag',
                    'details': None
                }
            ],
            'examples': [
                {
                    'description': 'Basic example',
                    'details': 'This shows basic usage',
                    'code': 'lda #5\nsta $10'
                }
            ],
            'registers': [
                {
                    'name': 'A',
                    'title': 'Accumulator',
                    'description': 'Primary register.',
                    'size': 8
                },
                {
                    'name': 'X',
                    'title': None,
                    'description': None,
                    'details': None,
                    'size': None
                }
            ]
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        # Verify structure
        self.assertIn('# test-isa', result)
        self.assertIn('Test ISA Description', result)
        self.assertIn('## General Information', result)
        self.assertIn('This is a detailed description\nwith multiple lines.', result)

        # Verify addressing modes table
        self.assertIn('### Addressing Modes', result)
        self.assertIn('| Mode | Description | Details |', result)
        self.assertIn('| `immediate` | Immediate addressing | Load value directly |', result)
        self.assertIn('| `register` | Register addressing |  |', result)

        # Verify flags table
        self.assertIn('### Flags', result)
        self.assertIn('| Name | Symbol | Description | Details |', result)
        self.assertIn('| carry | `C` | Carry flag | Set on overflow |', result)
        self.assertIn('| zero |  | Zero flag |  |', result)

        # Verify examples
        self.assertIn('### Examples', result)
        self.assertIn('#### Basic example', result)
        self.assertIn('This shows basic usage', result)
        self.assertIn('```assembly\nlda #5\nsta $10\n```', result)

        # Verify registers table
        self.assertIn('### Register Set', result)
        self.assertIn('| Symbol | Title | Description | Bit Size |', result)
        self.assertIn('| `A` | Accumulator | Primary register. | 8 |', result)
        self.assertIn('| `X` |  |  |  |', result)

    def test_generate_register_table_with_documentation(self):
        """Registers with documentation produce a table with optional columns."""
        self.mock_doc_model.general_docs['registers'] = [
            {
                'name': 'A',
                'title': 'Accumulator',
                'description': 'Primary working register.',
                'size': 8
            },
            {
                'name': 'SP',
                'title': 'Stack Pointer',
                'description': 'Manages stack pointer.',
                'details': None,
                'size': 16
            },
            {
                'name': 'X',
                'title': None,
                'description': None,
                'details': None,
                'size': None
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('### Register Set', result)
        self.assertIn('| Symbol | Title | Description | Bit Size |', result)
        self.assertIn('| `A` | Accumulator | Primary working register. | 8 |', result)
        self.assertIn('| `SP` | Stack Pointer | Manages stack pointer. | 16 |', result)
        self.assertIn('| `X` |  |  |  |', result)

    def test_generate_register_table_with_names_only(self):
        """Registers without documentation fall back to a name-only table."""
        self.mock_doc_model.general_docs['registers'] = [
            {
                'name': 'A',
                'title': None,
                'description': None,
                'details': None,
                'size': None
            },
            {
                'name': 'B',
                'title': None,
                'description': None,
                'details': None,
                'size': None
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('### Register Set', result)
        self.assertIn('| Symbol |', result)
        self.assertIn('| `A` |', result)
        self.assertIn('| `B` |', result)

    def test_generate_with_operand_sets(self):
        """Operand sets render as their own section with per-operand tables."""
        self.mock_doc_model.operand_sets = [
            {
                'key': 'register_operands',
                'title': 'General Registers',
                'category': 'Registers',
                'description': 'General purpose registers.',
                'details': 'Used for arithmetic operations.',
                'config_index': 0,
                'operands': [
                    {
                        'name': 'reg_a',
                        'title': 'Register A',
                        'syntax': 'a',
                        'mode': 'Register',
                        'mode_from_doc': True,
                        'description': 'Accumulator',
                        'details': 'Primary register.'
                    },
                    {
                        'name': 'reg_b',
                        'title': 'Register B',
                        'syntax': 'b',
                        'mode': 'Register',
                        'mode_from_doc': True,
                        'description': 'Index register',
                        'details': None
                    }
                ]
            },
            {
                'key': 'zero_page',
                'title': None,
                'category': None,
                'description': 'Undocumented operand set zero_page.',
                'details': None,
                'config_index': 1,
                'operands': [
                    {
                        'name': 'zp_addr',
                        'syntax': 'numeric_expression',
                        'mode': 'Address',
                        'mode_from_doc': False,
                        'description': None,
                        'details': 'Valid within `ZERO_PAGE` memory zone.'
                    }
                ]
            },
            {
                'key': 'enum_values',
                'title': 'Enumerated Values',
                'category': None,
                'description': 'Undocumented operand set enum_values.',
                'details': None,
                'config_index': 2,
                'operands': [
                    {
                        'name': 'enum',
                        'syntax': 'integer',
                        'mode': 'Numeric Enumeration',
                        'mode_from_doc': False,
                        'description': None,
                        'details': 'Possible values: `0`, `1`, `2`.'
                    }
                ]
            },
            {
                'key': 'memory_operands',
                'title': 'Memory Operands',
                'category': None,
                'description': 'Undocumented operand set memory_operands.',
                'details': None,
                'config_index': 3,
                'operands': [
                    {
                        'name': 'defered_indexed_x',
                        'title': 'Indirect Indexed Memory Value',
                        'syntax': '[x + [numeric_expression]]',
                        'mode': 'indirect_indexed',
                        'mode_from_doc': True,
                        'description': None,
                        'details': None
                    }
                ]
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Operand Sets', result)
        self.assertIn('### `register_operands` - General Registers', result)
        self.assertIn('*Category: Registers*', result)
        self.assertIn('General purpose registers.', result)
        self.assertIn('Used for arithmetic operations.', result)
        self.assertIn('| Register A (`reg_a`) | `a` | `Register` | Accumulator | Primary register. |', result)
        self.assertIn('[Addressing Mode](#addressing-modes)', result)
        self.assertIn('| Register B (`reg_b`) | `b` | `Register` | Index register |  |', result)
        self.assertIn('### `enum_values` - Enumerated Values', result)
        self.assertIn('| `enum` | `integer` | Numeric Enumeration | Possible values: `0`, `1`, `2`. |', result)
        self.assertIn('### `memory_operands` - Memory Operands', result)
        self.assertIn(
            '| Indirect Indexed Memory Value (`defered_indexed_x`) | `[x + [numeric_expression]]` | `indirect_indexed` |',
            result
        )
        self.assertIn('### `zero_page`', result)
        self.assertIn('Undocumented operand set zero_page.', result)
        self.assertIn('| `zp_addr` | `numeric_expression` | Address | Valid within `ZERO_PAGE` memory zone. |', result)

    def test_generate_with_instruction_documentation(self):
        """Test generating document with instruction documentation."""
        self.mock_doc_model.instruction_docs = {
            'lda': {
                'category': 'Data Movement',
                'title': 'Load accumulator',
                'details': 'Load a value into the accumulator register',
                'modifies': [
                    {
                        'type': 'register',
                        'target': 'A',
                        'description': 'Loaded with operand value',
                        'details': None
                    },
                    {
                        'type': 'flag',
                        'target': 'Z',
                        'description': 'Set if result is zero',
                        'details': 'Zero flag behavior'
                    }
                ],
                'examples': [
                    {
                        'description': 'Load immediate',
                        'details': 'Load the value 42',
                        'code': 'lda #42'
                    }
                ]
            },
            'add': {
                'category': 'Arithmetic',
                'title': 'Add to accumulator',
                'details': None,
                'modifies': [],
                'examples': []
            },
            'sta': {
                'category': 'Data Movement',
                'title': 'Store accumulator',
                'details': None,
                'modifies': [],
                'examples': []
            }
        }

        # Mock the get_instructions_by_category method
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Arithmetic': ['add'],
            'Data Movement': ['lda', 'sta']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        # Verify overall structure
        self.assertIn('# test-isa', result)
        self.assertIn('# Instructions', result)

        # Verify categories (should be alphabetical)
        arithmetic_pos = result.find('## Arithmetic')
        data_movement_pos = result.find('## Data Movement')
        self.assertLess(arithmetic_pos, data_movement_pos)

        # Verify instruction headers
        self.assertIn('### `ADD` : Add to accumulator', result)
        self.assertIn('### `LDA` : Load accumulator', result)
        self.assertIn('### `STA` : Store accumulator', result)

        # Verify detailed instruction content
        self.assertIn('Load a value into the accumulator register', result)

        # Verify modifies table
        self.assertIn('#### Modifies', result)
        self.assertIn('| Type | Target | Description | Details |', result)
        self.assertIn('| Register | A | Loaded with operand value |  |', result)
        self.assertIn('| Flag | Z | Set if result is zero | Zero flag behavior |', result)

        # Verify examples
        self.assertIn('#### Examples', result)
        self.assertIn('##### Load immediate', result)
        self.assertIn('Load the value 42', result)
        self.assertIn('```assembly\nlda #42\n```', result)

    def test_generate_with_undocumented_instructions(self):
        """Instructions without documentation still produce placeholders."""
        self.mock_doc_model.instruction_docs = {
            'nop': {
                'category': 'Uncategorized',
                'title': None,
                'details': None,
                'modifies': [],
                'examples': [],
                'documented': False
            }
        }
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Uncategorized': ['nop']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('# Instructions', result)
        self.assertIn('### `NOP`', result)
        self.assertIn('*Documentation not provided.*', result)

    def test_generate_empty_instruction_documentation(self):
        """Test generating document with no instruction documentation."""
        generator = MarkdownGenerator(self.mock_doc_model, verbose=1)

        with unittest.mock.patch('click.echo') as mock_echo:
            result = generator.generate()

            # Should warn about no instruction documentation
            mock_echo.assert_called_with('Warning: No instruction documentation found')

        # Should still have header
        self.assertIn('# test-isa', result)
        self.assertNotIn('# Instructions', result)

    def test_markdown_escaping_in_tables(self):
        """Test that newlines in table cells are properly escaped."""
        self.mock_doc_model.general_docs = {
            'description': None,
            'details': None,
            'addressing_modes': [
                {
                    'name': 'test',
                    'description': 'Line 1\nLine 2',
                    'details': 'Detail 1\nDetail 2'
                }
            ],
            'flags': [
                {
                    'name': 'test_flag',
                    'symbol': 'T',
                    'description': 'Flag line 1\nFlag line 2',
                    'details': 'Flag detail 1\nFlag detail 2'
                }
            ],
            'examples': []
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        # Verify newlines are converted to <br> in table cells
        self.assertIn('| `test` | Line 1<br>Line 2 | Detail 1<br>Detail 2 |', result)
        self.assertIn('| test_flag | `T` | Flag line 1<br>Flag line 2 | Flag detail 1<br>Flag detail 2 |', result)

    def test_modifies_table_without_details_column(self):
        """Test that modifies table omits Details column when no entries have details."""
        self.mock_doc_model.instruction_docs = {
            'nop': {
                'category': 'Operations',
                'title': 'No operation',
                'details': None,
                'modifies': [
                    {
                        'type': 'register',
                        'target': 'pc',
                        'description': 'Incremented',
                        'details': None
                    },
                    {
                        'type': 'flag',
                        'target': 'cycles',
                        'description': 'Consumed',
                        'details': None
                    }
                ],
                'examples': []
            }
        }

        # Mock the get_instructions_by_category method
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Operations': ['nop']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        # Verify modifies table has only 3 columns (no Details column)
        self.assertIn('| Type | Target | Description |', result)
        self.assertNotIn('| Type | Target | Description | Details |', result)
        self.assertIn('| Register | pc | Incremented |', result)
        self.assertIn('| Flag | cycles | Consumed |', result)

    def test_modifies_table_with_details_column(self):
        """Test that modifies table includes Details column when at least one entry has details."""
        self.mock_doc_model.instruction_docs = {
            'lda': {
                'category': 'Data Movement',
                'title': 'Load accumulator',
                'details': None,
                'modifies': [
                    {
                        'type': 'register',
                        'target': 'A',
                        'description': 'Loaded with value',
                        'details': None
                    },
                    {
                        'type': 'flag',
                        'target': 'Z',
                        'description': 'Set if zero',
                        'details': 'Detailed flag behavior'
                    }
                ],
                'examples': []
            }
        }

        # Mock the get_instructions_by_category method
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Data Movement': ['lda']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        # Verify modifies table has 4 columns (includes Details column)
        self.assertIn('| Type | Target | Description | Details |', result)
        self.assertIn('| Register | A | Loaded with value |  |', result)
        self.assertIn('| Flag | Z | Set if zero | Detailed flag behavior |', result)

    def test_has_general_documentation(self):
        """Test the _has_general_documentation method."""
        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)

        # Per new requirements, always show general section (contains config details)
        self.assertTrue(generator._has_general_documentation())

        # With details
        self.mock_doc_model.general_docs['details'] = 'Some details'
        self.assertTrue(generator._has_general_documentation())

        # Reset and test with addressing modes
        self.mock_doc_model.general_docs['details'] = None
        self.mock_doc_model.general_docs['addressing_modes'] = [{'name': 'test'}]
        self.assertTrue(generator._has_general_documentation())

        # Reset and test with flags
        self.mock_doc_model.general_docs['addressing_modes'] = []
        self.mock_doc_model.general_docs['flags'] = [{'name': 'test'}]
        self.assertTrue(generator._has_general_documentation())

        # Reset and test with examples
        self.mock_doc_model.general_docs['flags'] = []
        self.mock_doc_model.general_docs['examples'] = [{'code': 'test'}]
        self.assertTrue(generator._has_general_documentation())


if __name__ == '__main__':
    unittest.main()
