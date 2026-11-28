"""Expression features from the MOS 6502 milestone 1: new literal forms, `~`, the unary-minus
fix, the per-ISA `<`/`>` byte operators, and `*` as the current address.

Bytes compared with Carsten Herting's assemblers were captured on Nov 25, 2026, from his
Minimal 64x4 Revision 1.1 assembler (asm.cpp) and his Minimal UART CPU assembler (asm.py);
the tests never run those assemblers.
"""
import contextlib
import importlib.resources as pkg_resources
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.expression import parse_expression
from bespokeasm.utilities import ExpressionSyntax
from bespokeasm.utilities import is_explicit_numeric_string
from bespokeasm.utilities import parse_numeric_string

from test import config_files
from test.isa_configs import load_config
from test.isa_configs import write_json_config

TIGHT = ExpressionSyntax(low_high_operators='tight', current_address='instruction_start')
WHOLE = ExpressionSyntax(low_high_operators='whole_expression', current_address='value_address')

MIN64X4_CONFIG = pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml')
MINCPU_CONFIG = pkg_resources.files(config_files).joinpath('minhex', 'slu4-minimal-cpu.yaml')
HEX_BASE_CONFIG = pkg_resources.files(config_files).joinpath('test_default_numeric_base.yaml')
SIXTEEN_BIT_CONFIG = pkg_resources.files(config_files).joinpath('test_16bit_data_words.yaml')


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _value(expression: str, syntax=TIGHT, current_address=None) -> int:
    return parse_expression(None, expression, syntax).get_value(None, None, None, current_address)


def _error(expression: str, syntax=TIGHT, current_address=None) -> str:
    with pytest.raises(SyntaxError) as info:
        _value(expression, syntax, current_address)
    return str(info.value)


def _config(path, **general) -> dict:
    config = load_config(path)
    config['general'].update(general)
    return config


def _assemble(tmp_path, config: dict, source: str, start: int = 0, extension: str = 'asm') -> bytes:
    """The binary of ``source``, starting at address ``start``."""
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    config_path = write_json_config(config, tmp_path)
    (tmp_path / f'main.{extension}').write_text(source)
    assembler = Assembler(
        str(tmp_path / f'main.{extension}'), str(config_path), True, str(tmp_path / 'out.bin'), start, None, 0,
        False, None, None, 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.bin').read_bytes()


def _assembly_error(tmp_path, config: dict, source: str) -> str:
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, config, source)
    return str(info.value)


# --- Literals -------------------------------------------------------------------------------

@pytest.mark.parametrize(('literal', 'value'), [
    ('0o17', 15), ('17Q', 15), ('17q', 15), ('17O', 15), ('17o', 15),
    ('1010B', 10), ('1010b', 10), ('0FFH', 255), ('%101', 5), ('b101', 5), ('$7C', 124),
])
def test_literal_forms(literal, value):
    assert is_explicit_numeric_string(literal)
    assert parse_numeric_string(literal) == value
    assert _value(literal, 'decimal') == value


def test_binary_suffix_is_a_hex_number_under_a_hex_default_base():
    assert not is_explicit_numeric_string('1010B', 'hex')
    assert parse_numeric_string('1010B', 'hex') == 0x1010B
    assert _value('1B', 'hex') == 0x1B
    assert _value('17Q', 'hex') == 15     # Q is not a hex digit, so octal stays octal


def test_binary_suffix_in_an_operand_follows_the_default_base(tmp_path):
    config = _config(HEX_BASE_CONFIG)
    assert _assemble(tmp_path, config, 'ldi 1B\n') == bytes([0x40, 0x1B])
    config['general']['default_numeric_base'] = 'decimal'
    assert _assemble(tmp_path, config, 'ldi 1B\n') == bytes([0x40, 0x01])


