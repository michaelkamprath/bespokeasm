"""MOS 6502 milestone 3, end to end: indirect operands written in parentheses (`enclosure`),
`indirect_indexed_numeric` operands such as `($10,x)`, and how a parenthesized operand is read.

Unit tests live with their modules: test_parsing (the enclosure helpers),
test_instruction_parsing (the operand types), test_operand_parser (the per-instruction rule),
test_error_diagnostics (messages and config errors), test_configgen (editors) and
test_docsgen (generated docs)."""
import contextlib
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML

BYTE = {'size': 8, 'word_align': True}
WORD = {'size': 16, 'word_align': True}


def _opcode(value: int) -> dict:
    return {'value': value, 'size': 8}


def _config() -> dict:
    """A 6502-style instruction set. `lda` takes `#imm`, `abs` or `(zp,x)`, and in a second
    variant `(zp),y`; `ldx` takes only `abs`; `jmp` takes `abs`, or `(vec)` in a second variant.
    The macro `ldi` takes what `lda` takes; `pick` is `ldx abs`, or `jmp (vec)` in a second variant."""
    return {
        'description': 'enclosures test ISA',
        'general': {
            'address_size': 16, 'min_version': '0.9.0', 'multi_word_endian': 'little', 'registers': ['x', 'y'],
            'identifier': {'name': 'enclosures', 'version': '1.0.0', 'extension': 'asm'},
        },
        'operand_sets': {
            'lda_ops': {'operand_values': {
                'imm': {'type': 'numeric', 'prefix': '#', 'bytecode': _opcode(0xA9), 'argument': BYTE},
                'abs': {'type': 'numeric', 'bytecode': _opcode(0xAD), 'argument': WORD},
                'izx': {
                    'type': 'indirect_indexed_numeric', 'enclosure': 'parentheses',
                    'index_operands': {'x': {'type': 'register', 'register': 'x'}},
                    'bytecode': _opcode(0xA1), 'argument': BYTE,
                },
            }},
            'zp_indirect': {'operand_values': {
                'izy': {'type': 'indirect_numeric', 'enclosure': 'parentheses', 'bytecode': _opcode(0xB1),
                        'argument': BYTE},
            }},
            'y_register': {'operand_values': {'y': {'type': 'register', 'register': 'y'}}},
            'absolute': {'operand_values': {'abs': {'type': 'numeric', 'argument': WORD}}},
            # 6809-style `[n,x]` and `[n,y]`: each index register adds its own bits after the operand's.
            'indexed_bracket': {'operand_values': {'nxy': {
                'type': 'indirect_indexed_numeric', 'bytecode': {'value': 0b1001, 'size': 4}, 'argument': BYTE,
                'index_operands': {
                    'x': {'type': 'register', 'register': 'x', 'bytecode': {'value': 0, 'size': 4}},
                    'y': {'type': 'register', 'register': 'y', 'bytecode': {'value': 1, 'size': 4}},
                },
            }}},
            # Only the index bits tell the forms apart.
            'index_bits_only': {'operand_values': {'nxy': {
                'type': 'indirect_indexed_numeric', 'enclosure': 'braces', 'argument': BYTE,
                'index_operands': {
                    'x': {'type': 'register', 'register': 'x', 'bytecode': {'value': 0xC, 'size': 4}},
                    'y': {'type': 'register', 'register': 'y', 'bytecode': {'value': 0xD, 'size': 4}},
                },
            }}},
            'jmp_abs': {'operand_values': {
                'abs': {'type': 'numeric', 'bytecode': _opcode(0x4C), 'argument': WORD},
            }},
            'jmp_ind': {'operand_values': {
                'ind': {'type': 'indirect_numeric', 'enclosure': 'parentheses', 'bytecode': _opcode(0x6C),
                        'argument': WORD},
            }},
        },
        'instructions': {
            'lda': {
                'bytecode': {'value': 0, 'size': 0},
                'operands': {'count': 1, 'operand_sets': {'list': ['lda_ops']}},
                'variants': [{
                    'bytecode': {'value': 0, 'size': 0},
                    'operands': {'count': 2, 'operand_sets': {'list': ['zp_indirect', 'y_register']}},
                }],
            },
            'ldx': {'bytecode': _opcode(0xAE), 'operands': {'count': 1, 'operand_sets': {'list': ['absolute']}}},
            'ldd': {'bytecode': _opcode(0xEC), 'operands': {'count': 1, 'operand_sets': {'list': ['indexed_bracket']}}},
            'ldb': {'bytecode': _opcode(0xE6), 'operands': {'count': 1, 'operand_sets': {'list': ['index_bits_only']}}},
            # The `(vec)` form is in a later variant than `abs`, which alone would take `(vec)`.
            'jmp': {
                'bytecode': {'value': 0, 'size': 0},
                'operands': {'count': 1, 'operand_sets': {'list': ['jmp_abs']}},
                'variants': [{
                    'bytecode': {'value': 0, 'size': 0},
                    'operands': {'count': 1, 'operand_sets': {'list': ['jmp_ind']}},
                }],
            },
        },
        'macros': {
            'ldi': [{
                'operands': {'count': 1, 'operand_sets': {'list': ['lda_ops']}},
                'instructions': ['lda @ARG(0)'],
            }],
            # `abs` alone would take `(vec)`; it expands to `ldx` so taking it would show.
            'pick': [
                {'operands': {'count': 1, 'operand_sets': {'list': ['absolute']}}, 'instructions': ['ldx @ARG(0)']},
                {'operands': {'count': 1, 'operand_sets': {'list': ['jmp_ind']}}, 'instructions': ['jmp (@ARG(0))']},
            ],
        },
    }


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assemble(tmp_path, source: str, config: dict | None = None) -> bytes:
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    config_path = tmp_path / 'isa.yaml'
    with open(config_path, 'w') as handle:
        YAML().dump(config or _config(), handle)
    (tmp_path / 'main.asm').write_text(source)
    assembler = Assembler(
        str(tmp_path / 'main.asm'), str(config_path), True, str(tmp_path / 'out.bin'), 0, None, 0,
        False, None, None, 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.bin').read_bytes()


def _assembly_error(tmp_path, source: str) -> str:
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, source)
    return str(info.value)


