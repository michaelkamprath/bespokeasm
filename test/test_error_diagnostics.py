"""Regression tests for user-facing diagnostics.

Each case here previously produced a Python traceback, a silently accepted mistake, or a
message that did not tell the user what was wrong. The tests pin the current behavior so the
diagnostics stay useful.
"""
from __future__ import annotations

import copy
import pathlib

import pytest
from bespokeasm.assembler.engine import Assembler
from ruamel.yaml import YAML


MINIMAL_CONFIG = {
    'description': 'diagnostics test ISA',
    'general': {
        'address_size': 16,
        'min_version': '0.8.0',
        'registers': ['a', 'b'],
        'identifier': {'name': 'diag', 'version': '1.0.0', 'extension': 'diag'},
    },
    'operand_sets': {
        'imm': {
            'operand_values': {
                'u8': {'type': 'numeric', 'argument': {'size': 8, 'word_align': True}},
            },
        },
        'reg': {
            'operand_values': {
                'ra': {'type': 'register', 'register': 'a', 'bytecode': {'value': 0, 'size': 1}},
                'rb': {'type': 'register', 'register': 'b', 'bytecode': {'value': 1, 'size': 1}},
            },
        },
    },
    'instructions': {
        'nop': {'bytecode': {'value': 0, 'size': 8}},
        'ld': {
            'bytecode': {'value': 1, 'size': 7},
            'operands': {'count': 2, 'operand_sets': {'list': ['reg', 'imm']}},
        },
        'jmp': {
            'bytecode': {'value': 3, 'size': 8},
            'operands': {'count': 1, 'operand_sets': {'list': ['imm']}},
        },
    },
}


def write_config(tmp_path: pathlib.Path, mutate=None, name: str = 'isa.yaml') -> str:
    config = copy.deepcopy(MINIMAL_CONFIG)
    if mutate is not None:
        mutate(config)
    path = tmp_path / name
    YAML().dump(config, path)
    return str(path)


def assemble(tmp_path: pathlib.Path, source: str, config_path: str | None = None) -> Assembler:
    if config_path is None:
        config_path = write_config(tmp_path)
    source_path = tmp_path / 'prog.diag'
    source_path.write_text(source)
    assembler = Assembler(
        str(source_path), config_path,
        'binary', str(tmp_path / 'out.bin'),
        0, None, 0,
        False, 'listing', None, 0,
        [], [], False,
    )
    assembler.assemble_bytecode()
    return assembler


def assert_error(tmp_path: pathlib.Path, source: str, pattern: str, config_path: str | None = None) -> None:
    with pytest.raises(SystemExit, match=pattern):
        assemble(tmp_path, source, config_path)


class TestSourceExceptionsBecomeDiagnostics:
    def test_division_by_zero_is_reported(self, tmp_path):
        assert_error(tmp_path, '  ld a, 1/0\n', 'line 1 - division by zero in expression')

    def test_zero_alignment_is_reported(self, tmp_path):
        assert_error(tmp_path, '  .align 0\n  nop\n', r'line 1 - \.align value must be a positive integer')

    def test_instruction_after_org_expression_is_reported(self, tmp_path):
        assert_error(tmp_path, '.org 0x100 ld a, 1\n', 'line 1 - unexpected "ld" after the end of the expression')

    def test_unbalanced_parenthesis_in_constant_is_reported(self, tmp_path):
        assert_error(tmp_path, 'X = (1 + 2\n  nop\n', r'line 1 - expression ends unexpectedly; expected a closing parenthesis')

    def test_dangling_operator_is_reported(self, tmp_path):
        assert_error(tmp_path, '  .byte 1 +\n', 'line 1 - expression ends unexpectedly; expected a number, label')

    def test_second_else_is_reported(self, tmp_path):
        assert_error(tmp_path, '#if 1\n#else\n#else\n#endif\n', 'line 3 - #else must follow an #if')

    def test_elif_after_else_is_reported(self, tmp_path):
        assert_error(tmp_path, '#if 1\n#else\n#elif 1\n#endif\n', 'line 3 - #elif must follow an #if')

    def test_endif_without_if_is_reported(self, tmp_path):
        assert_error(tmp_path, '  nop\n#endif\n', 'line 2 - #endif has no matching #if')