def test_address_operands_read_bare_numbers_in_the_default_base(tmp_path):
    """Address operands used to ignore `default_numeric_base` and read `1F` as an error."""
    config = _config(HEX_BASE_CONFIG)
    config['operand_sets']['target'] = {
        'operand_values': {'addr': {'type': 'address', 'argument': {'size': 16, 'word_align': True}}},
    }
    config['instructions']['jmp'] = {
        'bytecode': {'value': 0xC3, 'size': 8},
        'operands': {'count': 1, 'operand_sets': {'list': ['target']}},
    }
    assert _assemble(tmp_path, config, 'jmp 1F\n') == bytes([0xC3, 0x00, 0x1F])


# --- Unary operators ------------------------------------------------------------------------

@pytest.mark.parametrize(('expression', 'value'), [
    ('-1+2', 1),             # negation applies to one term; it used to give -3
    ('2*-3+1', -5),          # it used to give -8
    ('-(1+2)', -3),
    ('--1', 1),
    ('-2*3', -6),
    ('~0', -1),
    ('~$0F & $FF', 0xF0),
    ('~1+1', -1),            # ~ applies to one term
    ('1 << 4', 16),          # shifts are unchanged
    ('$80 >> 4', 8),
])
def test_unary_operators(expression, value):
    assert _value(expression, 'decimal') == value


def test_complement_is_masked_by_the_data_width(tmp_path):
    config = _config(MINCPU_CONFIG)
    assert _assemble(tmp_path, config, '.org 0\n.byte ~$0F\n.2byte ~1\n') == bytes([0xF0, 0xFE, 0xFF])


# --- `<` and `>` ----------------------------------------------------------------------------
# They split a value by the instruction set's word size: with 8-bit words they are the low and
# high byte.

@pytest.mark.parametrize(('expression', 'tight', 'whole'), [
    ('<$12FF+1', 0x100, 0x00),     # tight: (<$12FF)+1; whole: <($12FF+1)
    ('>$12FF+1', 0x13, 0x13),
    ('<$1234', 0x34, 0x34),
    ('>$1234', 0x12, 0x12),
    ('<-1', 0xFF, 0xFF),
    ('>$123456', 0x34, 0x34),      # with 8-bit words, the same as BYTE1()
])
def test_low_high_operator_precedence(expression, tight, whole):
    assert _value(expression, TIGHT) == tight
    assert _value(expression, WHOLE) == whole


@pytest.mark.parametrize(('word_size', 'expression', 'tight', 'whole'), [
    (16, '<$12345678', 0x5678, 0x5678),     # the low word, not the low byte
    (16, '>$12345678', 0x1234, 0x1234),     # the word above it
    (16, '<$1234FFFF+1', 0x10000, 0x0000),  # tight: (<x)+1; whole: <(x+1)
    (4, '<$A7', 0x7, 0x7),                  # 4-bit words
    (4, '>$A7', 0xA, 0xA),
])
def test_low_high_operators_split_by_the_word_size(word_size, expression, tight, whole):
    assert _value(expression, ExpressionSyntax(low_high_operators='tight', word_size=word_size)) == tight
    assert _value(expression, ExpressionSyntax(low_high_operators='whole_expression', word_size=word_size)) == whole


def test_low_high_operators_emit_words_on_a_16_bit_word_isa(tmp_path):
    config = _config(SIXTEEN_BIT_CONFIG, low_high_operators='tight')
    words_config = _config(SIXTEEN_BIT_CONFIG)
    expected = _assemble(tmp_path, words_config, '.org 0\n.2byte $5678, $1234\n')
    assert _assemble(tmp_path, config, '.org 0\nvalue = $12345678\n.2byte <value, >value\n') == expected


def test_tight_low_high_operators_go_before_any_term():
    assert _value('1+<$1234', TIGHT) == 0x35
    assert _value('<($12FF+1)', TIGHT) == 0
    assert _value('LSB($1234) + >$1234', TIGHT) == 0x46


@pytest.mark.parametrize('expression', ['1+<2', '(1+<2)', '2*~>2', 'LSB(1|>2)', '<1+>2'])
def test_whole_expression_low_high_operators_only_start_a_scope(expression):
    assert 'may only start an expression or a parenthesis' in _error(expression, WHOLE)