@pytest.mark.parametrize(('source', 'expected'), [
    ('lda #$10', [0xA9, 0x10]),
    ('lda $1234', [0xAD, 0x34, 0x12]),
    ('lda ($10,x)', [0xA1, 0x10]),
    ('lda ( $10 , X )', [0xA1, 0x10]),
    ('lda ($10),y', [0xB1, 0x10]),
    ('lda ((1+2)*3,x)', [0xA1, 0x09]),
    ('lda ($10+1)*2', [0xAD, 0x22, 0x00]),       # parentheses that are only part of the operand
    ('lda #($10)', [0xA9, 0x10]),                # after `#` the value is never indirect
    ('ldx ($10)', [0xAE, 0x10, 0x00]),           # `ldx` gives parentheses no meaning
    ('jmp ($1234)', [0x6C, 0x34, 0x12]),
    ('jmp (vec*2)', [0x6C, 0x68, 0x24]),
    ('jmp ((vec))', [0x6C, 0x34, 0x12]),         # no `(( ))` form, so it is `(vec)` inside parentheses
    ('jmp $1234', [0x4C, 0x34, 0x12]),
    ('ldd [$10,x]', [0xEC, 0x90, 0x10]),
    ('ldd [$10, Y]', [0xEC, 0x91, 0x10]),
    ('ldb {$10,y}', [0xE6, 0xD0, 0x10]),
    ('pick ($1234)', [0x6C, 0x34, 0x12]),
    ('pick $1234', [0xAE, 0x34, 0x12]),
])
def test_parenthesized_operands_select_their_forms(tmp_path, source, expected):
    assert _assemble(tmp_path, f'vec = $1234\n{source}\n') == bytes(expected)


@pytest.mark.parametrize('source', ['lda ($10)', 'ldi ($10)'])
def test_parentheses_around_a_whole_operand_are_indirect_where_the_instruction_says_so(tmp_path, source):
    message = _assembly_error(tmp_path, f'{source}\n')
    assert 'parentheses around the whole operand select another form here; expected (address, x)' in message


def test_bracketed_operands_are_unchanged(tmp_path):
    config = _config()
    jmp_indirect = config['operand_sets']['jmp_ind']['operand_values']['ind']
    del jmp_indirect['enclosure']
    assert _assemble(tmp_path, 'jmp [$1234]\njmp ($1234)\n', config) == bytes([0x6C, 0x34, 0x12, 0x4C, 0x34, 0x12])


def test_index_bytecode_is_kept_when_the_operand_has_none_of_its_own(tmp_path):
    """`[hl + a]` used to drop the index register's bits when the operand had no `bytecode`,
    because the operand then had no bytecode position."""
    config = _config()
    config['general']['registers'] = ['x', 'y', 'hl', 'a']
    config['operand_sets']['hl_indexed'] = {'operand_values': {'hl_idx': {
        'type': 'indirect_indexed_register', 'register': 'hl',
        'index_operands': {
            'a': {'type': 'register', 'register': 'a', 'bytecode': {'value': 0xA, 'size': 4}},
            'x': {'type': 'register', 'register': 'x', 'bytecode': {'value': 0xB, 'size': 4}},
        },
    }}}
    config['instructions']['ldm'] = {
        'bytecode': {'value': 0x7, 'size': 4}, 'operands': {'count': 1, 'operand_sets': {'list': ['hl_indexed']}},
    }
    assert _assemble(tmp_path, 'ldm [hl + a]\nldm [hl + x]\n', config) == bytes([0x7A, 0x7B])


