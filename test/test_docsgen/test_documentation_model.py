import unittest
from unittest.mock import Mock
from unittest.mock import patch

from bespokeasm.docsgen.documentation_model import DocumentationModel


class TestDocumentationModel(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        # Mock ISA model
        self.mock_isa_model = Mock()
        self.mock_isa_model.isa_name = 'test-isa'
        self.mock_isa_model._config = {}

    def test_init_with_empty_config(self):
        """Test initialization with empty configuration."""
        model = DocumentationModel(self.mock_isa_model, verbose=0)

        self.assertEqual(model.isa_name, 'test-isa')
        self.assertIsNone(model.isa_description)
        self.assertEqual(model.general_docs['description'], None)
        self.assertEqual(model.general_docs['details'], None)
        self.assertEqual(model.general_docs['addressing_modes'], [])
        self.assertEqual(model.general_docs['flags'], [])
        self.assertEqual(model.general_docs['examples'], [])
        self.assertEqual(model.instruction_docs, {})

    def test_parse_general_documentation(self):
        """Test parsing general documentation section."""
        self.mock_isa_model._config = {
            'general': {
                'word_size': 12,
                'registers': {
                    'A': {
                        'description': 'Accumulator register',
                        'details': 'Primary working register.',
                        'size': 8
                    },
                    'SP': {
                        'description': 'Stack pointer',
                        'size': 16
                    },
                    'X': {}
                },
                'flags': {
                    'C': {
                        'name': 'carry',
                        'description': 'Carry flag',
                        'details': 'Set on arithmetic overflow'
                    },
                    'Z': {
                        'name': 'zero',
                        'description': 'Zero flag'
                    }
                },
                'documentation': {
                    'description': 'Test ISA Description',
                    'details': 'Detailed information about the ISA',
                    'addressing_modes': {
                        'immediate': {
                            'description': 'Immediate addressing',
                            'details': 'Load value directly'
                        },
                        'register': {
                            'description': 'Register addressing'
                        }
                    },
                    'examples': [
                        {
                            'description': 'Basic example',
                            'code': 'lda #5',
                            'details': 'Load immediate value'
                        }
                    ]
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)

        # Test general documentation
        self.assertEqual(model.isa_description, 'Test ISA Description')
        self.assertEqual(model.general_docs['description'], 'Test ISA Description')
        self.assertEqual(model.general_docs['details'], 'Detailed information about the ISA')

        # Test addressing modes
        addressing_modes = model.general_docs['addressing_modes']
        self.assertEqual(len(addressing_modes), 2)
        self.assertEqual(addressing_modes[0]['name'], 'immediate')
        self.assertEqual(addressing_modes[0]['description'], 'Immediate addressing')
        self.assertEqual(addressing_modes[0]['details'], 'Load value directly')
        self.assertEqual(addressing_modes[1]['name'], 'register')
        self.assertEqual(addressing_modes[1]['description'], 'Register addressing')
        self.assertIsNone(addressing_modes[1]['details'])

        # Test registers
        registers = model.general_docs['registers']
        self.assertEqual(len(registers), 3)
        self.assertEqual(registers[0]['name'], 'A')
        self.assertEqual(registers[0]['description'], 'Accumulator register')
        self.assertEqual(registers[0]['details'], 'Primary working register.')
        self.assertEqual(registers[0]['size'], 8)
        self.assertEqual(registers[1]['name'], 'SP')
        self.assertEqual(registers[1]['description'], 'Stack pointer')
        self.assertIsNone(registers[1]['details'])
        self.assertEqual(registers[1]['size'], 16)
        self.assertEqual(registers[2]['name'], 'X')
        self.assertIsNone(registers[2]['description'])
        self.assertIsNone(registers[2]['details'])
        self.assertIsNone(registers[2]['size'])

        # Test flags
        flags = model.general_docs['flags']
        self.assertEqual(len(flags), 2)
        self.assertEqual(flags[0]['name'], 'carry')
        self.assertEqual(flags[0]['symbol'], 'C')
        self.assertEqual(flags[0]['description'], 'Carry flag')
        self.assertEqual(flags[0]['details'], 'Set on arithmetic overflow')
        self.assertEqual(flags[1]['name'], 'zero')
        self.assertEqual(flags[1]['symbol'], 'Z')
        self.assertEqual(flags[1]['description'], 'Zero flag')

        # Test examples
        examples = model.general_docs['examples']
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]['description'], 'Basic example')
        self.assertEqual(examples[0]['code'], 'lda #5')
        self.assertEqual(examples[0]['details'], 'Load immediate value')

    def test_register_documentation_from_list(self):
        """Registers provided as a list are converted into name-only documentation entries."""
        self.mock_isa_model._config = {
            'general': {
                'registers': ['A', 'B', 'C']
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        registers = model.general_docs['registers']
        self.assertEqual(len(registers), 3)
        self.assertEqual(registers[0]['name'], 'A')
        self.assertIsNone(registers[0]['description'])
        self.assertIsNone(registers[0]['details'])
        self.assertIsNone(registers[0]['size'])

    def test_parse_general_documentation_legacy_flags(self):
        """Legacy documentation.flags structure is still supported."""
        self.mock_isa_model._config = {
            'general': {
                'documentation': {
                    'flags': [
                        {
                            'name': 'carry',
                            'symbol': 'C',
                            'description': 'Carry flag'
                        }
                    ]
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=1)
        flags = model.general_docs['flags']
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]['name'], 'carry')
        self.assertEqual(flags[0]['symbol'], 'C')
        self.assertEqual(flags[0]['description'], 'Carry flag')
        self.assertIsNone(flags[0]['details'])

    def test_parse_instruction_documentation(self):
        """Test parsing instruction documentation."""
        self.mock_isa_model._config = {
            'instructions': {
                'lda': {
                    'documentation': {
                        'category': 'Data Movement',
                        'description': 'Load accumulator',
                        'details': 'Load a value into the accumulator register',
                        'modifies': [
                            {
                                'register': 'A',
                                'description': 'Loaded with operand value'
                            },
                            {
                                'flag': 'Z',
                                'description': 'Set if result is zero'
                            }
                        ],
                        'examples': [
                            {
                                'description': 'Load immediate',
                                'code': 'lda #42',
                                'details': 'Load the value 42 into accumulator'
                            }
                        ]
                    }
                },
                'add': {
                    'documentation': {
                        'category': 'Arithmetic',
                        'description': 'Add to accumulator'
                    }
                },
                'nop': {
                    # No documentation
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)

        # Test instruction documentation
        self.assertEqual(len(model.instruction_docs), 2)  # Only documented instructions

        # Test LDA instruction
        lda_doc = model.instruction_docs['lda']
        self.assertEqual(lda_doc['category'], 'Data Movement')
        self.assertEqual(lda_doc['description'], 'Load accumulator')
        self.assertEqual(lda_doc['details'], 'Load a value into the accumulator register')

        # Test modifies
        modifies = lda_doc['modifies']
        self.assertEqual(len(modifies), 2)
        self.assertEqual(modifies[0]['type'], 'register')
        self.assertEqual(modifies[0]['target'], 'A')
        self.assertEqual(modifies[0]['description'], 'Loaded with operand value')
        self.assertEqual(modifies[1]['type'], 'flag')
        self.assertEqual(modifies[1]['target'], 'Z')
        self.assertEqual(modifies[1]['description'], 'Set if result is zero')

        # Test examples
        examples = lda_doc['examples']
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]['description'], 'Load immediate')
        self.assertEqual(examples[0]['code'], 'lda #42')
        self.assertEqual(examples[0]['details'], 'Load the value 42 into accumulator')

        # Test ADD instruction (minimal documentation)
        add_doc = model.instruction_docs['add']
        self.assertEqual(add_doc['category'], 'Arithmetic')
        self.assertEqual(add_doc['description'], 'Add to accumulator')
        self.assertIsNone(add_doc['details'])
        self.assertEqual(add_doc['modifies'], [])
        self.assertEqual(add_doc['examples'], [])

    def test_get_instructions_by_category(self):
        """Test getting instructions organized by category."""
        self.mock_isa_model._config = {
            'instructions': {
                'lda': {
                    'documentation': {
                        'category': 'Data Movement',
                        'description': 'Load accumulator'
                    }
                },
                'sta': {
                    'documentation': {
                        'category': 'Data Movement',
                        'description': 'Store accumulator'
                    }
                },
                'add': {
                    'documentation': {
                        'category': 'Arithmetic',
                        'description': 'Add to accumulator'
                    }
                },
                'jmp': {
                    'documentation': {
                        'category': 'Control Flow',
                        'description': 'Jump'
                    }
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        categories = model.get_instructions_by_category()

        # Test categories
        self.assertEqual(len(categories), 3)
        self.assertIn('Data Movement', categories)
        self.assertIn('Arithmetic', categories)
        self.assertIn('Control Flow', categories)

        # Test instructions in categories (should be sorted)
        self.assertEqual(categories['Data Movement'], ['lda', 'sta'])
        self.assertEqual(categories['Arithmetic'], ['add'])
        self.assertEqual(categories['Control Flow'], ['jmp'])

    def test_invalid_documentation_formats(self):
        """Test handling of invalid documentation formats."""
        self.mock_isa_model._config = {
            'general': {
                'documentation': {
                    'addressing_modes': {
                        'invalid': 'not a dict'  # Should be ignored
                    },
                    'flags': [
                        {'name': 'valid_flag', 'description': 'Valid'},
                        'invalid_flag',  # Should be ignored
                        {'description': 'no_name'}  # Should be ignored - no name
                    ],
                    'examples': [
                        {'description': 'valid', 'code': 'nop'},
                        {'description': 'no_code'},  # Should be ignored - no code
                        'invalid'  # Should be ignored
                    ]
                }
            },
            'instructions': {
                'test': {
                    'documentation': {
                        'category': 'Test',
                        'modifies': [
                            {'register': 'A', 'description': 'Valid'},
                            {'description': 'no_target'},  # Should be ignored
                            'invalid'  # Should be ignored
                        ]
                    }
                }
            }
        }

        with patch('click.echo') as mock_echo:
            model = DocumentationModel(self.mock_isa_model, verbose=1)

            # Should have warnings for invalid formats
            self.assertTrue(mock_echo.called)

            # Test that valid items are preserved and invalid ones ignored
            self.assertEqual(len(model.general_docs['addressing_modes']), 0)
            self.assertEqual(len(model.general_docs['flags']), 1)
            self.assertEqual(model.general_docs['flags'][0]['name'], 'valid_flag')
            self.assertEqual(len(model.general_docs['examples']), 1)
            self.assertEqual(model.general_docs['examples'][0]['description'], 'valid')

            # Test instruction modifies
            test_doc = model.instruction_docs['test']
            self.assertEqual(len(test_doc['modifies']), 1)
            self.assertEqual(test_doc['modifies'][0]['target'], 'A')


if __name__ == '__main__':
    unittest.main()