@pytest.mark.parametrize(('expression', 'tight', 'whole'), [
    ('~>$1234', ~0x12, ~0x12),                  # the complement of the high byte, in both modes
    ('~>$12FF+1', ~0x12 + 1, ~0x13),            # whole: ~(>($12FF+1))
    ('~>$1234^2<<1', ~0x12 ^ 4, ~0x12),         # whole: ~(>($1234^(2<<1)))
    ('-<$12FF+1', -0xFF + 1, 0),                # whole: -(<($12FF+1))
    ('(<$12FF+1)+1', 0x101, 1),                 # whole: the parenthesis ends the scope
    ('LSB(>$12FF+1)+1', 0x14, 0x14),            # tight: LSB((>$12FF)+1)+1; whole: LSB(>($12FF+1))+1
    ('<>$123456', 0x34, 0x34),
])
def test_whole_expression_low_high_operators_apply_to_the_rest_of_their_scope(expression, tight, whole):
    assert _value(expression, TIGHT) == tight
    assert _value(expression, WHOLE) == whole


@pytest.mark.parametrize(('operator', 'function'), [('<', 'BYTE0'), ('>', 'BYTE1')])
def test_low_high_operators_are_unavailable_unless_the_isa_turns_them_on(operator, function):
    assert f'use {function}(...)' in _error(f'{operator}$1234', 'decimal')


def test_a_low_high_operator_after_a_value_is_an_error():
    assert 'comparisons are only available in preprocessor conditions' in _error('1 < 2', TIGHT)


@pytest.mark.parametrize(('style', 'condition', 'taken'), [
    ('tight', '#if >ADDR == $12', True),
    ('tight', '#if <ADDR == $34', True),
    ('whole_expression', '#if >ADDR == $12', True),
    ('tight', '#if >ADDR > $13', False),
])
def test_low_high_operators_in_preprocessor_conditions(tmp_path, style, condition, taken):
    config = _config(MINCPU_CONFIG, low_high_operators=style)
    source = f'#define ADDR $1234\n.org 0\n{condition}\n.byte 1\n#else\n.byte 2\n#endif\n'
    assert _assemble(tmp_path, config, source) == bytes([1 if taken else 2])


# --- `*` ------------------------------------------------------------------------------------

def test_current_address_in_expressions():
    assert _value('*', TIGHT, 0x1234) == 0x1234
    assert _value('* * 2', TIGHT, 0x10) == 0x20      # the first * is the address, the second multiplies
    assert _value('*+2', TIGHT, 0x10) == 0x12
    assert _value('<*', TIGHT, 0x1234) == 0x34


def test_current_address_is_unavailable_unless_the_isa_turns_it_on():
    assert 'unexpected "*"' in _error('*', 'decimal')


def test_current_address_needs_an_address():
    with pytest.raises(Exception, match='only available in instruction operands and data values'):
        _value('*+1', TIGHT, None)


@pytest.mark.parametrize(('style', 'expected'), [
    # JPA at $12FF: `*` is the instruction ($12FF) or the operand's own bytes ($1300).
    ('instruction_start', [0x64, 0xFF, 0x12]),
    ('value_address', [0x64, 0x00, 0x13]),
])
def test_current_address_in_an_instruction_operand(tmp_path, style, expected):
    config = _config(MIN64X4_CONFIG, current_address=style)
    assert list(_assemble(tmp_path, config, '.org $12FF\nJPA *\n', start=0x12FF, extension='min64x4')) == expected


@pytest.mark.parametrize('style', ['instruction_start', 'value_address'])
def test_current_address_in_data_is_each_values_own_address(tmp_path, style):
    config = _config(MIN64X4_CONFIG, current_address=style, low_high_operators='whole_expression')
    found = _assemble(tmp_path, config, '.org $12FF\n.2byte *, *\n.byte <*, >*\n', start=0x12FF, extension='min64x4')
    assert list(found) == [0xFF, 0x12, 0x01, 0x13, 0x03, 0x13]


