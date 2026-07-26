import json
import os
import re
import sys
from functools import cached_property
from typing import Literal

import click
from bespokeasm import BESPOKEASM_MIN_REQUIRED_STR
from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.keywords import ASSEMBLER_KEYWORD_SET
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.instruction_set import InstructionSet
from bespokeasm.assembler.model.operand_set import OperandSet
from bespokeasm.assembler.model.operand_set import OperandSetCollection
from bespokeasm.utilities import is_unprefixed_numeric_string
from bespokeasm.utilities import normalize_default_numeric_base
from packaging import version
from ruamel.yaml import YAML


class AssemblerModel:
    _config: dict

    def __init__(
        self,
        config_file_path: str,
        is_verbose: int,
        diagnostic_reporter: DiagnosticReporter,
        static_analysis: bool = True,
    ):
        self._config_file = config_file_path
        self._static_analysis_enabled = static_analysis
        if diagnostic_reporter is None:
            raise ValueError('DiagnosticReporter is required for AssemblerModel')
        self._diagnostic_reporter = diagnostic_reporter
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
        register_names = self._configured_register_names()
        self._registers = set(register_names)
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
            self._diagnostic_reporter,
            default_numeric_base=self.default_numeric_base,
        )
        self._instructions = InstructionSet(
                self._config['instructions'],
                self._config.get('macros', None),
                self._operand_sets,
                self.multi_word_endianness,
                self.intra_word_endianness,
                self.default_numeric_base,
                self.registers,
                self.word_size,
                self.word_segment_size,
                self._diagnostic_reporter,
                retain_analysis_semantics=self.analysis_records_enabled,
            )

    _FLOW_TRANSFER_VALUES = {
        'none',
        'conditional',
        'unconditional',
        'call',
        'return',
        'indirect',
        'multiway',
    }
    _FLOW_DIRECT_TARGET_TRANSFERS = {'conditional', 'unconditional', 'call'}
    _FLOW_DIRECT_TARGET_OPERAND_TYPES = {'numeric', 'address', 'relative_address'}
    _FLOW_METADATA_KEYS = {
        'flow_effects',
        'flow_terminal',
        'flow_transfer',
        'flow_target_operand',
        'flow_call_effects',
    }

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
        try:
            general['default_numeric_base'] = normalize_default_numeric_base(
                general.get('default_numeric_base')
            )
        except ValueError:
            sys.exit(
                'ERROR - "default_numeric_base" must be one of: decimal, hex/hexadecimal/base16, '
                'octal/base8, binary/base2.'
            )
        self._validate_ambiguous_source_identifiers()
        if self._static_analysis_enabled:
            self._validate_flow_analysis_config()

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

    def _flow_config_error(self, message: str) -> None:
        self._diagnostic_reporter.error(None, message, category='flow')

    @staticmethod
    def _is_flow_delta_expression(value: str) -> bool:
        expression = re.sub(r'(?:ARG|COUNT)\(\d+\)', '1', value)
        return bool(re.fullmatch(r'[\d\s\+\-\*\/\%\(\)]+', expression))

    def _validate_flow_delta(self, value, context: str) -> None:
        if isinstance(value, bool):
            self._flow_config_error(f'{context} must be an integer or supported flow-delta expression')
        if isinstance(value, int):
            return
        if isinstance(value, str) and self._is_flow_delta_expression(value):
            return
        if isinstance(value, dict):
            if not value:
                self._flow_config_error(f'{context} edge map must not be empty')
            for edge_name, edge_value in value.items():
                self._validate_flow_delta(edge_value, f'{context}.{edge_name}')
            return
        self._flow_config_error(f'{context} must be an integer or supported flow-delta expression')

    def _validate_counter_class(self, counter_name: str, counter_config) -> None:
        context = f'flow_counters.{counter_name}'
        if not isinstance(counter_config, dict):
            self._flow_config_error(f'{context} must be a dictionary')
        if counter_config.get('operation', 'add') != 'add':
            self._flow_config_error(f'{context}.operation must be "add"')
        if counter_config.get('join', 'require-equal') not in {'require-equal', 'interval'}:
            self._flow_config_error(
                f'{context}.join must be "require-equal" or "interval"'
            )
        if counter_config.get('unknown_instructions', 'warn') not in {'ignore', 'warn', 'error'}:
            self._flow_config_error(
                f'{context}.unknown_instructions must be "ignore", "warn", or "error"'
            )
        if counter_config.get('exit_policy', 'balanced') not in {'balanced', 'none'}:
            self._flow_config_error(
                f'{context}.exit_policy must be "balanced" or "none"'
            )
        source = counter_config.get('source')
        if source is not None and (not isinstance(source, str) or not source.strip()):
            self._flow_config_error(f'{context}.source must be a non-empty dotted path')
        for option in ('min_value', 'max_value', 'default_init'):
            if option in counter_config and (
                isinstance(counter_config[option], bool)
                or not isinstance(counter_config[option], int)
            ):
                self._flow_config_error(f'{context}.{option} must be an integer')
        entry_modes = counter_config.get('entry_modes', {})
        if not isinstance(entry_modes, dict):
            self._flow_config_error(f'{context}.entry_modes must be a dictionary')
        for mode_name, mode_config in entry_modes.items():
            mode_context = f'{context}.entry_modes.{mode_name}'
            if not isinstance(mode_config, dict) or 'init' not in mode_config:
                self._flow_config_error(f'{mode_context} must be a dictionary containing integer init')
            for option in ('init', 'exit'):
                if option in mode_config and (
                    isinstance(mode_config[option], bool)
                    or not isinstance(mode_config[option], int)
                ):
                    self._flow_config_error(f'{mode_context}.{option} must be an integer')

    @staticmethod
    def _effective_instruction_configs(instruction_config: dict) -> list[dict]:
        root_config = {
            key: value
            for key, value in instruction_config.items()
            if key != 'variants'
        }
        if 'bytecode' in instruction_config:
            effective_configs = [root_config]
        else:
            effective_configs = []
        for variant_config in instruction_config.get('variants', []):
            effective_configs.append({**root_config, **variant_config})
        return effective_configs

    @staticmethod
    def _config_path_value(config: dict, path: str):
        value = config
        for component in path.split('.'):
            if not isinstance(value, dict) or component not in value:
                return None
            value = value[component]
        return value

    def _validate_flow_metadata_references(
        self,
        config: dict,
        context: str,
        counter_names: set[str],
    ) -> None:
        flow_effects = config.get('flow_effects')
        if flow_effects is not None:
            if not isinstance(flow_effects, dict):
                self._flow_config_error(f'{context}.flow_effects must be a dictionary')
            for counter_name, delta in flow_effects.items():
                if counter_name not in counter_names:
                    self._flow_config_error(
                        f'{context}.flow_effects names undeclared counter "{counter_name}"'
                    )
                self._validate_flow_delta(delta, f'{context}.flow_effects.{counter_name}')

        flow_terminal = config.get('flow_terminal')
        if flow_terminal is not None:
            if not isinstance(flow_terminal, list | tuple):
                self._flow_config_error(f'{context}.flow_terminal must be a list')
            for counter_name in flow_terminal:
                if counter_name not in counter_names:
                    self._flow_config_error(
                        f'{context}.flow_terminal names undeclared counter "{counter_name}"'
                    )

        call_effects = config.get('flow_call_effects')
        if call_effects is not None:
            if not isinstance(call_effects, dict):
                self._flow_config_error(f'{context}.flow_call_effects must be a dictionary')
            for counter_name, delta in call_effects.items():
                if counter_name not in counter_names:
                    self._flow_config_error(
                        f'{context}.flow_call_effects names undeclared counter "{counter_name}"'
                    )
                self._validate_flow_delta(delta, f'{context}.flow_call_effects.{counter_name}')

    def _validate_effective_transfer_config(self, config: dict, context: str) -> None:
        transfer = config.get('flow_transfer')
        target_operand = config.get('flow_target_operand')
        call_effects = config.get('flow_call_effects')

        if transfer is not None and transfer not in self._FLOW_TRANSFER_VALUES:
            self._flow_config_error(
                f'{context}.flow_transfer has invalid value "{transfer}"'
            )
        if transfer in self._FLOW_DIRECT_TARGET_TRANSFERS:
            if isinstance(target_operand, bool) or not isinstance(target_operand, int):
                self._flow_config_error(
                    f'{context}.flow_target_operand is required for flow_transfer "{transfer}"'
                )
            operand_count = config.get('operands', {}).get('count', 0)
            if target_operand < 0 or target_operand >= operand_count:
                self._flow_config_error(
                    f'{context}.flow_target_operand {target_operand} is outside '
                    f'the configured operand range 0..{operand_count - 1}'
                )
            target_types = self._configured_operand_types(
                config.get('operands', {}),
                target_operand,
            )
            if not target_types or not target_types.issubset(
                self._FLOW_DIRECT_TARGET_OPERAND_TYPES
            ):
                configured_types = ', '.join(sorted(target_types)) or 'unknown'
                self._flow_config_error(
                    f'{context}.flow_target_operand {target_operand} has incompatible '
                    f'operand type(s): {configured_types}'
                )
        elif target_operand is not None:
            self._flow_config_error(
                f'{context}.flow_target_operand is incompatible with '
                f'flow_transfer "{transfer or "unspecified"}"'
            )
        if call_effects is not None and transfer != 'call':
            self._flow_config_error(
                f'{context}.flow_call_effects is only valid with flow_transfer "call"'
            )

    def _configured_operand_types(
        self,
        operands_config: dict,
        target_operand: int,
    ) -> set[str]:
        configured_types = set()
        operand_sets = operands_config.get('operand_sets', {}).get('list', [])
        if target_operand < len(operand_sets):
            operand_set = self._config.get('operand_sets', {}).get(
                operand_sets[target_operand],
                {},
            )
            configured_types.update(
                operand.get('type', 'unknown')
                for operand in operand_set.get('operand_values', {}).values()
            )

        for specific_config in operands_config.get('specific_operands', {}).values():
            source_operands = [
                operand
                for operand in specific_config.get('list', {}).values()
                if operand.get('type') != 'empty'
            ]
            if target_operand < len(source_operands):
                configured_types.add(source_operands[target_operand].get('type', 'unknown'))
        return configured_types

    def _validate_flow_analysis_config(self) -> None:
        flow_counters = self._config.get('flow_counters', {})
        if not isinstance(flow_counters, dict):
            self._flow_config_error('flow_counters must be a dictionary')
        counter_names = set(flow_counters)
        for counter_name, counter_config in flow_counters.items():
            self._validate_counter_class(counter_name, counter_config)

        for mnemonic, instruction_config in self._config['instructions'].items():
            context = f'instructions.{mnemonic}'
            self._validate_flow_metadata_references(
                instruction_config,
                context,
                counter_names,
            )
            for variant_number, variant_config in enumerate(
                instruction_config.get('variants', []),
                start=1,
            ):
                self._validate_flow_metadata_references(
                    variant_config,
                    f'{context}.variants[{variant_number}]',
                    counter_names,
                )
            for variant_number, effective_config in enumerate(
                self._effective_instruction_configs(instruction_config)
            ):
                effective_context = f'{context}.effective_variant[{variant_number}]'
                self._validate_effective_transfer_config(effective_config, effective_context)
                for counter_name, counter_config in flow_counters.items():
                    source = counter_config.get('source', f'flow_effects.{counter_name}')
                    delta = self._config_path_value(effective_config, source)
                    if delta is not None:
                        self._validate_flow_delta(
                            delta,
                            f'{effective_context}.{source}',
                        )

        for mnemonic, macro_config in (self._config.get('macros') or {}).items():
            variants = macro_config if isinstance(macro_config, list) else macro_config.get('variants', [])
            metadata_locations = [macro_config] if isinstance(macro_config, dict) else []
            metadata_locations.extend(variants)
            for metadata in metadata_locations:
                if not isinstance(metadata, dict):
                    continue
                invalid_keys = self._FLOW_METADATA_KEYS.intersection(metadata)
                if invalid_keys:
                    invalid_key = sorted(invalid_keys)[0]
                    self._flow_config_error(
                        f'macros.{mnemonic} may not declare instruction flow metadata "{invalid_key}"'
                    )

    def _configured_register_names(self) -> list[str]:
        registers_config = self._config['general'].get('registers')
        if isinstance(registers_config, dict):
            return list(registers_config.keys())
        elif registers_config is None:
            return []
        else:
            return list(registers_config)

    def _validate_register_names(self, register_names: list[str]) -> None:
        if self.default_numeric_base == 'decimal':
            return
        for register_name in register_names:
            if is_unprefixed_numeric_string(register_name, self.default_numeric_base):
                sys.exit(
                    'ERROR: the instruction set configuration file specified register name '
                    f'"{register_name}" which is ambiguous with a bare {self.default_numeric_base} '
                    'numeric literal under general.default_numeric_base. Rename the register or '
                    'use a different default_numeric_base.'
                )

    def _validate_ambiguous_named_entities(
        self,
        names: list[str],
        entity_description: str,
    ) -> None:
        if self.default_numeric_base == 'decimal':
            return
        for name in names:
            if is_unprefixed_numeric_string(name, self.default_numeric_base):
                sys.exit(
                    'ERROR: the instruction set configuration file specified '
                    f'{entity_description} "{name}" which is ambiguous with a bare '
                    f'{self.default_numeric_base} numeric literal under '
                    'general.default_numeric_base. Rename it or use a different '
                    'default_numeric_base.'
                )

    def _validate_ambiguous_source_identifiers(self) -> None:
        self._validate_register_names(self._configured_register_names())
        self._validate_ambiguous_named_entities(
            [item['name'] for item in self.predefined_constants],
            'predefined constant name',
        )
        self._validate_ambiguous_named_entities(
            [item['name'] for item in self.predefined_data_blocks],
            'predefined data label',
        )
        self._validate_ambiguous_named_entities(
            [item['name'] for item in self.predefined_symbols],
            'predefined preprocessor symbol name',
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
    def diagnostic_reporter(self) -> DiagnosticReporter:
        return self._diagnostic_reporter

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
        self._diagnostic_reporter.warn(
            None,
            "The 'endian' general configuration option is deprecated and will be removed in a "
            "future version. Replace with 'multi_word_endian'.",
            category='deprecation',
        )
        if 'endian' in self._config['general']:
            return self._config['general']['endian']
        else:
            return 'big'

    @property
    def intra_word_endianness(self) -> Literal['little', 'big']:
        if 'intra_word_endian' in self._config['general']:
            return self._config['general']['intra_word_endian']
        if 'intra_word_endianness' in self._config['general']:
            self._diagnostic_reporter.warn(
                None,
                "The 'intra_word_endianness' general configuration option is deprecated and will be removed in a "
                "future version. Replace with 'intra_word_endian'.",
                category='deprecation',
            )
            return self._config['general']['intra_word_endianness']
        return 'big'

    @property
    def multi_word_endianness(self) -> Literal['little', 'big']:
        if 'multi_word_endian' in self._config['general']:
            return self._config['general']['multi_word_endian']
        if 'multi_word_endianness' in self._config['general']:
            self._diagnostic_reporter.warn(
                None,
                "The 'multi_word_endianness' general configuration option is deprecated and will be removed in a "
                "future version. Replace with 'multi_word_endian'.",
                category='deprecation',
            )
            return self._config['general']['multi_word_endianness']
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
    def default_numeric_base(self) -> Literal['decimal', 'hex', 'octal', 'binary']:
        return self._config['general'].get('default_numeric_base', 'decimal')

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

    @property
    def static_analysis_enabled(self) -> bool:
        return self._static_analysis_enabled

    @property
    def analysis_features(self) -> frozenset[str]:
        if not self._static_analysis_enabled:
            return frozenset()
        return frozenset({'flow_counters'}) if 'flow_counters' in self._config else frozenset()

    @property
    def analysis_records_enabled(self) -> bool:
        return bool(self.analysis_features)

    @property
    def flow_counters(self) -> dict:
        if not self._static_analysis_enabled:
            return {}
        return self._config.get('flow_counters', {})

    def get_operand_set(self, operand_set_name: str) -> OperandSet:
        return self._operand_sets.get_operand_set(operand_set_name)

    @cached_property
    def default_origin(self) -> int:
        return self._config['general'].get('origin', 0)

    @cached_property
    def predefined_constants(self) -> list[dict[str, int]]:
        if 'predefined' in self._config \
                and self._config['predefined'] is not None \
                and 'constants' in self._config['predefined']:
            return self._config['predefined']['constants']
        else:
            return []

    @cached_property
    def predefined_data_blocks(self) -> list[dict]:
        if 'predefined' in self._config \
                and self._config['predefined'] is not None \
                and 'data' in self._config['predefined']:
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
        if 'predefined' in self._config \
                and self._config['predefined'] is not None \
                and 'symbols' in self._config['predefined']:
            return self._config['predefined']['symbols']
        else:
            return []

    @property
    def allow_embedded_strings(self) -> bool:
        return self._config['general'].get('allow_embedded_strings', False)
