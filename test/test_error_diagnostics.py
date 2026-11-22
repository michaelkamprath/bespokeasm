"""Regression tests for user-facing diagnostics.

Each case here previously produced a Python traceback, a silently accepted mistake, or a
message that did not tell the user what was wrong. The tests pin the current behavior so the
diagnostics stay useful.
"""
from __future__ import annotations

import contextlib
import copy
import io
import pathlib
import re

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
        'mov': {
            'bytecode': {'value': 2, 'size': 6},
            'operands': {
                'count': 2,
                'operand_sets': {'list': ['reg', 'reg'], 'disallowed_pairs': [['ra', 'ra']]},
            },
        },
    },
    'macros': {
        'ld2': [
            {
                'operands': {'count': 1, 'operand_sets': {'list': ['imm']}},
                'instructions': ['ld a, @ARG(0)', 'ld b, @ARG(0)'],
            },
        ],
    },
}


def write_config(tmp_path: pathlib.Path, mutate=None, name: str = 'isa.yaml') -> str:
    config = copy.deepcopy(MINIMAL_CONFIG)
    if mutate is not None:
        mutate(config)
    path = tmp_path / name
    YAML().dump(config, path)
    return str(path)


def assemble(
    tmp_path: pathlib.Path,
    source: str,
    config_path: str | None = None,
    *,
    warnings_as_errors: bool = False,
) -> Assembler:
    if config_path is None:
        config_path = write_config(tmp_path)
    source_path = tmp_path / 'prog.diag'
    source_path.write_text(source)
    assembler = Assembler(
        str(source_path), config_path,
        'binary', str(tmp_path / 'out.bin'),
        0, None, 0,
        False, 'listing', None, 0,
        [], [], warnings_as_errors,
    )
    assembler.assemble_bytecode()
    return assembler


def assemble_capturing_warnings(tmp_path: pathlib.Path, source: str, config_path: str | None = None) -> str:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        assemble(tmp_path, source, config_path)
    return stderr.getvalue()


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


class TestOperandMismatchExplanations:
    @pytest.mark.parametrize(
        'source, pattern',
        [
            ('  ld a, 1, 2\n', r'instruction "ld" takes 2 operands, but 3 were given \("a", "1", "2"\)'),
            ('  ld a\n', r'instruction "ld" takes 2 operands, but 1 was given \("a"\)'),
            ('  nop a\n', r'instruction "nop" takes no operands, but 1 was given \("a"\)'),
            ('  ld x, 1\n', r'operand 1 "x" of instruction "ld" is not valid; expected a register \(a, b\)'),
            ('  mov a, 5\n', r'operand 2 "5" of instruction "mov" is not valid; expected a register \(a, b\)'),
            ('foo:\n  ld foo, 1\n', r'operand 1 "foo" of instruction "ld" is not valid; expected a register'),
            ('  ld a, b + 1\n', r'operand 2 "b \+ 1" of instruction "ld" uses register "b" in a numeric expression'),
            ('  ld a, (1 + 2\n', r'operand 2 "\(1 \+ 2" of instruction "ld": expression ends unexpectedly'),
            ('  ld a, 1 +\n', r'operand 2 "1 \+" of instruction "ld": expression ends unexpectedly'),
            ('  ld a, 0x1G\n', r'operand 2 "0x1G" of instruction "ld": unexpected "G"'),
            ("  ld a, 'ab'\n", r'operand 2 "\'ab\'" of instruction "ld": only single-character ordinals'),
            ('  ld a, "x"\n', r'operand 2 "x" of instruction "ld": double-quoted strings are not valid'),
            ('  ld a,\n', r'operand 2 of instruction "ld" is empty'),
            ('  mov a, a\n', r'the operand combination "a", "a" is not allowed for instruction "mov"'),
            ('  ld2 1, 2\n', r'macro "ld2" takes 1 operand, but 2 were given'),
            ('  ld2 b\n', r'operand 1 "b" of macro "ld2" uses register "b" in a numeric expression'),
        ],
    )
    def test_mismatch_names_the_offending_operand(self, tmp_path, source, pattern):
        assert_error(tmp_path, source, pattern)

    def test_valid_operands_still_assemble(self, tmp_path):
        assembler = assemble(tmp_path, '  ld a, 5\n  mov a, b\n  ld2 7\n  jmp 0\n')
        assert assembler is not None