@pytest.mark.parametrize('source', ['HERE = *\n', '.org *\n', '#if * == 0\n#endif\n'])
def test_current_address_outside_operands_and_data_is_an_error(tmp_path, source):
    config = _config(MIN64X4_CONFIG, current_address='instruction_start')
    message = _assembly_error(tmp_path, config, source)
    assert '"*" (the current address) is only available in instruction operands and data values' in message


def test_flow_analysis_reads_the_current_address_of_an_operand(tmp_path):
    """`jpa *+2` lands on the next instruction only if `*` is the operand's address ($0201)."""
    config = _config(MIN64X4_CONFIG, current_address='value_address')
    source = (
        '.org $0200\n#track stack mode=jumped\nmain:\n    jpa *+2\nnext:\n    phsi 1\n    pls\n#endtrack stack\n'
    )
    assert _assemble(tmp_path, config, source, start=0x200, extension='min64x4')[:3] == bytes([0x64, 0x03, 0x02])
    config['general']['current_address'] = 'instruction_start'
    # With `*` as the instruction's start ($0200), `*+2` is the middle of the jpa instruction.
    assert 'target 0x202 is invalid' in _assembly_error(tmp_path, config, source)


def test_flow_entry_checks_read_the_current_address_of_an_operand(tmp_path):
    """`jpa *+4` at $0200 targets `inner` ($0205) inside the tracked region, an illegal entry."""
    config = _config(MIN64X4_CONFIG, current_address='value_address')
    source = (
        '.org $0200\nstart:\n    jpa *+4\n#track stack mode=jumped\nmain:\n    phsi 1\ninner:\n    pls\n'
        '#endtrack stack\n'
    )
    assert 'control flow enters flow counter region "stack" after #track stack' in _assembly_error(
        tmp_path, config, source,
    )


# --- Carsten Herting's assemblers -----------------------------------------------------------

@pytest.mark.parametrize(('source', 'expected'), [
    # BespokeASM source, and the bytes Carsten's Minimal 64x4 Rev 1.1 assembler wrote for the
    # same line in his syntax, with `here` at $12FF.
    ('LDI <here+2', [0x74, 0x01]),
    ('LDI >here+0x100', [0x74, 0x13]),
    ('JPA *', [0x64, 0x00, 0x13]),
    ('JPS here+2', [0x67, 0x01, 0x13]),
    ('LDI <*', [0x74, 0x00]),
    ('LDI >*', [0x74, 0x13]),
    ('.2byte *, *', [0xFF, 0x12, 0x01, 0x13]),               # his `* *`
    ('.byte <*, >*', [0xFF, 0x13]),                          # his `<* >*`
    ('.byte <here+2, >here+0x100', [0x01, 0x13]),            # his `<here+2 >here+0x100`
])
def test_minimal_64x4_matches_carstens_assembler(tmp_path, source, expected):
    config = _config(MIN64X4_CONFIG, low_high_operators='whole_expression', current_address='value_address')
    found = _assemble(tmp_path, config, f'.org $12FF\nhere: {source}\n', start=0x12FF, extension='min64x4')
    assert list(found) == expected


def test_minimal_cpu_matches_carstens_assembler(tmp_path):
    """Carsten's Minimal UART CPU assembler wrote 0e 01 0e 13 14 01 13 for this line."""
    config = _config(MINCPU_CONFIG, low_high_operators='whole_expression')
    found = _assemble(tmp_path, config, '.org $12FF\nhere: LDI <here+2 LDI >here+0x100 JPA here+2\n', start=0x12FF)
    assert list(found) == [0x0E, 0x01, 0x0E, 0x13, 0x14, 0x01, 0x13]


# --- Configuration --------------------------------------------------------------------------

@pytest.mark.parametrize(('key', 'value', 'expected'), [
    ('low_high_operators', 'loose', 'general.low_high_operators must be "tight" or "whole_expression"'),
    ('current_address', 'here', 'general.current_address must be "instruction_start" or "value_address"'),
])
def test_config_values_are_validated(tmp_path, key, value, expected):
    config = _config(MINCPU_CONFIG, **{key: value})
    assert expected in _assembly_error(tmp_path, config, 'NOP\n')


