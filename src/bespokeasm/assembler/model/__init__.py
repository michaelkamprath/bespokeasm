import json
import os
import re
import sys
import warnings
from functools import cached_property
from typing import Literal

import click
from bespokeasm import BESPOKEASM_MIN_REQUIRED_STR
from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.assembler.keywords import ASSEMBLER_KEYWORD_SET
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.instruction_set import InstructionSet
from bespokeasm.assembler.model.operand_set import OperandSet
from bespokeasm.assembler.model.operand_set import OperandSetCollection
from packaging import version
from ruamel.yaml import YAML


class AssemblerModel:
    _config: dict

    def __init__(self, config_file_path: str, is_verbose: int):
        self._config_file = config_file_path
        self._global_label_scope = None

        if config_file_path.endswith('.json'):
            with open(config_file_path) as json_file:
                config_dict = json.load(json_file)
        elif config_file_path.endswith('.yaml'):
            yaml_loader = YAML()
            try:
                with open(config_file_path) as yaml_file:
                    config_dict = yaml_loader.load(yaml_file)
                if config_dict is None:
                    sys.exit('ERROR: Could not load YAML configuration file - file may be empty or invalid')
            except Exception as exc:
                sys.exit(f'ERROR: {exc}')
        else:
            sys.exit('ERROR: unknown ISA config file type')

        self._config = config_dict
        self._validate_config(is_verbose)

        # load ISA version information
        config_file_name = os.path.splitext(os.path.basename(config_file_path))[0]
        if 'identifier' in self._config['general']:
            self._isa_name = self._config['general']['identifier'].get('name', config_file_name)
            self._isa_version = str(self._config['general']['identifier'].get('version', '0.0.1')).strip()
            self._file_extension = self._config['general']['identifier'].get('extension', 'asm')
            # enforce semantic versioning
            version_match = re.match(
                r'^\s*' + version.VERSION_PATTERN + r'\s*$',
                self._isa_version,
                flags=re.IGNORECASE | re.VERBOSE,
            )
            if version_match is None:
                sys.exit(
                    f'ERROR - provide ISA version "{self._isa_version}" is not in semantic versioning '
                    f'format. See https://semver.org for details.'
                )
        else:
            self._isa_name = config_file_name
            self._isa_version = '0.0.1'
            self._file_extension = 'asm'
        self._isa_name = self._isa_name.strip().replace(' ', '_')
        self._isa_version = self._isa_version.strip()
        # set up registers
        registers = self._config['general'].get('registers', [])
        self._registers = set(registers if registers is not None else [])
        # check to see if any registers named with a keyword
        for reg in self._registers:
            if reg in ASSEMBLER_KEYWORD_SET:
                sys.exit(f'ERROR: the instruction set configuration file specified an unallowed register name: {reg}')
        self._operand_sets = OperandSetCollection(
            self._config['operand_sets'],
            self.multi_word_endianness,
            self.intra_word_endianness,
            self.registers,
            self.word_size,
            self.word_segment_size,
        )
        self._instructions = InstructionSet(
                self._config['instructions'],
                self._config.get('macros', None),
                self._operand_sets,
                self.multi_word_endianness,
                self.intra_word_endianness,
                self.registers,
                self.word_size,
                self.word_segment_size,
            )

    def _validate_config(self, is_verbose: int) -> None:
        '''Performs some validation checks on configuration dictionary'''
        # check to see if old-style "memory block" is defined
        if 'predefined' in self._config \
                and self._config['predefined'] is not None \
                and 'memory' in self._config['predefined']:
            sys.exit(
                'ERROR - ISA configuration file defines a predefined "memory" block. '
                'Memory blocks have been deprecated and replaced with "data" blocks.'
            )

        # ensure there is a general section
        if 'general' not in self._config:
            sys.exit('ERROR - ISA configuration file does not contain a "general" section.')

        # require min_version
        if 'min_version' not in self._config['general']:
            sys.exit('ERROR - ISA configuration file does not contain a required "min_version" field in the general section.')

        # what's the point if there is no instruction set?
        if 'instructions' not in self._config:
            sys.exit('ERROR - ISA configuration file does not contain an "instructions" section.')

        # Validate string_byte_packing option
        general = self._config['general']
        if general.get('string_byte_packing', False):
            word_size = general.get('word_size', 8)
            if word_size < 16 or word_size % 8 != 0:
                sys.exit('ERROR - "string_byte_packing" is only allowed if word_size is a multiple of 8 and at least 16.')
        # Validate string_byte_packing_fill
        fill = general.get('string_byte_packing_fill', 0)
        if not isinstance(fill, int) or not (0 <= fill <= 255):
            sys.exit('ERROR - "string_byte_packing_fill" must be an integer between 0 and 255.')

        # check for min required BespokeASM version
        if 'min_version' in self._config['general']:
            required_version = self._config['general']['min_version']
            if is_verbose > 0:
                click.echo(
                    f'The ISA configuration file requires BespokeASM version {required_version}. This '
                    f'version of BespokeASM is {BESPOKEASM_VERSION_STR}.'
                )
            if required_version > BESPOKEASM_VERSION_STR:
                sys.exit(
                    f'ERROR: the instruction set configuration file requires at least BespokeASM '
                    f'version {required_version}'
                )
            if required_version < BESPOKEASM_MIN_REQUIRED_STR:
                sys.exit(
                    f'ERROR: this version of BespokeASM requires a configuration file that minimally '
                    f'requires BespokeASM version {BESPOKEASM_MIN_REQUIRED_STR}'
                )

        # check to see if a GLOBAL memory sone was defined and has an illegal origin
        for zone in self.predefined_memory_zones:
            if zone['name'] == 'GLOBAL':
                if self.default_origin < zone['start']:
                    sys.exit(
                        f'ERROR: The ISA configuration file has redefined the GLOBAL memory zone and the '
                        f'default origin value of {self.default_origin} is less than the GLOBAL memory '
                        f'zone start value of {zone["start"]}.'
                    )

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        if 'description' in self._config:
            desc_str = self._config['description']
            return f'AssemblerModel("{desc_str}")'
        else:
            return 'AssemblerModel(*Undefined*)'

    @property
    def description(self) -> str:
        return self._config.get('description', 'BespokeASM Assembly')

    @property
    def isa_name(self) -> str:
        '''Name of language defined by this ISA model. Defaults to configuration file basename.'''
        return self._isa_name

    @property
    def isa_version(self) -> str:
        '''Version number of this ISA model. Must be in semantic version format, e.g. "0.2.4"'''
        return self._isa_version

    @property
    def assembly_file_extenions(self) -> str:
        return self._file_extension

    @property
    def endian(self) -> Literal['little', 'big']:
        warnings.warn(
            "The 'endian' general configuration option is deprecated and will be removed in a "
            "future version. Replace with 'multi_word_endianness'.",
            DeprecationWarning,
            stacklevel=2
        )
        if 'endian' in self._config['general']:
            return self._config['general']['endian']
        else:
            return 'big'

    @property
    def intra_word_endianness(self) -> Literal['little', 'big']:
        if 'intra_word_endianness' in self._config['general']:
            return self._config['general']['intra_word_endianness']
        else:
            return 'big'

    @property
    def multi_word_endianness(self) -> Literal['little', 'big']:
        if 'multi_word_endianness' in self._config['general']:
            return self._config['general']['multi_word_endianness']
        else:
            return 'big'

    @property
    def string_byte_packing(self) -> bool:
        '''Whether to pack string bytes tightly into words (for .byte/.cstr with quoted strings).'''
        return bool(self._config['general'].get('string_byte_packing', False))

    @property
    def string_byte_packing_fill(self) -> int:
        '''
        The byte value used to pad words when string_byte_packing is enabled and the string doesn't
        fill the word. Defaults to 0.
        '''
        return int(self._config['general'].get('string_byte_packing_fill', 0)) & 0xFF

    @property
    def cstr_terminator(self) -> int:
        if 'cstr_terminator' in self._config['general']:
            return int(self._config['general']['cstr_terminator']) & 0xFF
        else:
            return 0

    @property
    def address_size(self) -> int:
        '''The number of bits used to rerpesent a memory address'''
        return self._config['general']['address_size']

    @property
    def page_size(self) -> int:
        '''The number of bytes in a memory page'''
        return self._config['general'].get('page_size', 1)

    @property
    def word_size(self) -> int:
        '''The number of bits in a word. defaults to 8 bits.'''
        return self._config['general'].get('word_size', 8)

    @property
    def word_segment_size(self) -> int:
        '''The number of bits in a word segment. Defaults to the word size.'''
        return self._config['general'].get('word_segment_size', self.word_size)

    @property
    def registers(self) -> set[str]:
        return self._registers

    @property
    def operation_mnemonics(self) -> list[str]:
        '''returns list of all mnemonics, including instruction aliases and macros'''
        return self._instructions.operation_mnemonics

    @property
    def instruction_mnemonics(self) -> set[str]:
        '''returns a set of all instruction mnemonics, including aliases (not including macros)'''
        return self._instructions.instruction_mnemonics

    @property
    def macro_mnemonics(self) -> set[str]:
        '''returns a set of only defined macro mnemonics'''
        return self._instructions.macro_mnemonics

    @property
    def instructions(self) -> InstructionSet:
        return self._instructions

    def get_operand_set(self, operand_set_name: str) -> OperandSet:
        return self._operand_sets.get_operand_set(operand_set_name)

    @cached_property
    def default_origin(self) -> int:
        return self._config['general'].get('origin', 0)

    @cached_property
    def predefined_constants(self) -> list[dict[str, int]]:
        if 'predefined' in self._config and 'constants' in self._config['predefined']:
            return self._config['predefined']['constants']
        else:
            return []

    @cached_property
    def predefined_data_blocks(self) -> list[dict]:
        if 'predefined' in self._config and 'data' in self._config['predefined']:
            return self._config['predefined']['data']
        else:
            return []

    @cached_property
    def predefined_labels(self) -> list[str]:
        '''Provides a list of labels that were created by entities defined in the ISA model.
           Intend use is for creating syntax highlighting rules.
        '''
        results: list[str] = []
        for item in self.predefined_constants:
            results.append(item['name'])
        for item in self.predefined_data_blocks:
            results.append(item['name'])
        for item in self.predefined_memory_zones:
            results.append(item['name'])
        return results

    @cached_property
    def predefined_memory_zones(self) -> list[dict]:
        if 'predefined' in self._config \
                and self._config['predefined'] is not None \
                and 'memory_zones' in self._config['predefined']:
            return self._config['predefined']['memory_zones']
        else:
            return []

    @property
    def global_label_scope(self) -> LabelScope:
        if self._global_label_scope is None:
            self._global_label_scope = LabelScope.global_scope(self.registers)
            # add predefined constants to global scope
            predefines_lineid = LineIdentifier(0, os.path.basename(self._config_file))
            for predefined_constant in self.predefined_constants:
                label: str = predefined_constant['name']
                value: int = predefined_constant['value']
                self._global_label_scope.set_label_value(
                    label,
                    value,
                    predefines_lineid,
                    scope=LabelScopeType.GLOBAL,
                )
        return self._global_label_scope

    @property
    def predefined_symbols(self) -> list[dict]:
        if 'predefined' in self._config and 'symbols' in self._config['predefined']:
            return self._config['predefined']['symbols']
        else:
            return []

    @property
    def allow_embedded_strings(self) -> bool:
        return self._config['general'].get('allow_embedded_strings', False)

    @staticmethod
    def update_config_dict_to_latest(config_dict: dict) -> dict:
        """
        Given a config dict (as loaded from YAML/JSON), return a new dict updated to the latest config format.
        Applies upgrades based on the min_version field in the general section (if present).
        """
        from packaging import version
        from bespokeasm.utilities import CommentedMap, CommentedSeq

        def _update_recursive(obj, parent_key=None, in_general=False):
            if isinstance(obj, dict) or isinstance(obj, CommentedMap):
                result = obj.__class__() if isinstance(obj, CommentedMap) else {}
                for key, value in obj.items():
                    # Key renames and conversions
                    if in_general:
                        if key == 'endian':
                            result['multi_word_endianness'] = value
                            # Transfer comments if using ruamel.yaml
                            if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                                if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                    # Copy comments from old key to new key
                                    if key in obj.ca.items:
                                        result.ca.items['multi_word_endianness'] = obj.ca.items[key]
                        elif key == 'byte_size':
                            result['word_size'] = value
                            if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                                if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                    if key in obj.ca.items:
                                        result.ca.items['word_size'] = obj.ca.items[key]
                        elif key == 'byte_align':
                            result['word_align'] = value
                            if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                                if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                    if key in obj.ca.items:
                                        result.ca.items['word_align'] = obj.ca.items[key]
                        else:
                            result[key] = _update_recursive(value, key, in_general=True)
                            # Copy comments for non-renamed keys
                            if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                                if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                    if key in obj.ca.items:
                                        result.ca.items[key] = obj.ca.items[key]
                    elif key == 'byte_align':
                        result['word_align'] = value
                        if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                            if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                if key in obj.ca.items:
                                    result.ca.items['word_align'] = obj.ca.items[key]
                    elif key == 'endian':
                        result['multi_word_endian'] = value
                        if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                            if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                if key in obj.ca.items:
                                    result.ca.items['multi_word_endian'] = obj.ca.items[key]
                    elif key == 'memory' and parent_key == 'predefined':
                        result['data'] = _update_recursive(value, 'data')
                        if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                            if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                if key in obj.ca.items:
                                    result.ca.items['data'] = obj.ca.items[key]
                    else:
                        # Recurse, and detect if we're in the general section
                        result[key] = _update_recursive(value, key, in_general=(key == 'general'))
                        # Copy comments for non-renamed keys
                        if isinstance(obj, CommentedMap) and isinstance(result, CommentedMap):
                            if hasattr(obj, 'ca') and hasattr(result, 'ca'):
                                if key in obj.ca.items:
                                    result.ca.items[key] = obj.ca.items[key]
                return result
            elif isinstance(obj, list) or isinstance(obj, CommentedSeq):
                if isinstance(obj, CommentedSeq):
                    result = obj.__class__()
                    for item in obj:
                        result.append(_update_recursive(item, parent_key))
                    return result
                else:
                    return [_update_recursive(item, parent_key) for item in obj]
            else:
                # Always use the original value for leaves
                return obj

        updated = _update_recursive(config_dict)

        # Preserve file-level comments if using ruamel.yaml
        if isinstance(config_dict, CommentedMap) and isinstance(updated, CommentedMap):
            if hasattr(config_dict, 'ca') and hasattr(updated, 'ca'):
                # Copy file-level comments
                if hasattr(config_dict.ca, 'comment') and config_dict.ca.comment:
                    updated.ca.comment = config_dict.ca.comment

        general = updated.setdefault('general', {})
        min_version = general.get('min_version', None)

        # If no min_version, or min_version < 0.5.0, apply 0.5.0+ upgrades
        if min_version is None or version.parse(str(min_version)) < version.parse('0.5.0'):
            # Set defaults for new fields if missing
            if 'multi_word_endianness' not in general:
                general['multi_word_endianness'] = 'big'
            if 'word_size' not in general:
                general['word_size'] = 8
            if 'word_segment_size' not in general:
                general['word_segment_size'] = general['word_size']
            # Remove any other deprecated fields if present
            for deprecated in ['endian', 'byte_size', 'byte_align']:
                if deprecated in general:
                    del general[deprecated]

        # Always update min_version to the current minimum required
        from bespokeasm import BESPOKEASM_VERSION_STR
        general['min_version'] = BESPOKEASM_VERSION_STR

        return updated
