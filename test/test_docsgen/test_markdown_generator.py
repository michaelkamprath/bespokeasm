import unittest
from unittest.mock import Mock

from bespokeasm.docsgen.documentation_model import DocumentationModel
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
        self.mock_doc_model.predefined_memory_zones = []
        self.mock_doc_model.predefined_constants = []
        self.mock_doc_model.predefined_data = []
        self.mock_doc_model.macro_docs = {}
        self.mock_doc_model.get_macros_by_category = Mock(return_value={})

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
            'addressing_modes': [
                {
                    'name': 'immediate',
                    'title': 'Immediate addressing',
                    'description': 'Load value directly'
                },
                {
                    'name': 'register',
                    'title': 'Register addressing'
                }
            ],
            'flags': [
                {
                    'name': 'carry',
                    'symbol': 'C',
                    'description': 'Carry flag'
                },
                {
                    'name': 'zero',
                    'symbol': None,
                    'description': 'Zero flag'
                }
            ],
            'examples': [
                {
                    'title': 'Basic example',
                    'description': 'This shows basic usage',
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

        # Verify addressing modes table
        self.assertIn('### Addressing Modes', result)
        self.assertIn('| Mode | Title | Description |', result)
        self.assertIn('| `immediate` | Immediate addressing | Load value directly |', result)
        self.assertIn('| `register` | Register addressing |  |', result)

        # Verify flags table
        self.assertIn('### Flags', result)
        self.assertIn('| Name | Symbol | Description |', result)
        self.assertIn('| carry | `C` | Carry flag |', result)
        self.assertIn('| zero |  | Zero flag |', result)

        # Verify examples
        self.assertIn('# Examples', result)
        self.assertIn('## Basic example', result)
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
                'size': 16
            },
            {
                'name': 'X',
                'title': None,
                'description': None,
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
                'size': None
            },
            {
                'name': 'B',
                'title': None,
                'description': None,
                'size': None
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('### Register Set', result)
        self.assertIn('| Symbol |', result)

    def test_generate_predefined_memory_zones_with_documentation(self):
        """Predefined memory zones render with documentation and hex ranges."""
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16
            }
        }
        self.mock_doc_model.predefined_memory_zones = [
            {
                'name': 'ZERO_PAGE',
                'start': 0,
                'end': 255,
                'title': 'Zero Page',
                'description': 'Fast access memory.',
                'documented': True
            },
            {
                'name': 'ROM',
                'start': '0x8000',
                'end': '0xFFFF',
                'title': None,
                'description': 'Read-only memory.',
                'documented': True
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Predefined Memory Zones', result)
        self.assertIn('| Name | Start | End | Title | Description |', result)
        self.assertIn('| `ZERO_PAGE` | 0x0000 | 0x00FF | Zero Page | Fast access memory. |', result)
        self.assertIn('| `ROM` | 0x8000 | 0xFFFF | ROM | Read-only memory. |', result)

    def test_generate_instruction_markdown_with_documentation(self):
        """Instruction markdown includes headers, syntax, modifies, and examples."""
        instruction_doc = {
            'documented': True,
            'title': 'Load Accumulator',
            'description': 'Loads a value into the accumulator.',
            'versions': [
                {
                    'index': 1,
                    'documented': True,
                    'signatures': [
                        {
                            'operands': [
                                {
                                    'name': 'src',
                                    'type': 'register',
                                    'syntax': 'r',
                                    'value': 'register `A`',
                                    'description': 'Source register.',
                                    'include_in_code': True
                                }
                            ]
                        }
                    ]
                }
            ],
            'modifies': [
                {
                    'type': 'register',
                    'target': 'A',
                    'description': 'Updated with source value.'
                }
            ],
            'examples': [
                {
                    'title': 'Simple load',
                    'code': 'lda a'
                }
            ]
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate_instruction_markdown('lda', instruction_doc, add_header_rule=True)

        self.assertIn('### `LDA` : Load Accumulator', result)
        self.assertIn('---', result)
        self.assertIn('Loads a value into the accumulator.', result)
        self.assertIn('```asm\nLDA r\n```', result)
        self.assertIn('#### Modifies', result)
        self.assertIn('| Register | A | Updated with source value. |', result)
        self.assertIn('#### Examples', result)
        self.assertIn('```assembly\nlda a\n```', result)

    def test_generate_instruction_markdown_missing_docs(self):
        """Instruction markdown includes missing documentation notice."""
        instruction_doc = {
            'documented': False,
            'versions': [
                {
                    'index': 1,
                    'documented': False,
                    'signatures': [
                        {
                            'operands': []
                        }
                    ]
                }
            ]
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate_instruction_markdown('nop', instruction_doc)

        self.assertIn('### `NOP`', result)
        self.assertIn('Documentation not provided.', result)

    def test_generate_predefined_memory_zones_without_documentation(self):
        """Predefined memory zones omit documentation columns when none are provided."""
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16
            }
        }
        self.mock_doc_model.predefined_memory_zones = [
            {
                'name': 'ZERO_PAGE',
                'start': 0,
                'end': 255,
                'documented': False
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Predefined Memory Zones', result)
        self.assertIn('| Name | Start | End |', result)
        self.assertNotIn('| Name | Start | End | Title | Description |', result)

    def test_generate_predefined_constants_with_documentation(self):
        """Predefined constants render with documentation and hex values."""
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16
            }
        }
        self.mock_doc_model.predefined_constants = [
            {
                'name': '_Start',
                'value': 0x1000,
                'type': 'subroutine',
                'size': None,
                'description': 'Program entry point.',
                'documented': True
            },
            {
                'name': '_Prompt',
                'value': '0x1003',
                'type': 'variable',
                'size': 1,
                'description': 'Text prompt.',
                'documented': True
            },
            {
                'name': '_Vector',
                'value': 0x2000,
                'type': 'address',
                'size': None,
                'description': 'Interrupt vector address.',
                'documented': True
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Predefined Constants', result)
        self.assertIn('| Name | Value | Type | Size (Words) | Description |', result)
        self.assertIn('| `_Start` | 0x1000 | subroutine |  | Program entry point. |', result)
        self.assertIn('| `_Prompt` | 0x1003 | variable | 1 | Text prompt. |', result)
        self.assertIn('| `_Vector` | 0x2000 | address |  | Interrupt vector address. |', result)

    def test_generate_predefined_constants_without_documentation(self):
        """Predefined constants omit documentation columns when none are provided."""
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16
            }
        }
        self.mock_doc_model.predefined_constants = [
            {
                'name': '_Start',
                'value': 0x1000,
                'documented': False
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Predefined Constants', result)
        self.assertIn('| Name | Value |', result)
        self.assertNotIn('| Name | Value | Type | Size (Words) | Description |', result)

    def test_generate_predefined_data_with_documentation(self):
        """Predefined data blocks render with documentation and hex values."""
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16,
                'word_size': 8
            }
        }
        self.mock_doc_model.predefined_data = [
            {
                'name': 'BUFFER',
                'address': 0x10,
                'size': 8,
                'value': 0,
                'description': 'Scratch buffer for input.',
                'documented': True
            },
            {
                'name': 'FLAG',
                'address': '0x20',
                'size': 1,
                'value': None,
                'description': 'Status flag byte.',
                'documented': True
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Predefined Data', result)
        self.assertIn('| Name | Address | Size (Bytes) | Value | Description |', result)
        self.assertIn('| `BUFFER` | 0x0010 | 8 | 0x00 | Scratch buffer for input. |', result)
        self.assertIn('| `FLAG` | 0x0020 | 1 |  | Status flag byte. |', result)

    def test_generate_predefined_data_without_documentation(self):
        """Predefined data blocks omit description column when none are provided."""
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16,
                'word_size': 8
            }
        }
        self.mock_doc_model.predefined_data = [
            {
                'name': 'BUFFER',
                'address': 0x10,
                'size': 8,
                'value': 0,
                'documented': False
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Predefined Data', result)
        self.assertIn('| Name | Address | Size (Bytes) | Value |', result)
        self.assertNotIn('| Name | Address | Size (Bytes) | Value | Description |', result)

    def test_generate_predefined_hover_docs_uses_words_for_non_8bit_word_sizes(self):
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16,
                'word_size': 16,
            }
        }
        self.mock_doc_model.predefined_constants = [
            {
                'name': 'VAR_BUF',
                'value': 0x1000,
                'type': 'variable',
                'size': 2,
                'description': 'Buffer variable.',
                'documented': True,
            }
        ]
        self.mock_doc_model.predefined_data = [
            {
                'name': 'SCREEN',
                'address': 0x4000,
                'size': 4,
                'value': 0,
                'description': 'Screen buffer.',
                'documented': True,
            }
        ]
        self.mock_doc_model.predefined_memory_zones = [
            {
                'name': 'USER_RAM',
                'start': 0x3000,
                'end': 0x7FFF,
                'title': 'User RAM',
                'description': 'User workspace.',
                'documented': True,
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        docs = generator.generate_predefined_hover_docs()

        self.assertIn('VAR_BUF', docs['constants'])
        self.assertIn('### `VAR_BUF` : Predefined Constant', docs['constants']['VAR_BUF'])
        self.assertIn('| **Size** | 2 words |', docs['constants']['VAR_BUF'])
        self.assertIn('### `SCREEN` : Predefined Data Block', docs['data']['SCREEN'])
        self.assertIn('| **Size** | 4 words |', docs['data']['SCREEN'])
        self.assertIn('### `USER_RAM` : User RAM', docs['memory_zones']['USER_RAM'])

    def test_generate_predefined_hover_docs_uses_bytes_for_8bit_words(self):
        self.mock_doc_model.general_docs = {
            'hardware': {
                'address_size': 16,
                'word_size': 8,
            }
        }
        self.mock_doc_model.predefined_constants = [
            {
                'name': 'BUFFER_PTR',
                'value': 0x0010,
                'type': 'variable',
                'size': 1,
                'description': 'Pointer.',
                'documented': True,
            }
        ]
        self.mock_doc_model.predefined_data = [
            {
                'name': 'BUFFER',
                'address': 0x0020,
                'size': 8,
                'value': 0x00,
                'description': 'Byte buffer.',
                'documented': True,
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        docs = generator.generate_predefined_hover_docs()

        self.assertIn('| **Size** | 1 byte |', docs['constants']['BUFFER_PTR'])
        self.assertIn('| **Size** | 8 bytes |', docs['data']['BUFFER'])

    def test_macros_calling_syntax_from_operands(self):
        """Macros render calling syntax using their configured operands."""
        isa_model = Mock()
        isa_model.isa_name = 'macro-isa'
        isa_model._config = {
            'general': {
                'identifier': {'name': 'macro-isa'}
            },
            'operand_sets': {},
            'macros': {
                'push2': {
                    'variants': [
                        {
                            'operands': {
                                'specific_operands': {
                                    'immediate': {
                                        'list': {
                                            'value': {'type': 'numeric'}
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }

        doc_model = DocumentationModel(isa_model, verbose=0)
        generator = MarkdownGenerator(doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('# Macros', result)
        self.assertIn('### `PUSH2`', result)
        self.assertIn('*Calling syntax:*', result)
        self.assertIn('```asm\nPUSH2 value\n```', result)
        self.assertIn('| Operand | Type | Value |', result)

    def test_generate_macros_section(self):
        """Macros are rendered in their own section using instruction-style layout."""
        self.mock_doc_model.macro_docs = {
            'push2': {
                'category': 'Stack',
                'title': 'Push Word',
                'description': 'Push two-byte value.',
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'title': None,
                        'description': None,
                        'signatures': [
                            {
                                'operands': [
                                    {
                                        'name': 'value',
                                        'display_name': 'value',
                                        'type': 'numeric',
                                        'syntax': 'value',
                                        'value': 'numeric expression',
                                        'description': 'word to push',
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ],
                        'modifies': [],
                        'examples': [],
                        'documented': False
                    }
                ]
            }
        }
        self.mock_doc_model.get_macros_by_category = Mock(return_value={'Stack': ['push2']})

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('# Macros', result)
        self.assertIn('## Stack', result)
        self.assertIn('### `PUSH2` : Push Word', result)
        self.assertIn('*Calling syntax:*', result)
        self.assertIn('```asm\nPUSH2 value\n```', result)

    def test_generate_macros_section_without_documentation(self):
        """Macros without documentation omit the placeholder message."""
        self.mock_doc_model.macro_docs = {
            'foo': {
                'category': 'Uncategorized',
                'title': None,
                'description': None,
                'modifies': [],
                'examples': [],
                'documented': False,
                'versions': []
            }
        }
        self.mock_doc_model.get_macros_by_category = Mock(return_value={'Uncategorized': ['foo']})

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('# Macros', result)
        self.assertIn('### `FOO`', result)
        self.assertNotIn('*Documentation not provided.*', result)

    def test_generate_with_operand_sets(self):
        """Operand sets render as their own section with per-operand tables."""
        self.mock_doc_model.operand_sets = [
            {
                'key': 'register_operands',
                'title': 'General Registers',
                'category': 'Registers',
                'description': 'General purpose registers. Used for arithmetic operations.',
                'config_index': 0,
                'operands': [
                    {
                        'name': 'reg_a',
                        'title': 'Register A',
                        'syntax': 'a',
                        'value': 'register `a`',
                        'mode': 'Register',
                        'mode_from_doc': True,
                        'description': 'Accumulator. Primary register.'
                    },
                    {
                        'name': 'reg_b',
                        'title': 'Register B',
                        'syntax': 'b',
                        'value': 'register `b`',
                        'mode': 'Register',
                        'mode_from_doc': True,
                        'description': 'Index register'
                    }
                ]
            },
            {
                'key': 'zero_page',
                'title': None,
                'category': None,
                'description': None,
                'config_index': 1,
                'operands': [
                    {
                        'name': 'zp_addr',
                        'syntax': 'numeric_expression',
                        'value': 'numeric expression',
                        'mode': 'Address',
                        'mode_from_doc': False,
                        'description': 'Valid within `ZERO_PAGE` memory zone.'
                    }
                ]
            },
            {
                'key': 'enum_values',
                'title': 'Enumerated Values',
                'category': None,
                'description': None,
                'config_index': 2,
                'operands': [
                    {
                        'name': 'enum',
                        'syntax': 'enum',
                        'value': 'numeric values: `0`, `1`, `2`',
                        'mode': 'Numeric Enumeration',
                        'mode_from_doc': False,
                        'description': 'Possible values: `0`, `1`, `2`.'
                    }
                ]
            },
            {
                'key': 'memory_operands',
                'title': 'Memory Operands',
                'category': None,
                'description': None,
                'config_index': 3,
                'operands': [
                    {
                        'name': 'defered_indexed_x',
                        'title': 'Indirect Indexed Memory Value',
                        'syntax': '[x + [numeric_expression]]',
                        'value': 'register `x`',
                        'mode': 'indirect_indexed',
                        'mode_from_doc': True,
                        'description': None
                    }
                ]
            },
            {
                'key': 'limited_num',
                'title': 'Limited Number',
                'category': None,
                'description': None,
                'config_index': 4,
                'operands': [
                    {
                        'name': 'n3',
                        'syntax': 'numeric_expression',
                        'value': 'numeric expression valued between 0 and 0x7 expressed as 3 bit value',
                        'mode': 'numeric',
                        'mode_from_doc': False,
                        'description': None
                    }
                ]
            }
        ]

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('## Operand Sets', result)
        self.assertIn('### `register_operands` - General Registers', result)
        self.assertIn('*Category: Registers*', result)
        self.assertIn('General purpose registers. Used for arithmetic operations.', result)
        self.assertIn(
            '| Register A (`reg_a`) | `a` | register `a` | `Register` | Accumulator. Primary register. |',
            result
        )
        self.assertIn('| Operand | Syntax | Value | Addressing Mode | Description |', result)
        self.assertIn(
            '| Register B (`reg_b`) | `b` | register `b` | `Register` | Index register |',
            result
        )
        self.assertIn('### `enum_values` - Enumerated Values', result)
        self.assertIn(
            '| `enum` | `enum` | numeric values: `0`, `1`, `2` | Numeric Enumeration | Possible values: `0`, `1`, `2`. |',
            result
        )
        self.assertIn('### `memory_operands` - Memory Operands', result)
        self.assertIn(
            '| Indirect Indexed Memory Value (`defered_indexed_x`) | `[x + [numeric_expression]]` '
            '| register `x` | `indirect_indexed` |',
            result
        )
        self.assertIn('### `zero_page`', result)
        self.assertNotIn('Undocumented operand set zero_page.', result)
        self.assertIn(
            '| `zp_addr` | `numeric_expression` | numeric expression | Address | Valid within `ZERO_PAGE` memory zone. |',
            result
        )
        self.assertIn('### `limited_num` - Limited Number', result)
        self.assertIn('| Operand | Syntax | Value | Addressing Mode |', result)
        self.assertIn(
            '| `n3` | `numeric_expression` | numeric expression valued between 0 and 0x7 expressed as 3 bit value | numeric |',
            result
        )

    def test_generate_with_instruction_documentation(self):
        """Test generating document with instruction documentation."""
        self.mock_doc_model.instruction_docs = {
            'lda': {
                'category': 'Data Movement',
                'title': 'Load accumulator',
                'description': 'Transfers a literal into A.',
                'modifies': [
                    {
                        'type': 'register',
                        'target': 'A',
                        'description': 'Loaded with operand value'
                    },
                    {
                        'type': 'flag',
                        'target': 'Z',
                        'description': 'Set if result is zero'
                    }
                ],
                'examples': [
                    {
                        'title': 'Load immediate',
                        'description': 'Load the value 42',
                        'code': 'lda #42'
                    }
                ],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'operand_sets',
                                'label': None,
                                'operands': [
                                    {
                                        'name': 'imm8',
                                        'type': 'operand_set',
                                        'syntax': 'imm8',
                                        'value': '8-bit immediate',
                                        'description': '8-bit immediate value.',
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            'add': {
                'category': 'Arithmetic',
                'title': 'Add to accumulator',
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'specific',
                                'label': 'reg_imm',
                                'operands': [
                                    {
                                        'name': 'dest',
                                        'type': 'register',
                                        'syntax': 'r0',
                                        'value': 'register `r0`',
                                        'description': 'Destination register.',
                                        'include_in_code': True
                                    },
                                    {
                                        'name': 'value',
                                        'type': 'numeric',
                                        'syntax': 'numeric_expression',
                                        'value': 'numeric_expression',
                                        'description': 'Immediate value.',
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            'sta': {
                'category': 'Data Movement',
                'title': 'Store accumulator',
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'none',
                                'label': None,
                                'operands': []
                            }
                        ]
                    }
                ]
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
        self.assertIn('Transfers a literal into A.', result)
        self.assertIn('*Calling syntax:*', result)
        self.assertIn('```asm\nLDA imm8\n```', result)
        self.assertIn('```asm\nADD r0, numeric_expression\n```', result)
        self.assertIn('| Operand | Type | Value | Description |', result)
        self.assertIn('| `imm8` | operand_set | 8-bit immediate | 8-bit immediate value. |', result)
        self.assertIn('| `r0` | register | register `r0` | Destination register. |', result)
        self.assertIn('\n---\n\n### `STA`', result)
        self.assertNotIn('---\n*Calling syntax:*', result)

        # Verify modifies table
        self.assertIn('#### Modifies', result)
        self.assertIn('| Type | Target | Description |', result)
        self.assertIn('| Register | A | Loaded with operand value |', result)
        self.assertIn('| Flag | Z | Set if result is zero |', result)

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
                'description': None,
                'modifies': [],
                'examples': [],
                'documented': False,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'none',
                                'label': None,
                                'operands': []
                            }
                        ]
                    }
                ]
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
        self.assertIn('```asm\nNOP\n```', result)

    def test_instruction_versions_emit_headings(self):
        """Multiple operand variants render distinct version headings."""
        self.mock_doc_model.instruction_docs = {
            'mix': {
                'category': 'Data Movement',
                'title': 'Mixed operand instruction',
                'description': None,
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'specific',
                                'label': 'reg_variant',
                                'operands': [
                                    {
                                        'name': 'reg',
                                        'type': 'register',
                                        'description': None,
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'index': 2,
                        'signatures': [
                            {
                                'kind': 'operand_sets',
                                'label': None,
                                'operands': [
                                    {
                                        'name': 'imm',
                                        'type': 'operand_set',
                                        'description': None,
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Data Movement': ['mix']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('#### Version 1', result)
        self.assertIn('#### Version 2', result)
        self.assertIn('```asm\nMIX reg\n```', result)
        self.assertIn('```asm\nMIX imm\n```', result)

    def test_duplicate_operand_names_are_numbered(self):
        """Operands with identical names are numbered in syntax and operand tables."""
        self.mock_doc_model.instruction_docs = {
            'abb': {
                'category': 'Arithmetic',
                'title': None,
                'description': None,
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'operand_sets',
                                'label': None,
                                'operands': [
                                    {
                                        'name': 'absolute_address',
                                        'type': 'operand_set',
                                        'description': None,
                                        'include_in_code': True
                                    },
                                    {
                                        'name': 'absolute_address',
                                        'type': 'operand_set',
                                        'description': None,
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }

        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Arithmetic': ['abb']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('```asm\nABB absolute_address1, absolute_address2\n```', result)
        self.assertIn('| `absolute_address1` | operand_set |', result)
        self.assertIn('| `absolute_address2` | operand_set |', result)

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
            'addressing_modes': [
                {
                    'name': 'test',
                    'title': 'Short label',
                    'description': 'Line 1\nLine 2'
                }
            ],
            'flags': [
                {
                    'name': 'test_flag',
                    'symbol': 'T',
                    'description': 'Flag line 1\nFlag line 2'
                }
            ],
            'examples': []
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        # Verify newlines are converted to <br> in table cells
        self.assertIn('| `test` | Short label | Line 1<br>Line 2 |', result)
        self.assertIn('| test_flag | `T` | Flag line 1<br>Flag line 2 |', result)

    def test_modifies_table_without_details_column(self):
        """Test that modifies table omits Details column when no entries have details."""
        self.mock_doc_model.instruction_docs = {
            'nop': {
                'category': 'Operations',
                'title': 'No operation',
                'modifies': [
                    {
                        'type': 'register',
                        'target': 'pc',
                        'description': 'Incremented'
                    },
                    {
                        'type': 'flag',
                        'target': 'cycles',
                        'description': 'Consumed'
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

    def test_modifies_table_ignores_details(self):
        """Modifies table ignores details even when provided."""
        self.mock_doc_model.instruction_docs = {
            'lda': {
                'category': 'Data Movement',
                'title': 'Load accumulator',
                'modifies': [
                    {
                        'type': 'register',
                        'target': 'A',
                        'description': 'Loaded with value'
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

        # Verify modifies table ignores details column
        self.assertIn('| Type | Target | Description |', result)
        self.assertNotIn('| Type | Target | Description | Details |', result)
        self.assertIn('| Register | A | Loaded with value |', result)
        self.assertIn('| Flag | Z | Set if zero |', result)

    def test_numeric_bytecode_value_column(self):
        """Numeric bytecode operands show value range without duplicating details."""
        self.mock_doc_model.instruction_docs = {
            'lr': {
                'category': 'Data Movement',
                'title': 'Load register',
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'specific',
                                'label': 'reg_and_nbyte',
                                'operands': [
                                    {
                                        'name': 'dest',
                                        'type': 'register',
                                        'syntax': 'a',
                                        'value': 'register `a`',
                                        'description': None,
                                        'include_in_code': True
                                    },
                                    {
                                        'name': 'scratchpad_regs',
                                        'type': 'numeric_bytecode',
                                        'syntax': 'scratchpad_regs',
                                        'value': 'numeric expression valued between 0 and 0xB',
                                        'description': None,
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Data Movement': ['lr']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('```asm\nLR a, scratchpad_regs\n```', result)
        self.assertIn('| Operand | Type | Value |', result)
        self.assertIn('| `scratchpad_regs` | numeric_bytecode | numeric expression valued between 0 and 0xB |', result)

    def test_single_member_operand_set_shows_member_value(self):
        """Operand set with one member surfaces that member's syntax/value in where table."""
        self.mock_doc_model.instruction_docs = {
            'lr': {
                'category': 'Data Movement',
                'title': 'Load register',
                'modifies': [],
                'examples': [],
                'documented': True,
                'versions': [
                    {
                        'index': 1,
                        'signatures': [
                            {
                                'kind': 'operand_sets',
                                'label': None,
                                'operands': [
                                    {
                                        'name': 'single_reg',
                                        'type': 'register',
                                        'syntax': 'a',
                                        'value': 'register `a`',
                                        'description': None,
                                        'include_in_code': True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        self.mock_doc_model.get_instructions_by_category.return_value = {
            'Data Movement': ['lr']
        }

        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)
        result = generator.generate()

        self.assertIn('```asm\nLR a\n```', result)
        self.assertIn('| Operand | Type | Value |', result)
        self.assertIn('| `a` | register | register `a` |', result)

    def test_has_general_documentation(self):
        """Test the _has_general_documentation method."""
        generator = MarkdownGenerator(self.mock_doc_model, verbose=0)

        # Per new requirements, always show general section (contains config details)
        self.assertTrue(generator._has_general_documentation())

        # Reset and test with addressing modes
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