# --- Editor highlighting --------------------------------------------------------------------

def test_generated_grammars_color_the_new_literal_forms(tmp_path):
    import json
    import re
    import zipfile

    from bespokeasm.configgen.sublime import SublimeConfigGenerator
    from bespokeasm.configgen.vim import VimConfigGenerator
    from bespokeasm.configgen.vscode import VSCodeConfigGenerator

    def generate(cls, name):
        destination = tmp_path / name
        destination.mkdir()
        cls(str(MINCPU_CONFIG), 0, str(destination), 'test-lang', '1.0.0', 'testasm').generate()
        return destination

    grammar = json.loads(next(generate(VSCodeConfigGenerator, 'vscode').rglob('tmGrammar.json')).read_text())
    scopes = {pattern['name']: pattern['match'] for pattern in grammar['repository']['numeric-values']['patterns']}
    for literal, scope in [('0o17', 'octal'), ('17Q', 'octal'), ('17o', 'octal'), ('1010B', 'binary')]:
        assert re.fullmatch(scopes[f'constant.numeric.integer.{scope}'], literal), literal

    with zipfile.ZipFile(next(generate(SublimeConfigGenerator, 'sublime').glob('*.sublime-package'))) as package:
        syntax = package.read(next(n for n in package.namelist() if n.endswith('.sublime-syntax'))).decode()
    assert 'constant.numeric.integer.octal' in syntax and '[01]+[bB]' in syntax

    vim_files = '\n'.join(path.read_text() for path in generate(VimConfigGenerator, 'vim').rglob('*.vim'))
    assert 'OctNumber' in vim_files and '[+\\-*/&|^~]' in vim_files
    assert re.search(r'hi def link \w+OctNumber Number', vim_files)


# --- Generated documentation ----------------------------------------------------------------

def test_generated_docs_describe_the_expression_syntax(tmp_path):
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
    from bespokeasm.assembler.model import AssemblerModel
    from bespokeasm.docsgen import build_documentation_model
    from bespokeasm.docsgen.markdown_generator import MarkdownGenerator

    def docs(config_path):
        InstructionLine.reset_instruction_pattern_cache()
        return MarkdownGenerator(
            build_documentation_model(
                AssemblerModel(str(config_path), 0, DiagnosticReporter())
            )
        ).generate()

    plain = docs(MINCPU_CONFIG)
    assert 'Expression Syntax' not in plain            # nothing differs from the defaults
    assert '| **Bare Numbers** | Hexadecimal |' in docs(HEX_BASE_CONFIG)
    config_path = write_json_config(
        _config(MINCPU_CONFIG, low_high_operators='whole_expression', current_address='value_address'), tmp_path,
    )
    described = docs(config_path)
    assert '`<label+1` is `<(label+1)`' in described
    assert "The address of the operand's own bytes" in described
    assert 'Low and high byte of everything after the operator' in described
    config_path = write_json_config(_config(SIXTEEN_BIT_CONFIG, low_high_operators='tight'), tmp_path)
    assert 'Low and high 16-bit word of the term that follows' in docs(config_path)


@pytest.mark.parametrize(('source', 'addresses'), [
    ('JPA *', [4]), ('*+2', [0]), ('$3000-*-2', [6]), ('.2byte *, *', [7, 10]),
    ('label*2', []), ('x * (y)', []), ('2 * <x', []), ('<*', [1]),
])
def test_current_address_highlighting_tells_address_from_multiply(source, addresses):
    import re

    from bespokeasm.configgen.expression_scopes import CURRENT_ADDRESS_PATTERN
    assert [m.start() for m in re.finditer(CURRENT_ADDRESS_PATTERN, source)] == addresses


@pytest.mark.parametrize(('source', 'operators'), [
    ('<label', [0]), ('>(x+1)', [0]), ('LDI <here+2', [4]), ('1+<2', [2]), ('<*', [0]),
    ('1<<4', []), ('$80 >> 4', []), ('#if X > 5', []), ('a <= b', []), ('#if >ADDR == $12', [4]),
])
def test_low_high_highlighting_tells_operators_from_shifts_and_comparisons(source, operators):
    import re

    from bespokeasm.configgen.expression_scopes import LOW_HIGH_OPERATOR_PATTERN
    assert [m.start() for m in re.finditer(LOW_HIGH_OPERATOR_PATTERN, source)] == operators


