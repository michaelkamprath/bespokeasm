"""Structural validation of an instruction set configuration.

The assembler model historically read configuration values on demand, so a missing
or mistyped field surfaced as a Python ``KeyError`` or ``TypeError`` traceback, often
only when a source line first used the affected instruction. This module checks the
shape of the configuration up front and reports each problem as a user-facing error
that names the offending path within the configuration file.
"""
from __future__ import annotations

import os
from collections.abc import Callable

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

ENDIAN_VALUES = ('big', 'little')
ENDIAN_KEYS = (
    'multi_word_endian',
    'intra_word_endian',
    'multi_word_endianness',
    'intra_word_endianness',
    'endian',
)
OPERAND_TYPES_WITH_ARGUMENT = {
    'numeric',
    'address',
    'relative_address',
    'indirect_numeric',
    'deferred_numeric',
}
OPERAND_TYPES_WITH_REGISTER = {
    'register',
    'indirect_register',
    'indexed_register',
    'indirect_indexed_register',
}


class ConfigValidator:
    """Reports the first structural problem found in a configuration dictionary."""

    def __init__(self, config: dict, config_file_path: str, diagnostic_reporter: DiagnosticReporter) -> None:
        self._config = config
        self._config_name = os.path.basename(config_file_path)
        self._reporter = diagnostic_reporter

    def error(self, path: str, problem: str) -> None:
        self._reporter.error(None, f'ISA configuration {self._config_name}: {path} {problem}')

    # ---- primitive checks -------------------------------------------------

    def _is_int(self, value) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    def require_int(self, parent: dict, key: str, path: str, *, required: bool = False, minimum: int | None = None):
        if key not in parent:
            if required:
                self.error(f'{path}.{key}', 'is required and must be an integer')
            return None
        value = parent[key]
        if not self._is_int(value):
            self.error(f'{path}.{key}', f'must be an integer, not {self._describe(value)}')
        if minimum is not None and value < minimum:
            self.error(f'{path}.{key}', f'must be at least {minimum}, not {value}')
        return value

    def require_str(self, parent: dict, key: str, path: str, *, required: bool = False):
        if key not in parent:
            if required:
                self.error(f'{path}.{key}', 'is required and must be a string')
            return None
        value = parent[key]
        if not isinstance(value, str):
            self.error(f'{path}.{key}', f'must be a string, not {self._describe(value)}')
        return value

    def require_bool(self, parent: dict, key: str, path: str):
        if key in parent and not isinstance(parent[key], bool):
            self.error(f'{path}.{key}', f'must be true or false, not {self._describe(parent[key])}')

    def require_dict(self, parent: dict, key: str, path: str, *, required: bool = False, allow_none: bool = False):
        if key not in parent:
            if required:
                self.error(f'{path}.{key}', 'is required and must be a mapping')
            return None
        value = parent[key]
        if value is None and allow_none:
            return None
        if not isinstance(value, dict):
            self.error(f'{path}.{key}', f'must be a mapping, not {self._describe(value)}')
        return value

    def require_list(self, parent: dict, key: str, path: str, *, required: bool = False, allow_none: bool = False):
        if key not in parent:
            if required:
                self.error(f'{path}.{key}', 'is required and must be a list')
            return None
        value = parent[key]
        if value is None and allow_none:
            return None
        if not isinstance(value, list):
            self.error(f'{path}.{key}', f'must be a list, not {self._describe(value)}')
        return value

    def require_choice(self, parent: dict, key: str, path: str, choices: tuple):
        if key in parent and parent[key] not in choices:
            choice_text = ' or '.join(f'"{choice}"' for choice in choices)
            self.error(f'{path}.{key}', f'must be {choice_text}, not {self._describe(parent[key])}')

    @staticmethod
    def _describe(value) -> str:
        if value is None:
            return 'nothing (an empty value)'
        if isinstance(value, bool):
            return f'the boolean {str(value).lower()}'
        if isinstance(value, (int, float)):
            return f'the number {value}'
        if isinstance(value, str):
            return f'the string "{value}"'
        if isinstance(value, dict):
            return 'a mapping'
        if isinstance(value, list):
            return 'a list'
        return type(value).__name__

    # ---- sections -----------------------------------------------------------

    def validate(self) -> None:
        config = self._config
        general = self.require_dict(config, 'general', '<root>', required=True)
        self._validate_general(general)
        self._validate_operand_sets(self.require_dict(config, 'operand_sets', '<root>', allow_none=True))
        instructions = self.require_dict(config, 'instructions', '<root>', required=True)
        self._validate_instructions(instructions)
        macros = self.require_dict(config, 'macros', '<root>', allow_none=True)
        if macros is not None:
            self._validate_macros(macros)
        predefined = self.require_dict(config, 'predefined', '<root>', allow_none=True)
        if predefined is not None:
            self._validate_predefined(predefined, general)

    def _validate_general(self, general: dict) -> None:
        path = 'general'
        self.require_int(general, 'address_size', path, required=True, minimum=1)
        self.require_int(general, 'word_size', path, minimum=1)
        self.require_int(general, 'word_segment_size', path, minimum=1)
        self.require_int(general, 'origin', path, minimum=0)
        self.require_int(general, 'page_size', path, minimum=1)
        self.require_int(general, 'cstr_terminator', path)
        self.require_bool(general, 'allow_embedded_strings', path)
        self.require_bool(general, 'string_byte_packing', path)
        if 'min_version' in general and not isinstance(general['min_version'], str):
            self.error(
                f'{path}.min_version',
                f'must be a quoted version string such as "0.8.0", not {self._describe(general["min_version"])}',
            )
        for key in ENDIAN_KEYS:
            self.require_choice(general, key, path, ENDIAN_VALUES)
        registers = general.get('registers')
        if registers is not None and not isinstance(registers, (list, dict)):
            self.error(
                f'{path}.registers',
                f'must be a list of register names or a mapping of register names to their '
                f'documentation, not {self._describe(registers)}',
            )
        elif isinstance(registers, list):
            for index, name in enumerate(registers):
                if not isinstance(name, str):
                    self.error(f'{path}.registers[{index}]', f'must be a register name, not {self._describe(name)}')
        elif isinstance(registers, dict):
            for name, info in registers.items():
                if info is not None and not isinstance(info, dict):
                    self.error(
                        f'{path}.registers.{name}',
                        f'must be empty or a mapping of documentation fields, not {self._describe(info)}',
                    )
                elif isinstance(info, dict):
                    self.require_bool(info, 'reserved', f'{path}.registers.{name}')
        identifier = self.require_dict(general, 'identifier', path)
        if identifier is not None:
            self.require_str(identifier, 'name', f'{path}.identifier')
            self.require_str(identifier, 'extension', f'{path}.identifier')

    def _validate_operand_sets(self, operand_sets: dict | None) -> None:
        if operand_sets is None:
            return
        for name, operand_set in operand_sets.items():
            path = f'operand_sets.{name}'
            if not isinstance(operand_set, dict):
                self.error(path, f'must be a mapping, not {self._describe(operand_set)}')
            operand_values = self.require_dict(operand_set, 'operand_values', path, required=True)
            self._validate_operand_mapping(operand_values, f'{path}.operand_values')

    def _validate_operand_mapping(self, operands: dict, path: str) -> None:
        for operand_id, operand in operands.items():
            self._validate_operand(operand, f'{path}.{operand_id}')

    def _validate_operand(self, operand, path: str) -> None:
        if not isinstance(operand, dict):
            self.error(path, f'must be a mapping describing the operand, not {self._describe(operand)}')
        type_str = self.require_str(operand, 'type', path, required=True)
        bytecode = self.require_dict(operand, 'bytecode', path)
        if bytecode is not None:
            self.require_int(bytecode, 'size', f'{path}.bytecode', minimum=0)
            value = self.require_int(bytecode, 'value', f'{path}.bytecode')
            self._check_value_fits(value, bytecode.get('size'), f'{path}.bytecode')
        if type_str in OPERAND_TYPES_WITH_ARGUMENT:
            argument = self.require_dict(operand, 'argument', path, required=True)
            self.require_int(argument, 'size', f'{path}.argument', required=True, minimum=0)
            self.require_bool(argument, 'word_align', f'{path}.argument')
            for key in ENDIAN_KEYS:
                self.require_choice(argument, key, f'{path}.argument', ENDIAN_VALUES)
        elif 'argument' in operand:
            argument = self.require_dict(operand, 'argument', path)
            if argument is not None:
                self.require_int(argument, 'size', f'{path}.argument', minimum=0)
        if type_str in OPERAND_TYPES_WITH_REGISTER:
            self.require_str(operand, 'register', path, required=True)
        offset = self.require_dict(operand, 'offset', path)
        if offset is not None:
            self.require_int(offset, 'size', f'{path}.offset', minimum=0)
            self.require_bool(offset, 'word_align', f'{path}.offset')
        index_operands = self.require_dict(operand, 'index_operands', path)
        if index_operands is not None:
            self._validate_operand_mapping(index_operands, f'{path}.index_operands')

    def _check_value_fits(self, value, size, path: str) -> None:
        if not self._is_int(value) or not self._is_int(size) or size < 0:
            return
        if size == 0:
            fits = value == 0
        else:
            fits = -(1 << (size - 1)) <= value < (1 << size)
        if not fits:
            self.error(
                f'{path}.value',
                f'{value} does not fit in the configured size of {size} bit{"s" if size != 1 else ""}',
            )

    def _validate_operands_config(self, operands, path: str) -> None:
        if not isinstance(operands, dict):
            self.error(path, f'must be a mapping with a "count" entry, not {self._describe(operands)}')
        self.require_int(operands, 'count', path, required=True, minimum=0)
        operand_sets = self.require_dict(operands, 'operand_sets', path)
        if operand_sets is not None:
            set_list = self.require_list(operand_sets, 'list', f'{path}.operand_sets', required=True)
            for index, set_name in enumerate(set_list):
                if not isinstance(set_name, str):
                    self.error(
                        f'{path}.operand_sets.list[{index}]',
                        f'must be the name of an operand set, not {self._describe(set_name)}',
                    )
            self.require_bool(operand_sets, 'reverse_argument_order', f'{path}.operand_sets')
            self.require_bool(operand_sets, 'reverse_bytecode_order', f'{path}.operand_sets')
            self.require_list(operand_sets, 'disallowed_pairs', f'{path}.operand_sets')
        specific_operands = self.require_dict(operands, 'specific_operands', path)
        if specific_operands is not None:
            for name, specific in specific_operands.items():
                specific_path = f'{path}.specific_operands.{name}'
                if not isinstance(specific, dict):
                    self.error(specific_path, f'must be a mapping, not {self._describe(specific)}')
                operand_list = self.require_dict(specific, 'list', specific_path, required=True)
                self._validate_operand_mapping(operand_list, f'{specific_path}.list')

    def _validate_bytecode(self, variant: dict, path: str, *, required: bool) -> None:
        bytecode = self.require_dict(variant, 'bytecode', path, required=required)
        if bytecode is None:
            return
        size = self.require_int(bytecode, 'size', f'{path}.bytecode', required=True, minimum=0)
        value = self.require_int(bytecode, 'value', f'{path}.bytecode', required=True)
        self._check_value_fits(value, size, f'{path}.bytecode')
        suffix = self.require_dict(bytecode, 'suffix', f'{path}.bytecode')
        if suffix is not None:
            suffix_size = self.require_int(suffix, 'size', f'{path}.bytecode.suffix', required=True, minimum=0)
            suffix_value = self.require_int(suffix, 'value', f'{path}.bytecode.suffix', required=True)
            self._check_value_fits(suffix_value, suffix_size, f'{path}.bytecode.suffix')
        for key in ENDIAN_KEYS:
            self.require_choice(bytecode, key, f'{path}.bytecode', ENDIAN_VALUES)

    def _validate_variant_body(self, variant: dict, path: str) -> None:
        if 'operands' in variant:
            self._validate_operands_config(variant['operands'], f'{path}.operands')

    def _validate_instructions(self, instructions: dict) -> None:
        for mnemonic, instruction in instructions.items():
            path = f'instructions.{mnemonic}'
            if not isinstance(instruction, dict):
                self.error(path, f'must be a mapping, not {self._describe(instruction)}')
            has_variants = 'variants' in instruction
            if 'bytecode' not in instruction and not has_variants:
                self.error(path, 'must define a "bytecode" entry or a "variants" list')
            self._validate_bytecode(instruction, path, required=not has_variants)
            self._validate_variant_body(instruction, path)
            aliases = self.require_list(instruction, 'aliases', path)
            if aliases is not None:
                for index, alias in enumerate(aliases):
                    if not isinstance(alias, str):
                        self.error(f'{path}.aliases[{index}]', f'must be a mnemonic string, not {self._describe(alias)}')
            variants = self.require_list(instruction, 'variants', path)
            if variants is not None:
                for index, variant in enumerate(variants, start=1):
                    variant_path = f'{path}.variants[{index}]'
                    if not isinstance(variant, dict):
                        self.error(variant_path, f'must be a mapping, not {self._describe(variant)}')
                    self._validate_bytecode(variant, variant_path, required=True)
                    self._validate_variant_body(variant, variant_path)

    def _validate_macros(self, macros: dict) -> None:
        for mnemonic, macro in macros.items():
            path = f'macros.{mnemonic}'
            if isinstance(macro, list):
                variants = macro
            elif isinstance(macro, dict):
                variants = self.require_list(macro, 'variants', path, required=True)
            else:
                self.error(
                    path,
                    f'must be a list of variants or a mapping with a "variants" list, not {self._describe(macro)}',
                )
            for index, variant in enumerate(variants, start=1):
                variant_path = f'{path}.variants[{index}]' if isinstance(macro, dict) else f'{path}[{index}]'
                if not isinstance(variant, dict):
                    self.error(variant_path, f'must be a mapping, not {self._describe(variant)}')
                self._validate_variant_body(variant, variant_path)
                steps = self.require_list(variant, 'instructions', variant_path, required=True)
                for step_index, step in enumerate(steps):
                    if not isinstance(step, str):
                        self.error(
                            f'{variant_path}.instructions[{step_index}]',
                            f'must be an instruction string, not {self._describe(step)}',
                        )

    def _validate_predefined(self, predefined: dict, general: dict) -> None:
        self._validate_named_entries(
            predefined, 'constants', 'predefined.constants',
            lambda entry, path: self.require_int(entry, 'value', path, required=True),
        )

        def check_data(entry: dict, path: str) -> None:
            self.require_int(entry, 'address', path, required=True, minimum=0)
            self.require_int(entry, 'value', path, required=True)
            self.require_int(entry, 'size', path, required=True, minimum=1)
        self._validate_named_entries(predefined, 'data', 'predefined.data', check_data)

        address_size = general.get('address_size')
        address_limit = (1 << address_size) - 1 if self._is_int(address_size) and address_size > 0 else None

        def check_zone(entry: dict, path: str) -> None:
            start = self.require_int(entry, 'start', path, required=True, minimum=0)
            end = self.require_int(entry, 'end', path, required=True, minimum=0)
            if not self._is_int(start) or not self._is_int(end):
                return
            if start > end:
                self.error(path, f'start address {start} is greater than end address {end}')
            if address_limit is not None and end > address_limit:
                self.error(
                    path,
                    f'end address {end} is outside the {address_size}-bit address space '
                    f'(maximum address is {address_limit})',
                )
        self._validate_named_entries(predefined, 'memory_zones', 'predefined.memory_zones', check_zone)
        self._validate_named_entries(predefined, 'symbols', 'predefined.symbols', None)

    def _validate_named_entries(
        self,
        predefined: dict,
        key: str,
        path: str,
        check_entry: Callable[[dict, str], None] | None,
    ) -> None:
        entries = self.require_list(predefined, key, path.rsplit('.', 1)[0], allow_none=True)
        if entries is None:
            return
        for index, entry in enumerate(entries):
            entry_path = f'{path}[{index}]'
            if not isinstance(entry, dict):
                self.error(entry_path, f'must be a mapping with a "name" entry, not {self._describe(entry)}')
            name = self.require_str(entry, 'name', entry_path, required=True)
            if isinstance(name, str):
                entry_path = f'{path}[{name}]'
            if check_entry is not None:
                check_entry(entry, entry_path)