class TestConfigurationSchemaErrors:
    @pytest.mark.parametrize(
        'mutate, pattern',
        [
            (lambda c: c['general'].pop('address_size'), 'general.address_size is required and must be an integer'),
            (
                lambda c: c['general'].update(address_size='sixteen'),
                'general.address_size must be an integer, not the string "sixteen"',
            ),
            (lambda c: c['general'].update(word_size='8 bits'), 'general.word_size must be an integer'),
            (lambda c: c['general'].update(origin='zero'), 'general.origin must be an integer'),
            (lambda c: c['general'].update(min_version=0.8), 'general.min_version must be a quoted version string'),
            (lambda c: c['general'].update(multi_word_endian='middle'), 'general.multi_word_endian must be "big" or "little"'),
            (lambda c: c['general'].update(registers='a b'), 'general.registers must be a list of register names'),
            (lambda c: c['instructions']['nop'].pop('bytecode'), 'instructions.nop must define a "bytecode" entry'),
            (lambda c: c['instructions']['nop']['bytecode'].pop('size'), 'instructions.nop.bytecode.size is required'),
            (
                lambda c: c['instructions']['nop']['bytecode'].update(value=999),
                'instructions.nop.bytecode.value 999 does not fit in the configured size of 8 bits',
            ),
            (lambda c: c['instructions']['jmp']['operands'].pop('count'), 'instructions.jmp.operands.count is required'),
            (
                lambda c: c['instructions']['jmp']['operands'].update(operand_sets=['imm']),
                'instructions.jmp.operands.operand_sets must be a mapping, not a list',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].pop('type'),
                'operand_sets.imm.operand_values.u8.type is required',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].pop('argument'),
                'operand_sets.imm.operand_values.u8.argument is required',
            ),
            (lambda c: c['operand_sets'].update(imm={'values': {}}), 'operand_sets.imm.operand_values is required'),
            (
                lambda c: c.update(predefined={'constants': [{'name': 'FOO'}]}),
                r'predefined.constants\[FOO\].value is required',
            ),
            (
                lambda c: c.update(predefined={'memory_zones': [{'name': 'hi', 'start': 0x200, 'end': 0x100}]}),
                r'predefined.memory_zones\[hi\] start address 512 is greater than end address 256',
            ),
            (
                lambda c: c.update(predefined={'memory_zones': [{'name': 'hi', 'start': 0x200}]}),
                r'predefined.memory_zones\[hi\].end is required',
            ),
            (
                lambda c: c.update(predefined={'memory_zones': [{'name': 'hi', 'start': 0, 'end': 0x20000}]}),
                r'predefined.memory_zones\[hi\] end address 131072 is outside the 16-bit address space',
            ),
        ],
    )
    def test_malformed_configuration_names_the_offending_path(self, tmp_path, mutate, pattern):
        config_path = write_config(tmp_path, mutate)
        with pytest.raises(SystemExit, match=f'ERROR: ISA configuration isa.yaml: {pattern}'):
            assemble(tmp_path, '  nop\n', config_path)

    def test_configuration_errors_are_not_attributed_to_a_source_line(self, tmp_path):
        config_path = write_config(tmp_path, lambda c: c['instructions']['nop']['bytecode'].pop('size'))
        with pytest.raises(SystemExit) as exit_info:
            assemble(tmp_path, '  nop\n', config_path)
        assert 'prog.diag' not in str(exit_info.value)

    def test_malformed_json_is_reported(self, tmp_path):
        config_path = tmp_path / 'isa.json'
        config_path.write_text('{"general": ')
        with pytest.raises(SystemExit, match='could not parse JSON configuration file isa.json'):
            assemble(tmp_path, '  nop\n', str(config_path))

    def test_malformed_yaml_is_reported(self, tmp_path):
        config_path = tmp_path / 'isa.yaml'
        config_path.write_text('general: [oops\n')
        with pytest.raises(SystemExit, match='could not parse YAML configuration file isa.yaml'):
            assemble(tmp_path, '  nop\n', str(config_path))