@pytest.mark.parametrize(('line', 'positions'), [
    ('  lda #$10', [6]),
    ('  lda # $10', [6]),
    ('  lda #<msg', [6]),
    ('  sta $10, #1', [11]),
    ('#if FOO', []),                   # a preprocessor directive starts the line
    ('  nop ; #1 in a comment', [8]),  # editors scope comments before operands
    ('  lda $10#', []),
    ('  lda #', []),
])
def test_the_immediate_prefix_pattern_matches_where_an_operand_starts(line, positions):
    import re

    from bespokeasm.configgen.expression_scopes import IMMEDIATE_PREFIX_PATTERN
    assert [match.start() for match in re.finditer(IMMEDIATE_PREFIX_PATTERN, line)] == positions


@pytest.mark.parametrize('enabled', [False, True])
def test_generated_grammars_scope_the_isa_dependent_operators_only_when_enabled(tmp_path, enabled):
    import json
    import zipfile

    from bespokeasm.configgen.expression_scopes import CURRENT_ADDRESS_SCOPE
    from bespokeasm.configgen.expression_scopes import IMMEDIATE_PREFIX_SCOPE
    from bespokeasm.configgen.expression_scopes import LOW_HIGH_OPERATOR_SCOPE
    from bespokeasm.configgen.sublime import SublimeConfigGenerator
    from bespokeasm.configgen.vim import VimConfigGenerator
    from bespokeasm.configgen.vscode import VSCodeConfigGenerator

    settings = {'low_high_operators': 'tight', 'current_address': 'instruction_start'} if enabled else {}
    config = _config(MINCPU_CONFIG, **settings)
    if enabled:
        # An operand written after `#` turns on the immediate prefix's rule.
        numeric = next(
            operand for operand_set in config['operand_sets'].values()
            for operand in operand_set['operand_values'].values() if operand.get('type') == 'numeric'
        )
        numeric['prefix'] = '#'
    config_path = write_json_config(config, tmp_path)

    def generate(cls, name):
        InstructionLine.reset_instruction_pattern_cache()
        destination = tmp_path / name
        destination.mkdir()
        cls(str(config_path), 0, str(destination), 'test-lang', '1.0.0', 'testasm').generate()
        return destination

    vscode = generate(VSCodeConfigGenerator, 'vscode')
    grammar = json.loads(next(vscode.rglob('tmGrammar.json')).read_text())
    scopes = [pattern.get('name') for pattern in grammar['repository']['operators']['patterns']]
    theme = next(vscode.rglob('*-theme.json')).read_text()
    with zipfile.ZipFile(next(generate(SublimeConfigGenerator, 'sublime').glob('*.sublime-package'))) as package:
        syntax = package.read(next(n for n in package.namelist() if n.endswith('.sublime-syntax'))).decode()
    vim_files = '\n'.join(path.read_text() for path in generate(VimConfigGenerator, 'vim').rglob('*.vim'))
    for scope in (CURRENT_ADDRESS_SCOPE, LOW_HIGH_OPERATOR_SCOPE, IMMEDIATE_PREFIX_SCOPE):
        assert (scope in scopes) == enabled
        assert (scope in syntax) == enabled
        assert scope in theme                    # the color rule is harmless when unused
    if enabled:
        # They come first, so they win over multiplication and comparison.
        assert scopes[:3] == [CURRENT_ADDRESS_SCOPE, LOW_HIGH_OPERATOR_SCOPE, IMMEDIATE_PREFIX_SCOPE]
    assert ('syn match' in vim_files and 'CurrentAddress /' in vim_files) == enabled
    assert ('LowHighOperator /' in vim_files) == enabled
    assert ('ImmediatePrefix /' in vim_files) == enabled