class TestUnparsableLineMessages:
    @pytest.mark.parametrize(
        'source, pattern',
        [
            (
                'start\n  nop\n',
                r'unknown instruction "start"; if this is meant to be a label, write it with a colon as "start:"',
            ),
            ('  ldd a, 1\n', r'unknown instruction "ldd" in "ldd a, 1"; did you mean "ld"\?'),
            ('  .bytes 1, 2\n', r'unknown directive "\.bytes"; did you mean "\.byte"'),
            ('  .frobnicate\n', r'unknown directive "\.frobnicate"$'),
            ('  .org\n', r'\.org directive requires an address'),
            ('  .fill 10\n', r'\.fill directive requires a count and a fill value'),
            ('  .byte\n', r'\.byte directive requires at least one value'),
            ('X EQU\n  nop\n', r'constant "X" is missing a value after "="'),
            ('X =\n  nop\n', r'constant "X" is missing a value after "="'),
            ('#frobnicate\n  nop\n', r'unknown preprocessor directive "#frobnicate"'),
            ('#defin X 1\n  nop\n', r'unknown preprocessor directive "#defin"; did you mean "#define"\?'),
            ('my label:\n  nop\n', r'label "my label" is not valid; label names cannot contain spaces'),
        ],
    )
    def test_unparsable_text_is_classified(self, tmp_path, source, pattern):
        assert_error(tmp_path, source, pattern)


class TestLabelMessages:
    def test_unknown_global_label(self, tmp_path):
        assert_error(tmp_path, '  jmp nowhere\n', r'line 1 - unknown label "nowhere"; it is not defined')

    def test_unknown_local_label_explains_scope(self, tmp_path):
        assert_error(
            tmp_path,
            'one:\n.l:\n  nop\ntwo:\n  jmp .l\n',
            r'line 5 - unknown label "\.l"; local labels \(starting with "\."\) are only visible',
        )

    def test_unknown_file_label_explains_scope(self, tmp_path):
        assert_error(tmp_path, '  jmp _hidden\n', r'unknown label "_hidden"; file-scoped labels')

    def test_duplicate_label_names_first_definition(self, tmp_path):
        assert_error(
            tmp_path,
            'foo:\n  nop\nfoo:\n  nop\n',
            r'line 3 - label "foo" is defined multiple times; first defined at file .*prog\.diag, line 1',
        )

    def test_local_label_before_global_label(self, tmp_path):
        assert_error(tmp_path, '.loop:\n  nop\n', r'local label "\.loop" must come after a global label')

    def test_keyword_as_label(self, tmp_path):
        assert_error(
            tmp_path,
            'byte = 5\n  nop\n',
            r'"byte" cannot be used as a label or constant name because "byte" is an assembler keyword',
        )

    def test_bytecode_past_end_of_zone(self, tmp_path):
        assert_error(
            tmp_path,
            '  .org 0xFFFF\n  jmp 0\n',
            r'line 2 - bytecode at this line extends to address 65537 \(0x10001\), past the end of memory zone "GLOBAL"',
        )


class TestConfigurationFileType:
    def test_yml_extension_is_accepted(self, tmp_path):
        config_path = write_config(tmp_path, name='isa.yml')
        assert assemble(tmp_path, '  nop\n', config_path) is not None

    def test_other_extension_is_rejected_by_name(self, tmp_path):
        config_path = write_config(tmp_path, name='isa.txt')
        pattern = r'ISA configuration file "isa.txt" must have a \.yaml, \.yml, or \.json extension'
        with pytest.raises(SystemExit, match=pattern):
            assemble(tmp_path, '  nop\n', config_path)


