import click
import json
import os
from packaging import version
import re
import sys
import yaml

from bespokeasm import BESPOKEASM_VERSION_STR, BESPOKEASM_MIN_REQUIRED_STR
from bespokeasm.assembler.keywords import ASSEMBLER_KEYWORD_SET
from bespokeasm.assembler.model.instruction_set import InstructionSet
from bespokeasm.assembler.model.operand_set import OperandSet, OperandSetCollection
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier


class AssemblerModel:
    _config: dict

    def __init__(self, config_file_path: str, is_verbose: int):
        self._config_file = config_file_path
        self._global_label_scope = None

        if config_file_path.endswith('.json'):
            with open(config_file_path, 'r') as json_file:
                config_dict = json.load(json_file)
        elif config_file_path.endswith('.yaml'):
            with open(config_file_path, 'r') as yaml_file:
                try:
                    config_dict = yaml.safe_load(yaml_file)
                except yaml.YAMLError as exc:
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
                r"^\s*" + version.VERSION_PATTERN + r"\s*$",
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
        self._operand_sets = OperandSetCollection(self._config['operand_sets'], self.endian, self.registers)
        self._instructions = InstructionSet(
                self._config['instructions'],
                self._config.get('macros', None),
                self._operand_sets, self.endian, self.registers
            )

    def _validate_config(self, is_verbose: int) -> None:
        '''Performs some validation checks on configuration dictionary'''
        # check to see if old-style "memory block" is defined
        if 'predefined' in self._config and 'memory' in self._config['predefined']:
            sys.exit(
                'ERROR - ISA configuration file defines a predefined "memory" block. '
                'Memory blocks have been deprecated and replaced with "data" blocks.'
            )

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
    def endian(self) -> str:
        if 'endian' in self._config['general']:
            return self._config['general']['endian']
        else:
            return 'big'

    @property
    def address_size(self) -> int:
        '''The number of bits used to rerpesent a memory address'''
        return self._config['general']['address_size']

    @property
    def registers(self) -> set[str]:
        return self._registers

    @property
    def operation_mnemonics(self) -> list[str]:
        '''returns list of all mnemonics, instructions and macros'''
        return list(self._instructions.keys())

    @property
    def instruction_mnemonics(self) -> set[str]:
        '''returns a set of only native instruction mnemonics'''
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

    @property
    def default_origin(self) -> int:
        return self._config['general'].get('origin', 0)

    @property
    def predefined_constants(self) -> list[dict[str, int]]:
        if 'predefined' in self._config and 'constants' in self._config['predefined']:
            return self._config['predefined']['constants']
        else:
            return []

    @property
    def predefined_data_blocks(self) -> list[dict]:
        if 'predefined' in self._config and 'data' in self._config['predefined']:
            return self._config['predefined']['data']
        else:
            return []

    @property
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

    @property
    def predefined_memory_zones(self) -> list[dict]:
        if 'predefined' in self._config and 'memory_zones' in self._config['predefined']:
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
                self._global_label_scope.set_label_value(label, value, predefines_lineid)
        return self._global_label_scope
