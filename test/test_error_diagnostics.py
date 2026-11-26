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
from types import SimpleNamespace

import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand_diagnostics import explain_operand_mismatch
from bespokeasm.assembler.model.operand_parser import OperandParser
from bespokeasm.assembler.model.operand_set import OperandSetCollection
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
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].update(prefix='!'),
                'operand_sets.imm.operand_values.u8.prefix must be "#", the only supported prefix, not the string "!"',
            ),
            (
                lambda c: c['operand_sets']['reg']['operand_values']['ra'].update(prefix='#'),
                'operand_sets.reg.operand_values.ra.prefix is only available on numeric operands, not register operands',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].update(enclosure='parentheses'),
                'operand_sets.imm.operand_values.u8.enclosure is only available on indirect_numeric, deferred_numeric, '
                'indirect_indexed_numeric, indirect_register, indirect_indexed_register, relative_address operands, '
                'not numeric operands',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(
                    ind={'type': 'indirect_numeric', 'enclosure': 'parens', 'argument': {'size': 8, 'word_align': True}},
                ),
                'operand_sets.imm.operand_values.ind.enclosure must be "brackets" or "parentheses" or "braces", '
                'not the string "parens"',
            ),
            (
                # Legacy `use_curly_braces` contradicting `enclosure`.
                lambda c: c['operand_sets']['imm']['operand_values'].update(rel={
                    'type': 'relative_address', 'use_curly_braces': True, 'enclosure': 'parentheses',
                    'argument': {'size': 8, 'word_align': True},
                }),
                'operand_sets.imm.operand_values.rel.enclosure must be "braces" or left out, since use_curly_braces is '
                'true, not "parentheses"',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(
                    ind={'type': 'indirect_indexed_numeric', 'argument': {'size': 8, 'word_align': True}},
                ),
                'operand_sets.imm.operand_values.ind.index_operands is required',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(ind={
                    'type': 'indirect_indexed_numeric', 'argument': {'size': 8, 'word_align': True},
                    'index_separator': 'colon', 'index_operands': {'a': {'type': 'register', 'register': 'a'}},
                }),
                'operand_sets.imm.operand_values.ind.index_separator must be "comma" or "plus", not the string "colon"',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(
                    ind={'type': 'indirect_numeric', 'index_separator': 'plus', 'argument': {'size': 8, 'word_align': True}},
                ),
                'operand_sets.imm.operand_values.ind.index_separator is only available on indirect_indexed_numeric '
                'operands, not indirect_numeric operands',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(ind={
                    'type': 'indirect_indexed_numeric', 'index_operands': {'a': {'type': 'register', 'register': 'a'}},
                }),
                'operand_sets.imm.operand_values.ind.argument is required',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].update(select_by_value=True),
                'operand_sets.imm.operand_values.u8.select_by_value is only available on address operands, '
                'not numeric operands',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(zp={
                    'type': 'address', 'select_by_value': True, 'argument': {'size': 8, 'word_align': True},
                }),
                'operand_sets.imm.operand_values.zp.select_by_value needs argument.memory_zone, the zone whose values '
                'select this operand',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(zp={
                    'type': 'address', 'select_by_value': 'yes',
                    'argument': {'size': 8, 'word_align': True, 'memory_zone': 'GLOBAL'},
                }),
                'operand_sets.imm.operand_values.zp.select_by_value must be true or false, not the string "yes"',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values'].update(rel={
                    'type': 'relative_address', 'offset_base': 'end', 'argument': {'size': 8, 'word_align': True},
                }),
                'operand_sets.imm.operand_values.rel.offset_base must be "instruction_start" or "last_word" or '
                '"next_instruction", not the string "end"',
            ),
            (
                lambda c: c['operand_sets']['imm']['operand_values']['u8'].update(offset_base='last_word'),
                'operand_sets.imm.operand_values.u8.offset_base is only available on relative_address operands, '
                'not numeric operands',
            ),
            (
                # Legacy `offset_from_instruction_end` alongside `offset_base`.
                lambda c: c['operand_sets']['imm']['operand_values'].update(rel={
                    'type': 'relative_address', 'offset_base': 'last_word', 'offset_from_instruction_end': True,
                    'argument': {'size': 8, 'word_align': True},
                }),
                'operand_sets.imm.operand_values.rel.offset_from_instruction_end must be left out when offset_base is '
                'set; offset_base replaces it',
            ),
            (lambda c: c['general'].update(directive_aliases=['word']), 'general.directive_aliases must be a mapping'),
            (
                lambda c: c['general'].update(directive_aliases={'org': 'fill'}),
                'general.directive_aliases.org is already the name of the .org directive',
            ),
            (
                lambda c: c['general'].update(directive_aliases={'byte': '2byte'}),
                'general.directive_aliases.byte is already the name of the .byte directive',
            ),
            (
                lambda c: c['general'].update(directive_aliases={'word': 'org'}),
                r'general.directive_aliases.word must name a data or fill directive \(byte, 2byte, .*zerountil\), '
                'not the string "org"',
            ),
            (
                lambda c: c['general'].update(directive_aliases={'inc': 'include'}),
                'general.directive_aliases.inc must name a data or fill directive',
            ),
            (
                lambda c: c['general'].update(directive_aliases={'.word': '2byte'}),
                r'general.directive_aliases..word is not a valid directive name; write it without the period',
            ),
            (
                lambda c: c['general'].update(directive_aliases={'word': '.2byte'}),
                r'general.directive_aliases.word must name a data or fill directive .*, '
                'not the string ".2byte"; write it without the period',
            ),
            (
                lambda c: c['general'].update(directive_aliases={'Word': '2byte', 'word': '2byte'}),
                r'general.directive_aliases.word is defined more than once \(directive names ignore case\)',
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
            # Brackets are taken off before the value is checked, though no form here is in brackets.
            ('  ld a, [5]\n', r'operand 2 "\[5\]" of instruction "ld" is not valid; expected a numeric value or expression$'),
            ('  ld a, [5+]\n', r'operand 2 "\[5\+\]" of instruction "ld": expression ends unexpectedly'),
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

    @pytest.mark.parametrize(
        'source, pattern',
        [
            ('  ld a, #\n', r'operand 2 "#" of instruction "ld": "#" must be followed by a value'),
            ('  ld a, 5\n', r'operand 2 "5" of instruction "ld" is not valid; expected a "#" immediate value'),
            ('  ld a, #(1+\n', r'operand 2 "#\(1\+" of instruction "ld": expression ends unexpectedly'),
        ],
    )
    def test_mismatch_with_an_immediate_prefix(self, tmp_path, source, pattern):
        config_path = write_config(tmp_path, lambda c: c['operand_sets']['imm']['operand_values']['u8'].update(prefix='#'))
        assert_error(tmp_path, source, pattern, config_path)

    @staticmethod
    def _with_parenthesized_forms(config):
        """`jmp` takes `5` or, written in parentheses with register `a`, `(5,a)`."""
        byte = {'size': 8, 'word_align': True}
        config['operand_sets']['jmp_ops'] = {'operand_values': {
            'abs': {'type': 'numeric', 'bytecode': {'value': 0, 'size': 1}, 'argument': byte},
            'iza': {
                'type': 'indirect_indexed_numeric', 'enclosure': 'parentheses',
                'index_operands': {'a': {'type': 'register', 'register': 'a'}},
                'bytecode': {'value': 1, 'size': 1}, 'argument': byte,
            },
        }}
        config['instructions']['jmp'].update(
            bytecode={'value': 3, 'size': 7}, operands={'count': 1, 'operand_sets': {'list': ['jmp_ops']}},
        )

    @pytest.mark.parametrize(
        'source, pattern',
        [
            (
                '  jmp (5)\n',
                r'operand 1 "\(5\)" of instruction "jmp" is not valid; parentheses around the whole operand select '
                r'another form here; expected \(address, a\)$',
            ),
            (
                '  jmp (5,b)\n',
                r'operand 1 "\(5,b\)" of instruction "jmp" is not valid; expected \(address, a\), or a numeric value '
                r'or expression$',
            ),
            ('  jmp (b)\n', r'operand 1 "\(b\)" of instruction "jmp" uses register "b" in a numeric expression'),
            ('  jmp ((1+\n', r'operand 1 "\(\(1\+" of instruction "jmp": expression ends unexpectedly'),
        ],
    )
    def test_mismatch_with_parenthesized_operands(self, tmp_path, source, pattern):
        assert_error(tmp_path, source, pattern, write_config(tmp_path, self._with_parenthesized_forms))

    def test_parentheses_are_grouping_where_no_operand_is_written_in_them(self, tmp_path):
        config_path = write_config(tmp_path, self._with_parenthesized_forms)
        assert assemble(tmp_path, '  jmp (5,a)\n  jmp (5+1)*2\n  ld a, (5)\n', config_path) is not None

    def test_a_deferred_enclosure_names_two_pairs(self):
        byte = {'size': 8, 'word_align': True}
        reporter = DiagnosticReporter()
        collection = OperandSetCollection({'ind': {'operand_values': {
            'ind': {'type': 'indirect_numeric', 'enclosure': 'parentheses', 'argument': byte},
        }}}, 'big', 'big', set(), 8, 8, reporter)
        parser = OperandParser('op', {'count': 1, 'operand_sets': {'list': ['ind']}}, collection, 'big', 'big', set(), 8, 8,
                               reporter)
        # As when another variant of the instruction has a `((vec))` form.
        parser.use_instruction_enclosed_forms({(1, 0): {('parentheses', 1), ('parentheses', 2)}})
        message = explain_operand_mismatch(
            'instruction', 'op', [SimpleNamespace(_operand_parser=parser)], LineIdentifier(1, 'deferred'),
            ['((5))'], set(), MemoryZoneManager(16, 0), 'decimal',
        )
        assert message == (
            'operand 1 "((5))" of instruction "op" is not valid; two pairs of parentheses around the whole operand '
            'select another form here'
        )

    def test_a_prefix_where_the_operand_takes_none(self, tmp_path):
        assert_error(
            tmp_path, '  jmp #5\n',
            r'operand 1 "#5" of instruction "jmp" is not valid; "#" marks an immediate value, which this operand '
            r'does not take; expected a numeric value or expression$',
        )


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
            ('  .fill\n', r'\.fill directive requires a count and an optional fill value'),
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

    @pytest.mark.parametrize(
        'source, pattern',
        [
            ('  .word\n', r'\.word directive requires at least one value, for example "\.word 0x1234"'),
            ('  .res\n', r'\.res directive requires a count and an optional fill value, for example "\.res 16"'),
            ('  .wrd 5\n', r'unknown directive "\.wrd"; did you mean "\.word"\?'),
            ('  .word "hi"\n', r'\.word data directive used with string value'),
        ],
    )
    def test_messages_name_a_directive_alias_as_written(self, tmp_path, source, pattern):
        config_path = write_config(tmp_path, lambda c: c['general'].update(directive_aliases={'word': '2byte', 'res': 'fill'}))
        assert_error(tmp_path, source, pattern, config_path)


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

    def test_prefix_and_directive_aliases_are_recognized_settings(self, tmp_path):
        def mutate(config):
            config['operand_sets']['imm']['operand_values']['u8']['prefix'] = '#'
            config['general']['directive_aliases'] = {'word': '2byte'}
        config_path = write_config(tmp_path, mutate)
        assert 'WARNING' not in assemble_capturing_warnings(tmp_path, '  jmp #0\n  .word 1\n', config_path)

    def test_enclosure_is_a_recognized_setting(self, tmp_path):
        config_path = write_config(tmp_path, TestOperandMismatchExplanations._with_parenthesized_forms)
        assert 'WARNING' not in assemble_capturing_warnings(tmp_path, '  jmp (0,a)\n', config_path)

    def test_advisory_becomes_error_with_warnings_as_errors(self, tmp_path):
        config_path = write_config(tmp_path, lambda c: c.update(instruction={}))
        with pytest.raises(SystemExit, match=r'ERROR: ISA configuration isa.yaml: <root>\.instruction'):
            assemble(tmp_path, '  nop\n', config_path, warnings_as_errors=True)


@pytest.mark.parametrize(('config', 'expected'), [
    ({'type': 'indirect_numeric'}, '[address]'),
    ({'type': 'indirect_numeric', 'enclosure': 'parentheses'}, '(address)'),
    ({'type': 'indirect_indexed_numeric', 'enclosure': 'parentheses',
      'index_operands': {'a': {'type': 'register', 'register': 'a'}}}, '(address, a)'),
    ({'type': 'indirect_indexed_numeric', 'index_operands': {
        'a': {'type': 'register', 'register': 'a'}, 'b': {'type': 'register', 'register': 'b'}}}, '[address, a or b]'),
    ({'type': 'indirect_indexed_numeric', 'index_operands': {
        'n': {'type': 'numeric_bytecode', 'bytecode': {'size': 2, 'min': 0, 'max': 3}}}}, '[address, index]'),
    ({'type': 'indirect_numeric', 'enclosure': 'braces'}, '{address}'),
    ({'type': 'relative_address'}, 'a relative address'),
    ({'type': 'relative_address', 'use_curly_braces': True}, '{relative address}'),
    ({'type': 'relative_address', 'enclosure': 'parentheses'}, '(relative address)'),
    ({'type': 'deferred_numeric'}, '[[address]]'),
    ({'type': 'deferred_numeric', 'enclosure': 'parentheses'}, '((address))'),
    ({'type': 'indirect_register', 'register': 'a'}, '[a]'),
    ({'type': 'indirect_register', 'register': 'a', 'enclosure': 'parentheses',
      'offset': {'size': 8, 'word_align': True}}, '(a) or (a + offset)'),
    ({'type': 'indirect_indexed_register', 'register': 'a', 'enclosure': 'parentheses',
      'index_operands': {'b': {'type': 'register', 'register': 'b'}}}, '(a + index)'),
])
def test_described_operands_show_their_enclosure(config, expected):
    from bespokeasm.assembler.model.operand.factory import OperandFactory
    from bespokeasm.assembler.model.operand_diagnostics import describe_operands
    config = {'argument': {'size': 8, 'word_align': True}, **config}
    operand = OperandFactory.factory('op', config, 'big', 'big', {'a', 'b'}, 8, 8, DiagnosticReporter())
    assert describe_operands([operand]) == expected