class TestLikelyMistakesAreWarnings:
    @pytest.mark.parametrize(
        'source, pattern',
        [
            ('#if 1\n  nop\n', r'WARNING: .*line 1 - #if has no matching #endif before the end of prog\.diag'),
            ('#ifdef FOO\n  nop\n', r'WARNING: .*line 1 - #ifdef has no matching #endif'),
            (
                '#if FOO == 1\n  nop\n#endif\n',
                r'preprocessor symbol "FOO" is not defined; #if compares it as the literal text "FOO"',
            ),
            ('#if FOO\n  nop\n#endif\n', r'preprocessor symbol "FOO" is not defined'),
            ('#define 123 abc\n  nop\n', r'preprocessor symbol name "123" is not a valid symbol name'),
            ('nop:\n  nop\n', r'label "nop" has the same name as an instruction mnemonic'),
            ('ld = 3\n  nop\n', r'constant "ld" has the same name as an instruction mnemonic'),
            ('  .byte 1, 2,\n', r'trailing comma in \.byte directive is ignored'),
            ('  .byte 1,,2\n', r'empty value between commas in \.byte directive is ignored'),
        ],
    )
    def test_warning_is_emitted(self, tmp_path, source, pattern):
        output = assemble_capturing_warnings(tmp_path, source)
        assert re.search(pattern, output), output

    @pytest.mark.parametrize(
        'source',
        [
            '#define FOO bar\n#if FOO == "bar"\n  nop\n#endif\n',
            '#define FOO 1\n#if FOO == 1\n  nop\n#endif\n',
            '#if 1\n  nop\n#endif\n',
            '  .byte 1, 2, 3\n',
            'start:\n  nop\n',
        ],
    )
    def test_no_warning_for_correct_source(self, tmp_path, source):
        assert 'WARNING' not in assemble_capturing_warnings(tmp_path, source)

    def test_undefined_symbol_warning_is_emitted_once(self, tmp_path):
        output = assemble_capturing_warnings(tmp_path, '#if FOO\n  nop\n  nop\n  nop\n#endif\n')
        assert output.count('preprocessor symbol "FOO" is not defined') == 1

    def test_warnings_as_errors_elevates_warning(self, tmp_path):
        with pytest.raises(SystemExit, match='ERROR: .*#if has no matching #endif'):
            assemble(tmp_path, '#if 1\n  nop\n', warnings_as_errors=True)


class TestConfigurationAdvisories:
    @pytest.mark.parametrize(
        'mutate, pattern',
        [
            (
                lambda c: c.update(instruction={}),
                r'<root>\.instruction is not a recognized setting and is ignored \(did you mean "instructions"\?\)',
            ),
            (
                lambda c: c['general'].update(multi_word_endianess='little'),
                r'general\.multi_word_endianess is not a recognized setting.*multi_word_endian',
            ),
            (
                lambda c: c['instructions']['nop'].update(bytecodes={}),
                r'instructions\.nop\.bytecodes is not a recognized setting.*bytecode',
            ),
            (
                lambda c: c['instructions']['jmp']['operands'].update(operand_set={}),
                r'instructions\.jmp\.operands\.operand_set is not a recognized setting',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].update(arguments={}),
                r'operand_sets\.imm\.operand_values\.u8\.arguments is not a recognized setting.*argument',
            ),
            (
                lambda c: c.update(predefined={'constants': [{'name': '9FOO', 'value': 1}]}),
                r'predefined\.constants\[9FOO\] name "9FOO" is not a valid symbol name',
            ),
            (
                lambda c: c.update(predefined={'constants': [{'name': 'a', 'value': 1}]}),
                r'predefined\.constants\[a\] name "a" is also a register name',
            ),
        ],
    )
    def test_advisory_is_a_warning(self, tmp_path, mutate, pattern):
        config_path = write_config(tmp_path, mutate)
        output = assemble_capturing_warnings(tmp_path, '  nop\n', config_path)
        assert re.search(f'WARNING: ISA configuration isa.yaml: {pattern}', output), output

    def test_clean_configuration_has_no_advisories(self, tmp_path):
        assert 'WARNING' not in assemble_capturing_warnings(tmp_path, '  nop\n')

    def test_advisory_becomes_error_with_warnings_as_errors(self, tmp_path):
        config_path = write_config(tmp_path, lambda c: c.update(instruction={}))
        with pytest.raises(SystemExit, match=r'ERROR: ISA configuration isa.yaml: <root>\.instruction'):
            assemble(tmp_path, '  nop\n', config_path, warnings_as_errors=True)
