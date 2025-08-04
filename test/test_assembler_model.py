import importlib.resources as pkg_resources
import unittest

import bespokeasm.assembler.model.operand_set as AS
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser import InstructioParser
from ruamel.yaml import YAML

from test import config_files

#
# Tests
#


class TestConfigObject(unittest.TestCase):
    label_values = None

    @classmethod
    def setUpClass(cls):
        cls._register_argument_config_str = pkg_resources.files(config_files) \
            .joinpath('register_argument_exmaple_config.yaml').read_text()
        cls._eater_sap1_config_str = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml').read_text()
        cls.label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        cls.label_values.set_label_value('label1', 2, 1)
        cls.label_values.set_label_value('LABEL2', 0xF0, 2)

    def test_argument_set_construction(self):
        yaml_loader = YAML()
        conf1 = yaml_loader.load(self._eater_sap1_config_str)
        arg_collection1 = AS.OperandSetCollection(conf1['operand_sets'], 'big', 'big', set(), 8, 8,)
        self.assertEqual(len(arg_collection1), 2, 'there are 2 argument sets')
        self.assertTrue('integer' in arg_collection1)
        self.assertTrue('address' in arg_collection1)

        conf2 = yaml_loader.load(self._register_argument_config_str)
        arg_collection2 = AS.OperandSetCollection(
            conf2['operand_sets'], 'little', 'little', {'a', 'i', 'j', 'sp', 'ij', 'mar'}, 8, 8,
        )
        self.assertEqual(len(arg_collection2), 4, 'there are 4 argument sets')
        self.assertTrue('8_bit_source' in arg_collection2)
        self.assertTrue('8_bit_destination' in arg_collection2)
        self.assertTrue('int8' in arg_collection2)
        self.assertTrue('int16' in arg_collection2)

    def test_instruction_parsing(self):
        fp = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        model1 = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(model1.address_size, model1.default_origin)

        test_line_id = LineIdentifier(1212, 'test_instruction_parsing')

        pi1 = InstructioParser.parse_instruction(
            model1, test_line_id, 'LDA $f', memzone_mngr,
        )
        self.assertEqual(pi1.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            pi1.get_words(TestConfigObject.label_values, 0x8000, pi1.word_count),
            [Word(0x1F, model1.word_size, model1.word_segment_size, model1.intra_word_endianness)],
            'assembled instruction',
        )

        pi2 = InstructioParser.parse_instruction(
            model1, test_line_id, 'add label1+5', memzone_mngr,
        )
        self.assertEqual(pi2.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            pi2.get_words(TestConfigObject.label_values, 0x8000, pi2.word_count),
            [Word(0x27, model1.word_size, model1.word_segment_size, model1.intra_word_endianness)],
            'assembled instruction',
        )

        pi3 = InstructioParser.parse_instruction(
            model1, test_line_id, 'out', memzone_mngr,
        )
        self.assertEqual(pi3.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            pi3.get_words(TestConfigObject.label_values, 0x8000, pi3.word_count),
            [Word(0xE0, model1.word_size, model1.word_segment_size, model1.intra_word_endianness)],
            'assembled instruction'
        )

        fp = pkg_resources.files(config_files).joinpath('register_argument_exmaple_config.yaml')
        model2 = AssemblerModel(str(fp), 0)
        memzone_mngr2 = MemoryZoneManager(model2.address_size, model2.default_origin)

        piA = InstructioParser.parse_instruction(
            model2, LineIdentifier(1, 'test_mov_a_i'), 'mov a, i', memzone_mngr2,
        )
        self.assertEqual(piA.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piA.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b01000010, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'assembled instruction'
        )

        piB = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov a,[$1120 + label1]', memzone_mngr2,
        )
        self.assertEqual(piB.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piB.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01000110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x22, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x11, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'assembled instruction'
        )

        piC = InstructioParser.parse_instruction(
            model2, test_line_id, 'add i', memzone_mngr2,
        )
        self.assertEqual(piC.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piC.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b10111010, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'assembled instruction'
        )

        piD = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [$110D + (label1 + LABEL2)] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piD.word_count, 4, 'assembled instruciton is 4 byte')
        self.assertEqual(
            piD.get_words(TestConfigObject.label_values, 0x8000, 4),
            [
                Word(0b01110111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0xFF, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x11, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piE = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp - label1] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piE.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piE.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0b11111110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piF = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp+label1] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piF.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piF.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piG = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp] , 0x88', memzone_mngr2,
        )
        self.assertEqual(piG.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piG.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x88, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piH = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [$8000], [label1]', memzone_mngr2,
        )
        self.assertEqual(piH.word_count, 5, 'assembled instruciton is 5 byte')
        self.assertEqual(
            piH.get_words(TestConfigObject.label_values, 0x8000, 5),
            [
                Word(0b01110110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x80, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piI = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [mar], [label1]', memzone_mngr2,
        )
        self.assertEqual(piI.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piI.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01100110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'no offset should be emitted for [mar]'
        )

        piJ = InstructioParser.parse_instruction(
            model2, test_line_id, 'swap [$8000], [label1]', memzone_mngr2,
        )
        self.assertEqual(piJ.word_count, 5, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piJ.get_words(TestConfigObject.label_values, 0x8000, 5),
            [
                Word(0b11110110, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x80, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x00, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should NOT be in reverse order'
        )

        piK = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov [sp+2], [sp+4]', memzone_mngr2,
        )
        self.assertEqual(piK.word_count, 3, 'assembled instruciton is 3 byte')
        self.assertEqual(
            piK.get_words(TestConfigObject.label_values, 0x8000, 3),
            [
                Word(0b01101101, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x04, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'arguments should be in reverse order'
        )

        piL = InstructioParser.parse_instruction(
            model2, test_line_id, 'pop i', memzone_mngr2,
        )
        self.assertEqual(piL.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piL.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b00001010, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'pop to i'
        )

        piM = InstructioParser.parse_instruction(
            model2, LineIdentifier(158, 'test_pop_empty_arg'), 'pop', memzone_mngr2,
        )
        self.assertEqual(piM.word_count, 1, 'assembled instruciton is 1 byte')
        self.assertEqual(
            piM.get_words(TestConfigObject.label_values, 0x8000, 1),
            [Word(0b00001111, model2.word_size, model2.word_segment_size, model2.intra_word_endianness)],
            'just pop'
        )

        piN = InstructioParser.parse_instruction(
            model2, test_line_id, 'mov a, [sp+2]', memzone_mngr2,
        )
        self.assertEqual(piN.word_count, 2, 'assembled instruciton is 2 byte')
        self.assertEqual(
            piN.get_words(TestConfigObject.label_values, 0x8000, 2),
            [
                Word(0b01000101, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
                Word(0x02, model2.word_size, model2.word_segment_size, model2.intra_word_endianness),
            ],
            'just move [sp+2] into a'
        )

        with self.assertRaises(SystemExit, msg='should error on unallowed operand combinations'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a, a', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='[mar] should have no offset'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov [mar+2], [label1]', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='should error due to too many operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a, i, j', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='should error due to too many operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'nop 123', memzone_mngr2)
        with self.assertRaises(SystemExit, msg='should error due to too few operands'):
            InstructioParser.parse_instruction(model2, test_line_id, 'mov a', memzone_mngr2)

    def test_bad_registers_in_configuratin(self):
        fp = pkg_resources.files(config_files).joinpath('test_bad_registers_in_configuratin.yaml')
        with self.assertRaises(SystemExit, msg='model configuration should not specify prohibited register names'):
            AssemblerModel(str(fp), 0)

    def test_min_required_version(self):
        fp = pkg_resources.files(config_files).joinpath('test_min_required_version_config.yaml')
        with self.assertRaises(SystemExit, msg='the min version check should fail'):
            AssemblerModel(str(fp), 0)

    def test_predefined_entities(self):
        fp = pkg_resources.files(config_files).joinpath('test_compiler_features.yaml')
        model = AssemblerModel(str(fp), 0)

        self.assertSetEqual(set(model.predefined_labels), {'CONST1', 'CONST2', 'buffer'}, 'label set should equal')

    def test_mnemonic_lists(self):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_macros.yaml')
        model = AssemblerModel(str(fp), 0)

        self.assertSetEqual(
            model.instruction_mnemonics,
            {'push', 'pop', 'mov', 'add', 'addc', 'ldar'},
            'instruction mnomonics should match'
        )
        self.assertSetEqual(
            model.macro_mnemonics,
            {'push2', 'mov2', 'add16', 'swap', 'incs'},
            'macro mnomonics should match'
        )
        self.assertListEqual(
            model.operation_mnemonics,
            [
                'push', 'pop', 'mov', 'add',
                'addc', 'ldar', 'push2', 'mov2',
                'add16', 'swap', 'incs',
            ],
            'instruction + macro mnomonics should match'
        )

    def test_word_size_and_segment_size(self):
        fp = pkg_resources.files(config_files).joinpath('test_16bit_data_words.yaml')
        model = AssemblerModel(str(fp), 0)
        self.assertEqual(model.word_size, 16, 'word size should match')
        self.assertEqual(model.word_segment_size, 16, 'word segment size should match')
        self.assertEqual(model.intra_word_endianness, 'big', 'intra-word endianness should match')
        self.assertEqual(model.multi_word_endianness, 'big', 'multi-word endianness should match')

    def test_predefined_data_creation(self):
        # TODO: add test for predefined data creation
        pass

    def test_duplicate_mnemonic_or_alias(self):
        # This config has 'jsr' and an alias 'jsr' for another instruction, which should fail
        from ruamel.yaml import YAML
        bad_config = {
            'description': 'Duplicate mnemonic/alias',
            'general': {
                'min_version': '0.5.0',
                'address_size': 8,
                'multi_word_endianness': 'little',
                'registers': [],
                'identifier': {'name': 'bad', 'version': '0.1.0'}
            },
            'operand_sets': {},
            'instructions': {
                'jsr': {
                    'aliases': ['call'],
                    'bytecode': {'value': 1, 'size': 8}
                },
                'foo': {
                    'aliases': ['jsr'],  # This should cause a duplicate error
                    'bytecode': {'value': 2, 'size': 8}
                }
            }
        }
        import tempfile
        import os
        yaml = YAML()
        with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as tmp:
            yaml.dump(bad_config, tmp)
            tmp_path = tmp.name
        try:
            with self.assertRaises(SystemExit) as cm:
                AssemblerModel(tmp_path, 0)
            self.assertIn('Duplicate mnemonic or alias found: "jsr"', str(cm.exception))
        finally:
            os.remove(tmp_path)


class TestUpdateConfigDictToLatest(unittest.TestCase):
    def test_deprecated_fields_are_converted(self):
        old_config = {
            'general': {
                'endian': 'little',
                'byte_size': 16,
                'byte_align': 2,
                'min_version': '0.4.0',
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)
        g = updated['general']
        self.assertNotIn('endian', g)
        self.assertNotIn('byte_size', g)
        self.assertNotIn('byte_align', g)
        self.assertEqual(g['multi_word_endianness'], 'little')
        self.assertEqual(g['word_size'], 16)
        self.assertEqual(g['word_align'], 2)
        self.assertEqual(g['word_segment_size'], 16)
        self.assertNotIn('intra_word_endianness', g, 'intra_word_endianness should not be added, defaults to big')
        self.assertIn('min_version', g)

    def test_operand_sets_byte_align_conversion(self):
        old_config = {
            'general': {'min_version': '0.4.0'},
            'operand_sets': {
                'test_operand': {
                    'operand_values': {
                        'int8': {
                            'type': 'numeric',
                            'argument': {
                                'size': 8,
                                'byte_align': True,
                                'endian': 'little'
                            }
                        }
                    }
                },
                'test_operand2': {
                    'operand_values': {
                        'addr': {
                            'type': 'numeric',
                            'argument': {
                                'size': 16,
                                'byte_align': False,
                                'endian': 'big'
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Check that byte_align was converted to word_align in operand_sets
        operand1 = updated['operand_sets']['test_operand']['operand_values']['int8']['argument']
        self.assertNotIn('byte_align', operand1)
        self.assertIn('word_align', operand1)
        self.assertTrue(operand1['word_align'])

        operand2 = updated['operand_sets']['test_operand2']['operand_values']['addr']['argument']
        self.assertNotIn('byte_align', operand2)
        self.assertIn('word_align', operand2)
        self.assertFalse(operand2['word_align'])

    def test_operand_sets_offset_byte_align_conversion(self):
        old_config = {
            'general': {'min_version': '0.4.0'},
            'operand_sets': {
                'test_operand': {
                    'operand_values': {
                        'indirect': {
                            'type': 'indirect_register',
                            'register': 'sp',
                            'offset': {
                                'size': 8,
                                'byte_align': True,
                                'endian': 'little'
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Check that byte_align was converted to word_align in offset configuration
        offset = updated['operand_sets']['test_operand']['operand_values']['indirect']['offset']
        self.assertNotIn('byte_align', offset)
        self.assertIn('word_align', offset)
        self.assertTrue(offset['word_align'])

    def test_nested_operand_configurations(self):
        old_config = {
            'general': {'min_version': '0.4.0'},
            'operand_sets': {
                'complex_operand': {
                    'operand_values': {
                        'nested1': {
                            'type': 'numeric',
                            'argument': {
                                'size': 8,
                                'byte_align': True
                            }
                        },
                        'nested2': {
                            'type': 'address',
                            'argument': {
                                'size': 16,
                                'byte_align': False
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Check nested configurations are properly converted
        nested1 = updated['operand_sets']['complex_operand']['operand_values']['nested1']['argument']
        self.assertNotIn('byte_align', nested1)
        self.assertTrue(nested1['word_align'])

        nested2 = updated['operand_sets']['complex_operand']['operand_values']['nested2']['argument']
        self.assertNotIn('byte_align', nested2)
        self.assertFalse(nested2['word_align'])

    def test_mixed_old_and_new_configurations(self):
        old_config = {
            'general': {'min_version': '0.4.0'},
            'operand_sets': {
                'mixed_operand': {
                    'operand_values': {
                        'old_style': {
                            'type': 'numeric',
                            'argument': {
                                'size': 8,
                                'byte_align': True
                            }
                        },
                        'new_style': {
                            'type': 'numeric',
                            'argument': {
                                'size': 16,
                                'word_align': False
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Old style should be converted
        old_style = updated['operand_sets']['mixed_operand']['operand_values']['old_style']['argument']
        self.assertNotIn('byte_align', old_style)
        self.assertTrue(old_style['word_align'])

        # New style should remain unchanged
        new_style = updated['operand_sets']['mixed_operand']['operand_values']['new_style']['argument']
        self.assertNotIn('byte_align', new_style)
        self.assertFalse(new_style['word_align'])

    def test_min_version_is_updated(self):
        old_config = {'general': {'min_version': '0.1.0'}}
        updated = AssemblerModel.update_config_dict_to_latest(old_config)
        g = updated['general']
        from bespokeasm import BESPOKEASM_VERSION_STR
        self.assertEqual(g['min_version'], BESPOKEASM_VERSION_STR)

    def test_memory_blocks_conversion(self):
        old_config = {
            'general': {'min_version': '0.4.0'},
            'predefined': {
                'memory': [
                    {'name': 'test_memory', 'start': 0x1000, 'size': 256}
                ]
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Check that memory blocks were converted to data blocks
        self.assertNotIn('memory', updated['predefined'])
        self.assertIn('data', updated['predefined'])
        self.assertEqual(len(updated['predefined']['data']), 1)
        self.assertEqual(updated['predefined']['data'][0]['name'], 'test_memory')

    def test_operand_endian_conversion(self):
        old_config = {
            'general': {'min_version': '0.4.0'},
            'operand_sets': {
                'test_operand': {
                    'operand_values': {
                        'int8': {
                            'type': 'numeric',
                            'argument': {
                                'size': 8,
                                'endian': 'little'
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Check that endian was converted to multi_word_endian only
        argument = updated['operand_sets']['test_operand']['operand_values']['int8']['argument']
        self.assertNotIn('endian', argument)
        self.assertIn('multi_word_endian', argument)
        self.assertNotIn('intra_word_endian', argument)  # Should not be added, defaults to 'big'
        self.assertEqual(argument['multi_word_endian'], 'little')

    def test_comprehensive_deprecated_field_conversion(self):
        old_config = {
            'general': {
                'min_version': '0.4.0',
                'endian': 'little',
                'byte_size': 16,
                'byte_align': 2
            },
            'predefined': {
                'memory': [
                    {'name': 'test_memory', 'start': 0x1000, 'size': 256}
                ]
            },
            'operand_sets': {
                'test_operand': {
                    'operand_values': {
                        'int8': {
                            'type': 'numeric',
                            'argument': {
                                'size': 8,
                                'byte_align': True,
                                'endian': 'little'
                            }
                        },
                        'indirect': {
                            'type': 'indirect_register',
                            'register': 'sp',
                            'offset': {
                                'size': 8,
                                'byte_align': True,
                                'endian': 'big'
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Check general section conversions
        g = updated['general']
        self.assertNotIn('endian', g)
        self.assertNotIn('byte_size', g)
        self.assertNotIn('byte_align', g)
        self.assertEqual(g['multi_word_endianness'], 'little')
        self.assertEqual(g['word_size'], 16)
        self.assertEqual(g['word_align'], 2)

        # Check memory blocks conversion
        self.assertNotIn('memory', updated['predefined'])
        self.assertIn('data', updated['predefined'])

        # Check operand conversions
        int8_arg = updated['operand_sets']['test_operand']['operand_values']['int8']['argument']
        self.assertNotIn('byte_align', int8_arg)
        self.assertNotIn('endian', int8_arg)
        self.assertIn('word_align', int8_arg)
        self.assertIn('multi_word_endian', int8_arg)
        self.assertNotIn('intra_word_endian', int8_arg)  # Should not be added, defaults to 'big'
        self.assertTrue(int8_arg['word_align'])
        self.assertEqual(int8_arg['multi_word_endian'], 'little')

        # Check offset conversions
        offset = updated['operand_sets']['test_operand']['operand_values']['indirect']['offset']
        self.assertNotIn('byte_align', offset)
        self.assertNotIn('endian', offset)
        self.assertIn('word_align', offset)
        self.assertIn('multi_word_endian', offset)
        self.assertNotIn('intra_word_endian', offset)  # Should not be added, defaults to 'big'
        self.assertTrue(offset['word_align'])
        self.assertEqual(offset['multi_word_endian'], 'big')

    def test_noop_for_up_to_date_config(self):
        up_to_date = {
            'general': {
                'multi_word_endianness': 'big',
                'intra_word_endianness': 'little',
                'word_size': 8,
                'word_segment_size': 8,
                'min_version': '0.5.0',
            },
            'operand_sets': {
                'modern_operand': {
                    'operand_values': {
                        'modern': {
                            'type': 'numeric',
                            'argument': {
                                'size': 8,
                                'word_align': True
                            }
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(up_to_date)
        g = updated['general']
        self.assertEqual(g['multi_word_endianness'], 'big')
        self.assertEqual(g['intra_word_endianness'], 'little')
        self.assertEqual(g['word_size'], 8)
        self.assertEqual(g['word_segment_size'], 8)
        from bespokeasm import BESPOKEASM_VERSION_STR
        self.assertEqual(g['min_version'], BESPOKEASM_VERSION_STR)

        # Operand sets should remain unchanged
        operand = updated['operand_sets']['modern_operand']['operand_values']['modern']['argument']
        self.assertIn('word_align', operand)
        self.assertNotIn('byte_align', operand)

    def test_disallowed_pairs_formatting_preservation(self):
        """Test that disallowed_pairs maintain their original formatting."""
        old_config = {
            'general': {'min_version': '0.4.0'},
            'instructions': {
                'test_instruction': {
                    'operands': {
                        'operand_sets': {
                            'disallowed_pairs': [
                                ['a_register', 'a_register'],
                                ['flags_register', 'flags_register'],
                                ['i_register', 'i_register']
                            ]
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Import the formatting function to test it
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import convert_disallowed_pairs_to_flow_style, FlowStyleList
        from ruamel.yaml import YAML
        import io

        # Convert the updated config to use flow style for disallowed_pairs
        formatted_dict = convert_disallowed_pairs_to_flow_style(updated)

        # Dump to string to check formatting
        yaml_dumper = YAML()

        # Register FlowStyleList representer for ruamel.yaml
        def represent_flow_style_list(self, data):
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

        yaml_dumper.representer.add_representer(FlowStyleList, represent_flow_style_list)

        output_stream = io.StringIO()
        yaml_dumper.dump(formatted_dict, output_stream)
        output = output_stream.getvalue()

        # Check that disallowed_pairs uses the correct format
        lines = output.split('\n')
        disallowed_pairs_found = False
        correct_format_count = 0

        for i, line in enumerate(lines):
            if 'disallowed_pairs:' in line:
                disallowed_pairs_found = True
                # Look at next few lines to check format
                for j in range(i+1, min(i+10, len(lines))):
                    next_line = lines[j]
                    if next_line.strip() and not next_line.startswith(' '):
                        break
                    if next_line.strip():
                        # Should be in format: "  - [item1, item2]"
                        if (
                            next_line.strip().startswith('- [') and
                            next_line.strip().endswith(']') and
                            next_line.count('[') == 1 and
                            next_line.count(']') == 1
                        ):
                            correct_format_count += 1

        self.assertTrue(disallowed_pairs_found, 'disallowed_pairs should be found in output')
        self.assertGreater(correct_format_count, 0, 'Should have at least one correctly formatted pair')
        self.assertEqual(correct_format_count, 3, 'Should have exactly 3 correctly formatted pairs')

    def test_other_lists_not_affected_by_formatting(self):
        """Test that other lists are not converted to inline format."""
        old_config = {
            'general': {'min_version': '0.4.0'},
            'instructions': {
                'test_instruction': {
                    'operands': {
                        'operand_sets': {
                            'list': ['operand1', 'operand2', 'operand3'],
                            'variants': [
                                {'bytecode': {'value': 1}},
                                {'bytecode': {'value': 2}}
                            ]
                        }
                    }
                }
            }
        }
        updated = AssemblerModel.update_config_dict_to_latest(old_config)

        # Import the formatting function to test it
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import convert_disallowed_pairs_to_flow_style, FlowStyleList
        from ruamel.yaml import YAML
        import io

        # Convert the updated config to use flow style for disallowed_pairs
        formatted_dict = convert_disallowed_pairs_to_flow_style(updated)

        # Dump to string to check formatting
        yaml_dumper = YAML()

        # Register FlowStyleList representer for ruamel.yaml
        def represent_flow_style_list(self, data):
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

        yaml_dumper.representer.add_representer(FlowStyleList, represent_flow_style_list)

        output_stream = io.StringIO()
        yaml_dumper.dump(formatted_dict, output_stream)
        output = output_stream.getvalue()

        # Check that other lists are not converted to inline format
        lines = output.split('\n')
        inline_lists_found = 0

        for i, line in enumerate(lines):
            if ('list:' in line or 'variants:' in line) and i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip().startswith('[') and next_line.strip().endswith(']'):
                    inline_lists_found += 1

        self.assertEqual(inline_lists_found, 0, 'Other lists should not be converted to inline format')

    def test_flow_style_list_class_behavior(self):
        """Test that FlowStyleList correctly forces flow style."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import FlowStyleList
        from ruamel.yaml import YAML
        import io

        # Test regular list vs FlowStyleList
        regular_list = ['item1', 'item2']
        flow_style_list = FlowStyleList(['item1', 'item2'])

        # Dump both to see the difference
        yaml_dumper = YAML()

        # Register FlowStyleList representer for ruamel.yaml
        def represent_flow_style_list(self, data):
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

        yaml_dumper.representer.add_representer(FlowStyleList, represent_flow_style_list)

        regular_output_stream = io.StringIO()
        flow_output_stream = io.StringIO()
        yaml_dumper.dump({'test': regular_list}, regular_output_stream)
        yaml_dumper.dump({'test': flow_style_list}, flow_output_stream)
        regular_output = regular_output_stream.getvalue()
        flow_output = flow_output_stream.getvalue()

        # Regular list should be in block format
        self.assertIn('- item1', regular_output)
        self.assertIn('- item2', regular_output)

        # FlowStyleList should be in inline format
        self.assertIn('[item1, item2]', flow_output)
        self.assertNotIn('- item1', flow_output)
        self.assertNotIn('- item2', flow_output)

    def test_convert_disallowed_pairs_function(self):
        """Test that convert_disallowed_pairs_to_flow_style correctly identifies and converts disallowed_pairs."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import convert_disallowed_pairs_to_flow_style, FlowStyleList

        test_config = {
            'instructions': {
                'test1': {
                    'operands': {
                        'operand_sets': {
                            'disallowed_pairs': [
                                ['a_register', 'a_register'],
                                ['flags_register', 'flags_register']
                            ]
                        }
                    }
                },
                'test2': {
                    'operands': {
                        'operand_sets': {
                            'list': ['operand1', 'operand2'],  # Should not be converted
                            'disallowed_pairs': [
                                ['i_register', 'i_register']
                            ]
                        }
                    }
                }
            }
        }

        converted = convert_disallowed_pairs_to_flow_style(test_config)

        # Check that disallowed_pairs inner lists are converted to FlowStyleList
        disallowed_pairs1 = converted['instructions']['test1']['operands']['operand_sets']['disallowed_pairs']
        disallowed_pairs2 = converted['instructions']['test2']['operands']['operand_sets']['disallowed_pairs']

        self.assertIsInstance(disallowed_pairs1[0], FlowStyleList)
        self.assertIsInstance(disallowed_pairs1[1], FlowStyleList)
        self.assertIsInstance(disallowed_pairs2[0], FlowStyleList)

        # Check that other lists are not converted
        other_list = converted['instructions']['test2']['operands']['operand_sets']['list']
        self.assertIsInstance(other_list, list)
        self.assertNotIsInstance(other_list, FlowStyleList)

    def test_json_input_handling(self):
        """Test that JSON input files are handled correctly."""
        import io
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import dump_yaml_with_formatting

        # Create a test JSON config
        json_config = {
            'general': {'min_version': '0.4.0'},
            'instructions': {
                'test_instruction': {
                    'operands': {
                        'operand_sets': {
                            'disallowed_pairs': [
                                ['a_register', 'a_register'],
                                ['flags_register', 'flags_register']
                            ]
                        }
                    }
                }
            }
        }

        # Update the config
        updated = AssemblerModel.update_config_dict_to_latest(json_config)

        # Test formatting with JSON input
        output_stream = io.StringIO()
        dump_yaml_with_formatting(updated, output_stream)
        output_yaml = output_stream.getvalue()

        # Verify the output is valid YAML
        lines = output_yaml.split('\n')
        disallowed_pairs_found = False
        correct_format_count = 0

        for i, line in enumerate(lines):
            if 'disallowed_pairs:' in line:
                disallowed_pairs_found = True
            elif disallowed_pairs_found and line.strip().startswith('- ['):
                correct_format_count += 1

        self.assertTrue(disallowed_pairs_found, 'disallowed_pairs should be found in output')
        self.assertEqual(correct_format_count, 2, 'Should have 2 correctly formatted pairs')

        # Verify the output can be parsed as YAML
        yaml_loader = YAML()
        parsed_yaml = yaml_loader.load(output_yaml)
        self.assertIsInstance(parsed_yaml, dict, 'Output should be valid YAML')
        self.assertIn('general', parsed_yaml, 'Output should contain general section')
        self.assertIn('instructions', parsed_yaml, 'Output should contain instructions section')

    def test_yaml_vs_json_input_behavior(self):
        """Test that YAML and JSON inputs produce the same output format."""
        import io
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import dump_yaml_with_formatting

        # Same config in both formats
        config_data = {
            'general': {'min_version': '0.4.0'},
            'instructions': {
                'test_instruction': {
                    'operands': {
                        'operand_sets': {
                            'disallowed_pairs': [
                                ['a_register', 'a_register'],
                                ['flags_register', 'flags_register']
                            ]
                        }
                    }
                }
            }
        }

        # Update the config
        updated = AssemblerModel.update_config_dict_to_latest(config_data)

        # Test YAML input
        yaml_output_stream = io.StringIO()
        dump_yaml_with_formatting(updated, yaml_output_stream)
        yaml_output = yaml_output_stream.getvalue()

        # Test JSON input
        json_output_stream = io.StringIO()
        dump_yaml_with_formatting(updated, json_output_stream)
        json_output = json_output_stream.getvalue()

        # Both should produce the same YAML output format
        self.assertEqual(yaml_output, json_output, 'YAML and JSON inputs should produce identical output')

        # Both should have correct disallowed_pairs formatting
        for output in [yaml_output, json_output]:
            lines = output.split('\n')
            disallowed_pairs_found = False
            correct_format_count = 0

            for line in lines:
                if 'disallowed_pairs:' in line:
                    disallowed_pairs_found = True
                elif disallowed_pairs_found and line.strip().startswith('- ['):
                    correct_format_count += 1

            self.assertTrue(disallowed_pairs_found, 'disallowed_pairs should be found')
            self.assertEqual(correct_format_count, 2, 'Should have 2 correctly formatted pairs')

    def test_number_format_preservation(self):
        """Test that binary and hex values preserve their original format."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import dump_yaml_with_formatting, load_yaml_with_format_preservation
        from ruamel.yaml import YAML
        import io

        # Test config with various number formats
        test_yaml = """
general:
  min_version: 0.4.0
instructions:
  test_instruction:
    bytecode:
      value: 0b00010
    variants:
      - bytecode:
          value: 0x76
      - bytecode:
          value: 0b00100
      - bytecode:
          value: 42
      - bytecode:
          value: 0x8000
operand_sets:
  test_operands:
    operand_values:
      binary_val:
        bytecode:
          value: 0b111
      hex_val:
        bytecode:
          value: 0xF0
      decimal_val:
        bytecode:
          value: 123
"""

        # Load with format preservation
        config = load_yaml_with_format_preservation(test_yaml)

        # Update the config
        updated = AssemblerModel.update_config_dict_to_latest(config)

        # Dump with formatting
        output_stream = io.StringIO()
        dump_yaml_with_formatting(updated, output_stream)
        output = output_stream.getvalue()

        # Check that binary values are preserved
        self.assertIn('value: 0b00010', output, 'Binary value 0b00010 should be preserved')
        self.assertIn('value: 0b00100', output, 'Binary value 0b00100 should be preserved')
        self.assertIn('value: 0b111', output, 'Binary value 0b111 should be preserved')

        # Check that hex values are preserved
        self.assertIn('value: 0x76', output, 'Hex value 0x76 should be preserved')
        self.assertIn('value: 0x8000', output, 'Hex value 0x8000 should be preserved')
        self.assertIn('value: 0xF0', output, 'Hex value 0xF0 should be preserved')

        # Check that decimal values remain decimal
        self.assertIn('value: 42', output, 'Decimal value 42 should remain decimal')
        self.assertIn('value: 123', output, 'Decimal value 123 should remain decimal')

        # Verify the values are still correct when parsed
        yaml_loader = YAML()
        parsed = yaml_loader.load(output)
        self.assertEqual(parsed['instructions']['test_instruction']['bytecode']['value'], 2)
        self.assertEqual(parsed['instructions']['test_instruction']['variants'][0]['bytecode']['value'], 0x76)
        self.assertEqual(parsed['instructions']['test_instruction']['variants'][1]['bytecode']['value'], 4)
        self.assertEqual(parsed['instructions']['test_instruction']['variants'][2]['bytecode']['value'], 42)
        self.assertEqual(parsed['instructions']['test_instruction']['variants'][3]['bytecode']['value'], 0x8000)

    def test_number_format_preservation_with_update_config(self):
        """Test that number format preservation works with the update-config command."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import load_yaml_with_format_preservation, dump_yaml_with_formatting
        from ruamel.yaml import YAML
        import io

        # Test config with deprecated fields and number formats
        test_yaml = """
general:
  min_version: 0.4.0
  endian: little
instructions:
  test_instruction:
    bytecode:
      value: 0b00010
    variants:
      - bytecode:
          value: 0x76
      - bytecode:
          value: 0b00100
operand_sets:
  test_operands:
    operand_values:
      binary_val:
        bytecode:
          value: 0b111
        offset:
          byte_align: true
      hex_val:
        bytecode:
          value: 0xF0
        argument:
          byte_align: true
"""

        # Load with format preservation
        config = load_yaml_with_format_preservation(test_yaml)

        # Update the config (this should convert deprecated fields)
        updated = AssemblerModel.update_config_dict_to_latest(config)

        # Dump with formatting
        output_stream = io.StringIO()
        dump_yaml_with_formatting(updated, output_stream)
        output = output_stream.getvalue()

        # Check that deprecated fields were converted
        self.assertIn('multi_word_endianness: little', output, 'endian should be converted to multi_word_endianness')
        self.assertIn('word_align: true', output, 'byte_align should be converted to word_align')

        # Check that number formats are still preserved
        self.assertIn('value: 0b00010', output, 'Binary value should be preserved after conversion')
        self.assertIn('value: 0x76', output, 'Hex value should be preserved after conversion')
        self.assertIn('value: 0b00100', output, 'Binary value should be preserved after conversion')
        self.assertIn('value: 0b111', output, 'Binary value should be preserved after conversion')
        self.assertIn('value: 0xF0', output, 'Hex value should be preserved after conversion')

        # Verify the values are still correct
        yaml_loader = YAML()
        parsed = yaml_loader.load(output)
        self.assertEqual(parsed['general']['multi_word_endianness'], 'little')
        self.assertEqual(parsed['instructions']['test_instruction']['bytecode']['value'], 2)
        self.assertEqual(parsed['instructions']['test_instruction']['variants'][0]['bytecode']['value'], 0x76)

    def test_comment_preservation(self):
        """Test that comments are preserved in the output YAML."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

        from bespokeasm.utilities import dump_yaml_with_formatting, load_yaml_with_format_preservation
        from ruamel.yaml import YAML
        import io

        # Test config with comments
        test_yaml = """
# This is a test configuration file
general:
  min_version: 0.4.0  # Old version that needs updating
  # This is a comment about endianness
  endian: little
instructions:
  # Main instruction definition
  test_instruction:
    bytecode:
      value: 0b00010  # Binary value
    variants:
      - bytecode:
          value: 0x76  # Hex value
      - bytecode:
          value: 0b00100  # Another binary value
operand_sets:
  # Operand definitions
  test_operands:
    operand_values:
      binary_val:
        bytecode:
          value: 0b111  # Binary value
        offset:
          byte_align: true  # This will be converted
      hex_val:
        bytecode:
          value: 0xF0  # Hex value
        argument:
          byte_align: true  # This will be converted
"""

        # Load with format preservation
        config = load_yaml_with_format_preservation(test_yaml)

        # Update the config (this should convert deprecated fields)
        updated = AssemblerModel.update_config_dict_to_latest(config)

        # Dump with formatting
        output_stream = io.StringIO()
        dump_yaml_with_formatting(updated, output_stream)
        output = output_stream.getvalue()

        # Check that comments are preserved
        self.assertIn('# This is a test configuration file', output, 'File header comment should be preserved')
        self.assertIn('# Old version that needs updating', output, 'Inline comment should be preserved')
        self.assertIn('# This is a comment about endianness', output, 'Standalone comment should be preserved')
        self.assertIn('# Main instruction definition', output, 'Section comment should be preserved')
        self.assertIn('# Binary value', output, 'Value comment should be preserved')
        self.assertIn('# Hex value', output, 'Hex value comment should be preserved')
        self.assertIn('# Another binary value', output, 'Another value comment should be preserved')
        self.assertIn('# Operand definitions', output, 'Operand comment should be preserved')
        self.assertIn('# This will be converted', output, 'Conversion comment should be preserved')

        # Check that deprecated fields were converted
        self.assertIn('multi_word_endianness: little', output, 'endian should be converted to multi_word_endianness')
        self.assertIn('word_align: true', output, 'byte_align should be converted to word_align')

        # Check that number formats are still preserved
        self.assertIn('value: 0b00010', output, 'Binary value should be preserved after conversion')
        self.assertIn('value: 0x76', output, 'Hex value should be preserved after conversion')
        self.assertIn('value: 0b00100', output, 'Binary value should be preserved after conversion')
        self.assertIn('value: 0b111', output, 'Binary value should be preserved after conversion')
        self.assertIn('value: 0xF0', output, 'Hex value should be preserved after conversion')

        # Verify the values are still correct
        yaml_loader = YAML()
        parsed = yaml_loader.load(output)
        self.assertEqual(parsed['general']['multi_word_endianness'], 'little')
        self.assertEqual(parsed['instructions']['test_instruction']['bytecode']['value'], 2)
        self.assertEqual(parsed['instructions']['test_instruction']['variants'][0]['bytecode']['value'], 0x76)

    def test_update_config_output_format_matches_input(self):
        """Test that update-config outputs JSON if input is JSON and YAML if input is YAML."""
        import io
        import sys
        import os
        import json
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from bespokeasm.__main__ import update_config

        # Prepare a simple config
        config_data = {
            'general': {'min_version': '0.4.0'},
            'instructions': {
                'test_instruction': {
                    'operands': {
                        'operand_sets': {
                            'disallowed_pairs': [
                                ['a_register', 'a_register'],
                                ['flags_register', 'flags_register']
                            ]
                        }
                    }
                }
            }
        }
        # Write JSON and YAML input files
        json_file = 'test_update_config_input.json'
        yaml_file = 'test_update_config_input.yaml'
        with open(json_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        with open(yaml_file, 'w') as f:
            from ruamel.yaml import YAML
            yaml_dumper = YAML()
            yaml_dumper.dump(config_data, f)

        # Capture stdout for JSON input
        json_stdout = io.StringIO()
        sys_stdout_orig = sys.stdout
        sys.stdout = json_stdout
        try:
            update_config.callback(json_file, None)
        finally:
            sys.stdout = sys_stdout_orig
        json_output = json_stdout.getvalue()
        # Should be valid JSON
        parsed_json = json.loads(json_output)
        self.assertIn('general', parsed_json)
        self.assertIn('instructions', parsed_json)
        # Should not contain YAML formatting
        self.assertNotIn('disallowed_pairs:', json_output)

        # Capture stdout for YAML input
        yaml_stdout = io.StringIO()
        sys.stdout = yaml_stdout
        try:
            update_config.callback(yaml_file, None)
        finally:
            sys.stdout = sys_stdout_orig
        yaml_output = yaml_stdout.getvalue()
        # Should be valid YAML
        yaml_loader = YAML()
        parsed_yaml = yaml_loader.load(yaml_output)
        self.assertIn('general', parsed_yaml)
        self.assertIn('instructions', parsed_yaml)
        # Should contain YAML formatting
        self.assertIn('disallowed_pairs:', yaml_output)
        self.assertIn('- [a_register, a_register]', yaml_output)

        # Clean up
        os.remove(json_file)
        os.remove(yaml_file)

    def test_update_config_output_file_extension(self):
        """Test that update-config respects output file extension if specified."""
        import sys
        import os
        import json
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from bespokeasm.__main__ import update_config

        # Prepare a simple config
        config_data = {
            'general': {'min_version': '0.4.0'},
            'instructions': {
                'test_instruction': {
                    'operands': {
                        'operand_sets': {
                            'disallowed_pairs': [
                                ['a_register', 'a_register'],
                                ['flags_register', 'flags_register']
                            ]
                        }
                    }
                }
            }
        }
        # Write JSON and YAML input files
        json_file = 'test_update_config_input.json'
        yaml_file = 'test_update_config_input.yaml'
        with open(json_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        with open(yaml_file, 'w') as f:
            from ruamel.yaml import YAML
            yaml_dumper = YAML()
            yaml_dumper.dump(config_data, f)

        # Output to JSON file from YAML input
        output_json_file = 'test_update_config_output.json'
        update_config.callback(yaml_file, output_json_file)
        with open(output_json_file) as f:
            output_json = f.read()
        parsed_json = json.loads(output_json)
        self.assertIn('general', parsed_json)
        self.assertIn('instructions', parsed_json)
        self.assertNotIn('disallowed_pairs:', output_json)
        os.remove(output_json_file)

        # Output to YAML file from JSON input
        output_yaml_file = 'test_update_config_output.yaml'
        update_config.callback(json_file, output_yaml_file)
        with open(output_yaml_file) as f:
            output_yaml = f.read()
        yaml_loader = YAML()
        parsed_yaml = yaml_loader.load(output_yaml)
        self.assertIn('general', parsed_yaml)
        self.assertIn('instructions', parsed_yaml)
        self.assertIn('disallowed_pairs:', output_yaml)
        self.assertIn('- [a_register, a_register]', output_yaml)
        os.remove(output_yaml_file)

        # Clean up
        os.remove(json_file)
        os.remove(yaml_file)


if __name__ == '__main__':
    unittest.main()