def _numeric_index_config(enumeration: bool, **general) -> dict:
    """`ldn [value, index]`, where the index is a 4-bit number, and with ``enumeration`` a
    `numeric_enumeration` listed after it that gives index 2 the bits 0xF."""
    config = _config()
    config['general'].update(general)
    index_operands = {'n': {'type': 'numeric_bytecode', 'bytecode': {'size': 4, 'min': 0, 'max': 15}}}
    if enumeration:
        index_operands['e'] = {'type': 'numeric_enumeration', 'bytecode': {'size': 4, 'value_dict': {2: 0xF}}}
    config['operand_sets']['numeric_index'] = {'operand_values': {'ni': {
        'type': 'indirect_indexed_numeric', 'argument': BYTE, 'index_operands': index_operands,
    }}}
    config['instructions']['ldn'] = {
        'bytecode': {'value': 0xD, 'size': 4}, 'operands': {'count': 1, 'operand_sets': {'list': ['numeric_index']}},
    }
    return config


def test_index_operands_are_tried_in_operand_set_order(tmp_path):
    # An enumeration is tried before a numeric bytecode, as in an operand set, so `2` is 0xF.
    assert _assemble(tmp_path, 'ldn [$10, 2]\n', _numeric_index_config(enumeration=True)) == bytes([0xDF, 0x10])


def test_index_operands_read_numbers_in_the_default_base(tmp_path):
    config = _numeric_index_config(enumeration=False, default_numeric_base='hex')
    assert _assemble(tmp_path, 'ldn [10, b]\n', config) == bytes([0xDB, 0x10])


def _plus_index_config(reverse_argument_order: bool = False) -> dict:
    """`ldp [value + index]`, where the index is any operand: `[a + offset]`, `[b + offset]`
    with an 8-bit offset, or the register `x`."""
    config = _config()
    config['general']['registers'] = ['x', 'y', 'a', 'b']
    config['operand_sets']['plus_index'] = {'operand_values': {'based': {
        'type': 'indirect_indexed_numeric', 'index_separator': 'plus',
        'bytecode': {'value': 0x2, 'size': 4}, 'argument': WORD,
        'index_operands': {
            'a_off': {'type': 'indirect_register', 'register': 'a', 'bytecode': {'value': 0xA, 'size': 4},
                      'offset': BYTE},
            'b_off': {'type': 'indirect_register', 'register': 'b', 'bytecode': {'value': 0xB, 'size': 4},
                      'offset': BYTE},
            'x': {'type': 'register', 'register': 'x', 'bytecode': {'value': 0xF, 'size': 4}},
        },
    }}}
    config['instructions']['ldp'] = {
        'bytecode': _opcode(0xEE), 'operands': {'count': 1, 'operand_sets': {'list': ['plus_index']}},
    }
    config['instructions']['stp'] = {
        'bytecode': _opcode(0xEF),
        'operands': {'count': 2, 'operand_sets': {
            'list': ['plus_index', 'absolute'], 'reverse_argument_order': reverse_argument_order,
        }},
    }
    return config


@pytest.mark.parametrize(('source', 'expected'), [
    # The index's offset follows the value.
    ('ldp [$1234 +[a+6]]', [0xEE, 0x2A, 0x34, 0x12, 0x06]),
    ('ldp [$1234 + 2*n + [b - 1]]', [0xEE, 0x2B, 0x38, 0x12, 0xFF]),
    ('ldp [$1000 + (n+1) + x]', [0xEE, 0x2F, 0x03, 0x10]),
    ('ldp [$1000 + [a]]', [0xEE, 0x2A, 0x00, 0x10, 0x00]),
])
def test_plus_separates_the_value_from_an_index_of_any_operand_type(tmp_path, source, expected):
    assert _assemble(tmp_path, f'n = 2\n{source}\n', _plus_index_config()) == bytes(expected)


@pytest.mark.parametrize(('reverse', 'expected'), [
    (False, [0xEF, 0x2A, 0x34, 0x12, 0x06, 0x66, 0x55]),
    # Reversing the argument order reverses the operands, not one operand's own arguments.
    (True, [0xEF, 0x2A, 0x66, 0x55, 0x34, 0x12, 0x06]),
])
def test_an_index_argument_stays_with_its_operand(tmp_path, reverse, expected):
    config = _plus_index_config(reverse_argument_order=reverse)
    assert _assemble(tmp_path, 'stp [$1234 + [a+6]], $5566\n', config) == bytes(expected)


@pytest.mark.parametrize('source', ['ldp [$1234 + [y+6]]', 'ldp [$1234, x]', 'ldp [+ x]'])
def test_plus_index_errors_name_the_expected_form(tmp_path, source):
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, f'{source}\n', _plus_index_config())
    assert 'is not valid; expected [address + index]' in str(info.value)


def test_a_plus_index_is_the_last_term_that_reads_as_one(tmp_path):
    # Any split leaves a number on both sides; the index is the last term, so `$10 + 1` is the value.
    config = _numeric_index_config(enumeration=False)
    config['operand_sets']['numeric_index']['operand_values']['ni']['index_separator'] = 'plus'
    assert _assemble(tmp_path, 'ldn [$10 + 1 + 2]\n', config) == bytes([0xD2, 0x11])


@pytest.mark.parametrize('source', ['lda (,x)', 'lda ($10,)', 'lda ($10,x,x)'])
def test_a_comma_index_needs_exactly_one_value_and_one_index(tmp_path, source):
    assert 'is not valid' in _assembly_error(tmp_path, f'{source}\n')
