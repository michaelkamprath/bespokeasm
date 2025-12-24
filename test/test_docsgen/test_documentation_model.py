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
        self.assertEqual(model.predefined_memory_zones, [])
        self.assertEqual(model.predefined_constants, [])
        self.assertEqual(model.operand_sets, [])
        self.assertEqual(model.instruction_docs, {})
        self.assertEqual(model.macro_docs, {})

    def test_parse_general_documentation(self):
        """Test parsing general documentation section."""
        self.mock_isa_model._config = {
            'general': {
                'word_size': 12,
                'registers': {
                    'A': {
                        'title': 'Accumulator',
                        'description': 'Primary working register.',
                        'size': 8
                    },
                    'SP': {
                        'title': 'Stack Pointer',
                        'description': 'Holds the top of stack address.',
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
        self.assertEqual(registers[0]['title'], 'Accumulator')
        self.assertEqual(registers[0]['description'], 'Primary working register.')
        self.assertIsNone(registers[0]['details'])
        self.assertEqual(registers[0]['size'], 8)
        self.assertEqual(registers[1]['name'], 'SP')
        self.assertEqual(registers[1]['title'], 'Stack Pointer')
        self.assertEqual(registers[1]['description'], 'Holds the top of stack address.')
        self.assertIsNone(registers[1]['details'])
        self.assertEqual(registers[1]['size'], 16)
        self.assertEqual(registers[2]['name'], 'X')
        self.assertIsNone(registers[2]['title'])
        self.assertIsNone(registers[2]['description'])
        self.assertIsNone(registers[2]['details'])
        self.assertEqual(registers[2]['size'], 12)

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

    def test_parse_macro_documentation(self):
        """Macro documentation matches instruction-style fields and variant parsing."""
        self.mock_isa_model._config = {
            'operand_sets': {},
            'macros': {
                'push2': {
                    'documentation': {
                        'category': 'Stack',
                        'title': 'Push Word',
                        'description': 'Pushes a 16-bit value.',
                        'details': 'Expands to two pushes.',
                        'examples': [{'description': 'push', 'code': 'push2 $1234'}]
                    },
                    'variants': [
                        {
                            'operands': {
                                'specific_operands': {
                                    'immediate': {
                                        'list': {
                                            'value': {
                                                'type': 'numeric'
                                            }
                                        }
                                    }
                                }
                            },
                            'documentation': {
                                'title': 'Immediate',
                                'description': 'Immediate 16-bit value.'
                            }
                        }
                    ]
                },
                'mov2': [
                    {
                        'operands': {
                            'specific_operands': {
                                'address_pair': {
                                    'list': {
                                        'src': {'type': 'indirect_numeric'},
                                        'dst': {'type': 'indirect_numeric'}
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)

        self.assertIn('push2', model.macro_docs)
        push2_doc = model.macro_docs['push2']
        self.assertTrue(push2_doc['documented'])
        self.assertEqual(push2_doc['category'], 'Stack')
        self.assertEqual(push2_doc['title'], 'Push Word')
        self.assertEqual(push2_doc['description'], 'Pushes a 16-bit value.')
        self.assertEqual(push2_doc['details'], 'Expands to two pushes.')
        self.assertEqual(len(push2_doc['versions']), 1)
        self.assertEqual(push2_doc['versions'][0]['title'], 'Immediate')
        self.assertEqual(push2_doc['versions'][0]['description'], 'Immediate 16-bit value.')
        self.assertEqual(len(push2_doc['versions'][0]['signatures']), 1)
        self.assertEqual(push2_doc['versions'][0]['signatures'][0]['operands'][0]['type'], 'numeric')

        mov2_doc = model.macro_docs['mov2']
        self.assertFalse(mov2_doc['documented'])
        self.assertEqual(mov2_doc['category'], 'Uncategorized')
        self.assertEqual(len(mov2_doc['versions']), 1)
        self.assertEqual(len(mov2_doc['versions'][0]['signatures'][0]['operands']), 2)

    def test_macro_category_defaults_when_none(self):
        """A None category is treated as Uncategorized instead of breaking sorting."""
        self.mock_isa_model._config = {
            'operand_sets': {},
            'macros': {
                'noop': {
                    'documentation': {
                        'category': None,
                        'description': 'does nothing'
                    },
                    'variants': [
                        {
                            'operands': {
                                'specific_operands': {
                                    'none': {'list': {}}
                                }
                            }
                        }
                    ]
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        self.assertEqual(model.macro_docs['noop']['category'], 'Uncategorized')

    def test_parse_operand_sets_documentation(self):
        """Operand set documentation is parsed with ordering, syntax, and auto details."""
        self.mock_isa_model._config = {
            'operand_sets': {
                'register_operands': {
                    'documentation': {
                        'title': 'General Registers',
                        'category': 'Registers',
                        'description': 'General purpose registers.',
                        'details': 'Used for arithmetic operations.',
                        'operand_order': ['reg_b', 'reg_a']
                    },
                    'operand_values': {
                        'reg_a': {
                            'type': 'register',
                            'register': 'a',
                            'documentation': {
                                'title': 'Register A',
                                'mode': 'Register',
                                'description': 'Accumulator register',
                                'details': 'Used frequently.'
                            }
                        },
                        'reg_b': {
                            'type': 'register',
                            'register': 'b',
                            'documentation': {
                                'title': 'Register B',
                                'mode': 'Register',
                                'description': 'Index register'
                            }
                        }
                    }
                },
                'zero_page': {
                    'operand_values': {
                        'zp_addr': {
                            'type': 'address',
                            'argument': {
                                'memory_zone': 'ZERO_PAGE'
                            }
                        }
                    }
                },
                'limited_num': {
                    'operand_values': {
                        'n3': {
                            'type': 'numeric',
                            'bytecode': {
                                'min': 0,
                                'max': 7,
                                'size': 3
                            }
                        }
                    }
                },
                'rel_range': {
                    'operand_values': {
                        'rel_off': {
                            'type': 'relative_address',
                            'argument': {
                                'min': -5,
                                'max': 5,
                                'size': 8
                            },
                            'use_curly_braces': False
                        }
                    }
                },
                'offset_addr': {
                    'operand_values': {
                        'offset': {
                            'type': 'relative_address',
                            'argument': {
                                'min': -127,
                                'max': 128,
                                'size': 8
                            }
                        }
                    }
                },
                'memory_operands': {
                    'operand_values': {
                        'defered_indexed_x': {
                            'type': 'indirect_indexed_register',
                            'register': 'x',
                            'index_operands': {
                                'indirect_addr': {
                                    'type': 'indirect_numeric'
                                }
                            },
                            'documentation': {
                                'title': 'Indirect Indexed Memory Value',
                                'mode': 'indirect_indexed'
                            }
                        }
                    }
                },
                'enum_values': {
                    'operand_values': {
                        'enum': {
                            'type': 'numeric_enumeration',
                            'bytecode': {
                                'value_dict': {
                                    0: 0,
                                    1: 1,
                                    2: 2
                                }
                            }
                        }
                    }
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        operand_sets = model.operand_sets
        operand_sets_map = {entry['key']: entry for entry in operand_sets}
        self.assertSetEqual(
            set(operand_sets_map.keys()),
            {'register_operands', 'zero_page', 'enum_values', 'memory_operands', 'limited_num', 'rel_range', 'offset_addr'}
        )

        register_set = operand_sets_map['register_operands']
        self.assertEqual(register_set['title'], 'General Registers')
        self.assertEqual(register_set['category'], 'Registers')

        self.assertEqual(register_set['description'], 'General purpose registers.')
        self.assertEqual(register_set['details'], 'Used for arithmetic operations.')
        self.assertEqual([op['name'] for op in register_set['operands']], ['reg_b', 'reg_a'])
        self.assertEqual(register_set['operands'][0]['syntax'], 'b')
        self.assertEqual(register_set['operands'][0]['value'], 'register `b`')
        self.assertEqual(register_set['operands'][0]['mode'], 'Register')
        self.assertTrue(register_set['operands'][0]['mode_from_doc'])
        self.assertEqual(register_set['operands'][0]['description'], 'Index register')
        self.assertIsNone(register_set['operands'][0]['details'])
        self.assertEqual(register_set['operands'][0]['title'], 'Register B')
        self.assertEqual(register_set['operands'][1]['syntax'], 'a')
        self.assertEqual(register_set['operands'][1]['value'], 'register `a`')
        self.assertEqual(register_set['operands'][1]['details'], 'Used frequently.')
        self.assertEqual(register_set['operands'][1]['title'], 'Register A')
        self.assertTrue(register_set['operands'][1]['mode_from_doc'])

        zero_page_set = operand_sets_map['zero_page']
        self.assertIsNone(zero_page_set['description'])
        self.assertIsNone(zero_page_set['details'])
        self.assertEqual(len(zero_page_set['operands']), 1)
        zp_operand = zero_page_set['operands'][0]
        self.assertEqual(zp_operand['mode'], 'Address')
        self.assertFalse(zp_operand['mode_from_doc'])
        self.assertEqual(zp_operand['syntax'], 'zp_addr')
        self.assertEqual(zp_operand['value'], 'numeric expression')
        self.assertIn('Valid within `ZERO_PAGE` memory zone.', zp_operand['details'])
        self.assertIsNone(zp_operand['title'])

        enum_set = operand_sets_map['enum_values']
        self.assertIsNone(enum_set['description'])
        enum_operand = enum_set['operands'][0]
        self.assertEqual(enum_operand['mode'], 'Numeric Enumeration')
        self.assertFalse(enum_operand['mode_from_doc'])
        self.assertIsNone(enum_operand['title'])
        self.assertIsNone(enum_operand['description'])
        self.assertEqual(enum_operand['syntax'], 'enum')
        self.assertEqual(enum_operand['value'], 'numeric values: `0`, `1`, `2`')
        self.assertIn('Possible values: `0`, `1`, `2`.', enum_operand['details'])

        memory_set = operand_sets_map['memory_operands']
        self.assertIsNone(memory_set['description'])
        memory_operand = memory_set['operands'][0]
        self.assertEqual(memory_operand['name'], 'defered_indexed_x')
        self.assertEqual(memory_operand['syntax'], '[x + [indirect_addr]]')
        self.assertEqual(memory_operand['value'], 'register `x`')
        self.assertEqual(memory_operand['mode'], 'indirect_indexed')
        self.assertTrue(memory_operand['mode_from_doc'])

        limited_set = operand_sets_map['limited_num']
        limited_operand = limited_set['operands'][0]
        self.assertEqual(limited_operand['value'], 'numeric expression valued between 0 and 7 expressed as 3 bit value')

        rel_set = operand_sets_map['rel_range']
        rel_operand = rel_set['operands'][0]
        self.assertEqual(rel_operand['value'], 'numeric expression valued between -5 and 5 expressed as 8 bit value')

        offset_set = operand_sets_map['offset_addr']
        offset_operand = offset_set['operands'][0]
        self.assertEqual(offset_operand['value'], 'numeric expression valued between -127 and 128 expressed as 8 bit value')

    def test_parse_predefined_memory_zones_documentation(self):
        """Predefined memory zones documentation is parsed with optional metadata."""
        self.mock_isa_model._config = {
            'predefined': {
                'memory_zones': [
                    {
                        'name': 'ZERO_PAGE',
                        'start': 0,
                        'end': 255,
                        'documentation': {
                            'title': 'Zero Page',
                            'description': 'Fast access memory.'
                        }
                    },
                    {
                        'name': 'ROM',
                        'start': '0x8000',
                        'end': '0xFFFF'
                    }
                ]
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        memory_zones = model.predefined_memory_zones
        self.assertEqual(len(memory_zones), 2)

        zero_page = memory_zones[0]
        self.assertEqual(zero_page['name'], 'ZERO_PAGE')
        self.assertEqual(zero_page['start'], 0)
        self.assertEqual(zero_page['end'], 255)
        self.assertEqual(zero_page['title'], 'Zero Page')
        self.assertEqual(zero_page['description'], 'Fast access memory.')
        self.assertTrue(zero_page['documented'])

        rom_zone = memory_zones[1]
        self.assertEqual(rom_zone['name'], 'ROM')
        self.assertEqual(rom_zone['start'], '0x8000')
        self.assertEqual(rom_zone['end'], '0xFFFF')
        self.assertIsNone(rom_zone['title'])
        self.assertIsNone(rom_zone['description'])
        self.assertFalse(rom_zone['documented'])

    def test_parse_predefined_constants_documentation(self):
        """Predefined constants documentation is parsed with optional metadata."""
        self.mock_isa_model._config = {
            'predefined': {
                'constants': [
                    {
                        'name': '_Start',
                        'value': 0x1000,
                        'documentation': {
                            'type': 'subroutine',
                            'description': 'Program entry point.'
                        }
                    },
                    {
                        'name': '_Prompt',
                        'value': '0x1003'
                    }
                ]
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        constants = model.predefined_constants
        self.assertEqual(len(constants), 2)

        start_const = constants[0]
        self.assertEqual(start_const['name'], '_Start')
        self.assertEqual(start_const['value'], 0x1000)
        self.assertEqual(start_const['type'], 'subroutine')
        self.assertIsNone(start_const['size'])
        self.assertEqual(start_const['description'], 'Program entry point.')
        self.assertTrue(start_const['documented'])

        prompt_const = constants[1]
        self.assertEqual(prompt_const['name'], '_Prompt')
        self.assertEqual(prompt_const['value'], '0x1003')
        self.assertIsNone(prompt_const['type'])
        self.assertIsNone(prompt_const['size'])
        self.assertIsNone(prompt_const['description'])
        self.assertFalse(prompt_const['documented'])

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
        self.assertIsNone(registers[0]['title'])
        self.assertIsNone(registers[0]['description'])
        self.assertIsNone(registers[0]['details'])
        self.assertEqual(registers[0]['size'], 8)

    def test_parse_general_documentation_legacy_flags(self):
        """Legacy documentation.flags structure should be ignored."""
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

        with patch('click.echo') as mock_echo:
            model = DocumentationModel(self.mock_isa_model, verbose=1)
            flags = model.general_docs['flags']
            self.assertEqual(len(flags), 0)
            mock_echo.assert_called()

    def test_parse_instruction_documentation(self):
        """Test parsing instruction documentation."""
        self.mock_isa_model._config = {
            'operand_sets': {
                'imm8': {
                    'documentation': {
                        'description': '8-bit immediate value',
                        'details': 'Unsigned literal constrained to 0-255.'
                    }
                }
            },
            'instructions': {
                'lda': {
                    'operands': {
                        'count': 1,
                        'operand_sets': {
                            'list': ['imm8']
                        }
                    },
                    'documentation': {
                        'category': 'Data Movement',
                        'title': 'Load accumulator',
                        'description': 'Transfers a literal into the accumulator.',
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
                    'operands': {
                        'count': 2,
                        'specific_operands': {
                            'register_immediate': {
                                'list': {
                                    'dest': {
                                        'type': 'register',
                                        'documentation': {
                                            'description': 'Destination register.'
                                        }
                                    },
                                    'value': {
                                        'type': 'numeric',
                                        'documentation': {
                                            'description': 'Immediate value to add.'
                                        }
                                    }
                                }
                            }
                        }
                    },
                    'documentation': {
                        'category': 'Arithmetic',
                        'title': 'Add to accumulator'
                    }
                },
                'nop': {
                    # No documentation
                    'operands': {
                        'count': 0
                    }
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)

        # Test instruction documentation
        self.assertEqual(len(model.instruction_docs), 3)

        # Test LDA instruction
        lda_doc = model.instruction_docs['lda']
        self.assertEqual(lda_doc['category'], 'Data Movement')
        self.assertEqual(lda_doc['title'], 'Load accumulator')
        self.assertEqual(lda_doc['description'], 'Transfers a literal into the accumulator.')
        self.assertEqual(lda_doc['details'], 'Load a value into the accumulator register')
        self.assertTrue(lda_doc['documented'])
        self.assertEqual(len(lda_doc['versions']), 1)
        lda_signature = lda_doc['versions'][0]['signatures'][0]
        self.assertEqual(lda_signature['kind'], 'operand_sets')
        self.assertEqual(len(lda_signature['operands']), 1)
        self.assertEqual(lda_signature['operands'][0]['name'], 'imm8')
        self.assertEqual(lda_signature['operands'][0]['type'], 'operand_set')
        self.assertEqual(lda_signature['operands'][0]['description'], '8-bit immediate value')
        self.assertEqual(
            lda_signature['operands'][0]['details'],
            'Unsigned literal constrained to 0-255.'
        )

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
        self.assertEqual(add_doc['title'], 'Add to accumulator')
        self.assertIsNone(add_doc['description'])
        self.assertIsNone(add_doc['details'])
        self.assertEqual(add_doc['modifies'], [])
        self.assertEqual(add_doc['examples'], [])
        self.assertTrue(add_doc['documented'])
        self.assertEqual(len(add_doc['versions']), 1)
        add_signature = add_doc['versions'][0]['signatures'][0]
        operand_names = [operand['name'] for operand in add_signature['operands']]
        self.assertEqual(operand_names, ['dest', 'value'])
        operand_types = [operand['type'] for operand in add_signature['operands']]
        self.assertEqual(operand_types, ['register', 'numeric'])
        self.assertEqual(add_signature['operands'][0]['syntax'], 'register_label')
        self.assertEqual(add_signature['operands'][0]['value'], 'register `register_label`')
        self.assertEqual(add_signature['operands'][1]['syntax'], 'value')
        self.assertEqual(add_signature['operands'][1]['value'], 'numeric expression')

        # Test NOP instruction (no documentation)
        nop_doc = model.instruction_docs['nop']
        self.assertEqual(nop_doc['category'], 'Uncategorized')
        self.assertIsNone(nop_doc['title'])
        self.assertIsNone(nop_doc['description'])
        self.assertIsNone(nop_doc['details'])
        self.assertEqual(nop_doc['modifies'], [])
        self.assertEqual(nop_doc['examples'], [])
        self.assertFalse(nop_doc['documented'])
        self.assertEqual(len(nop_doc['versions']), 1)
        self.assertEqual(len(nop_doc['versions'][0]['signatures'][0]['operands']), 0)

    def test_operand_set_single_member_exposes_syntax_and_value(self):
        """Operand sets with a single member surface that member's syntax/value in signatures."""
        self.mock_isa_model._config = {
            'operand_sets': {
                'single_reg': {
                    'operand_values': {
                        'reg_a': {
                            'type': 'register',
                            'register': 'a'
                        }
                    }
                }
            },
            'instructions': {
                'lr': {
                    'operands': {
                        'count': 1,
                        'operand_sets': {
                            'list': ['single_reg']
                        }
                    }
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        signature = model.instruction_docs['lr']['versions'][0]['signatures'][0]
        operand = signature['operands'][0]
        self.assertEqual(operand['type'], 'register')
        self.assertEqual(operand['name'], 'reg_a')
        self.assertEqual(operand['syntax'], 'a')
        self.assertEqual(operand['value'], 'register `a`')

    def test_get_instructions_by_category(self):
        """Test getting instructions organized by category."""
        self.mock_isa_model._config = {
            'instructions': {
                'lda': {
                    'documentation': {
                        'category': 'Data Movement',
                        'title': 'Load accumulator'
                    }
                },
                'sta': {
                    'documentation': {
                        'category': 'Data Movement',
                        'title': 'Store accumulator'
                    }
                },
                'add': {
                    'documentation': {
                        'category': 'Arithmetic',
                        'title': 'Add to accumulator'
                    }
                },
                'jmp': {
                    'documentation': {
                        'category': 'Control Flow',
                        'title': 'Jump'
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

    def test_instruction_variant_versions(self):
        """Instruction variants are exposed as sequential versions."""
        self.mock_isa_model._config = {
            'operand_sets': {
                'imm': {},
                'reg': {}
            },
            'instructions': {
                'jmp': {
                    'operands': {
                        'count': 1,
                        'operand_sets': {
                            'list': ['imm']
                        }
                    },
                    'variants': [
                        {
                            'operands': {
                                'count': 2,
                                'specific_operands': {
                                    'double_address': {
                                        'list': {
                                            'target': {
                                                'type': 'address'
                                            },
                                            'source': {
                                                'type': 'address'
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    ]
                },
                'mov': {
                    'variants': [
                        {
                            'operands': {
                                'count': 1,
                                'operand_sets': {
                                    'list': ['reg']
                                }
                            }
                        }
                    ]
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)

        jmp_versions = model.instruction_docs['jmp']['versions']
        self.assertEqual([version['index'] for version in jmp_versions], [1, 2])
        self.assertEqual(jmp_versions[1]['signatures'][0]['kind'], 'specific')
        self.assertEqual(
            [operand['name'] for operand in jmp_versions[1]['signatures'][0]['operands']],
            ['target', 'source']
        )

        mov_versions = model.instruction_docs['mov']['versions']
        self.assertEqual([version['index'] for version in mov_versions], [1])
        self.assertEqual(mov_versions[0]['signatures'][0]['kind'], 'operand_sets')
        self.assertEqual(
            mov_versions[0]['signatures'][0]['operands'][0]['name'],
            'reg'
        )

    def test_operand_syntax_example_and_value(self):
        """Specific operands honor syntax_example and derive value summaries."""
        self.mock_isa_model._config = {
            'instructions': {
                'lr': {
                    'operands': {
                        'count': 3,
                        'specific_operands': {
                            'reg_indirect_numeric': {
                                'list': {
                                    'acc': {
                                        'type': 'register',
                                        'register': 'a',
                                        'documentation': {
                                            'syntax_example': 'a',
                                            'description': 'Accumulator'
                                        }
                                    },
                                    'ptr': {
                                        'type': 'indirect_register',
                                        'register': 'is',
                                        'documentation': {
                                            'description': 'Pointer'
                                        }
                                    },
                                    'scratchpad_regs': {
                                        'type': 'numeric_bytecode',
                                        'bytecode': {
                                            'min': 0,
                                            'max': 11
                                        },
                                        'documentation': {
                                            'description': 'Scratchpad register selector'
                                        }
                                    }
                                }
                            }
                        }
                    },
                    'documentation': {
                        'category': 'Data Movement',
                        'title': 'Load register'
                    }
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        lr_signature = model.instruction_docs['lr']['versions'][0]['signatures'][0]
        operands = lr_signature['operands']
        self.assertEqual(operands[0]['syntax'], 'a')
        self.assertEqual(operands[0]['value'], 'register `a`')
        self.assertEqual(operands[1]['syntax'], '[is]')
        self.assertEqual(operands[1]['value'], 'register `is`')
        self.assertEqual(operands[2]['syntax'], 'scratchpad_regs')
        self.assertEqual(operands[2]['value'], 'numeric expression valued between 0 and 0xB')

    def test_numeric_value_with_size_and_range(self):
        """Numeric operand value includes range and bit size when present."""
        self.mock_isa_model._config = {
            'instructions': {
                'ld': {
                    'operands': {
                        'count': 1,
                        'specific_operands': {
                            'imm': {
                                'list': {
                                    'immediate': {
                                        'type': 'numeric',
                                        'bytecode': {
                                            'min': 1,
                                            'max': 10,
                                            'size': 8
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        model = DocumentationModel(self.mock_isa_model, verbose=0)
        signature = model.instruction_docs['ld']['versions'][0]['signatures'][0]
        operand = signature['operands'][0]
        self.assertEqual(operand['value'], 'numeric expression valued between 1 and 0xA expressed as 8 bit value')

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
            self.assertEqual(len(model.general_docs['flags']), 0)
            self.assertEqual(len(model.general_docs['examples']), 1)
            self.assertEqual(model.general_docs['examples'][0]['description'], 'valid')

            # Test instruction modifies
            test_doc = model.instruction_docs['test']
            self.assertEqual(len(test_doc['modifies']), 1)
            self.assertEqual(test_doc['modifies'][0]['target'], 'A')


if __name__ == '__main__':
    unittest.main()
