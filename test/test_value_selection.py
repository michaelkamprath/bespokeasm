"""MOS 6502 milestone 5: `select_by_value` address operands, which match only when their value
lies in their memory zone, and the pass-1 relaxation that sizes them."""
import contextlib
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope

from test.isa_configs import write_json_config

ZP_ARGUMENT = {'size': 8, 'word_align': True, 'memory_zone': 'ZERO_PAGE'}
ABS_ARGUMENT = {'size': 16, 'word_align': True}


def _opcode(value: int) -> dict:
    return {'value': value, 'size': 8}


def _config() -> dict:
    """A 6502-style instruction set:
    - `lda` has a zero-page form (A5) listed before an absolute form (AD), as variants;
    - `ora` has both forms in one operand set, with the opcodes in the operands (05, 0D);
    - `stz` has only a zero-page form (64);
    - `jmp` is absolute (4C), and `nop` (EA);
    - the macro `ldm` is `lda`."""
    return {
        'description': 'value selection test ISA',
        'general': {
            'address_size': 16, 'min_version': '0.9.0', 'multi_word_endian': 'little',
            'identifier': {'name': 'valsel', 'version': '1.0.0', 'extension': 'asm'},
        },
        'predefined': {'memory_zones': [{'name': 'ZERO_PAGE', 'start': 0, 'end': 0xFF}]},
        'operand_sets': {
            'zero_page': {'operand_values': {
                'zp': {'type': 'address', 'select_by_value': True, 'argument': ZP_ARGUMENT},
            }},
            'absolute': {'operand_values': {'abs': {'type': 'address', 'argument': ABS_ARGUMENT}}},
            'memory': {'operand_values': {
                'zp': {'type': 'address', 'select_by_value': True, 'bytecode': _opcode(0x05), 'argument': ZP_ARGUMENT},
                'abs': {'type': 'address', 'bytecode': _opcode(0x0D), 'argument': ABS_ARGUMENT},
            }},
        },
        'instructions': {
            'nop': {'bytecode': _opcode(0xEA)},
            'lda': {
                'bytecode': _opcode(0xA5),
                'operands': {'count': 1, 'operand_sets': {'list': ['zero_page']}},
                'variants': [{'bytecode': _opcode(0xAD), 'operands': {'count': 1, 'operand_sets': {'list': ['absolute']}}}],
            },
            'ora': {'bytecode': {'value': 0, 'size': 0}, 'operands': {'count': 1, 'operand_sets': {'list': ['memory']}}},
            'stz': {'bytecode': _opcode(0x64), 'operands': {'count': 1, 'operand_sets': {'list': ['zero_page']}}},
            'jmp': {'bytecode': _opcode(0x4C), 'operands': {'count': 1, 'operand_sets': {'list': ['absolute']}}},
        },
        'macros': {
            'ldm': [{'operands': {'count': 1, 'operand_sets': {'list': ['absolute']}}, 'instructions': ['lda @ARG(0)']}],
        },
    }


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assemble(tmp_path, source: str, config: dict | None = None, start: int = 0) -> tuple[bytes, str]:
    """The binary from ``start`` and what the assembler wrote to stderr."""
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    config_path = write_json_config(config or _config(), tmp_path)
    (tmp_path / 'main.asm').write_text(source)
    assembler = Assembler(
        str(tmp_path / 'main.asm'), config_path, True, str(tmp_path / 'out.bin'), start, None, 0,
        False, None, None, 0, [], [],
    )
    stderr = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.bin').read_bytes(), stderr.getvalue()


def _bytes(tmp_path, source: str, config: dict | None = None, start: int = 0) -> list[int]:
    return list(_assemble(tmp_path, source, config, start)[0])


def _error(tmp_path, source: str, config: dict | None = None) -> str:
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, source, config)
    return str(info.value)


@pytest.mark.parametrize(('source', 'expected'), [
    ('lda $10', [0xA5, 0x10]),
    ('lda $FF', [0xA5, 0xFF]),
    ('lda $100', [0xAD, 0x00, 0x01]),
    ('lda $1234', [0xAD, 0x34, 0x12]),
    ('ora $10', [0x05, 0x10]),                   # both forms in one operand set
    ('ora $1234', [0x0D, 0x34, 0x12]),
    ('ldm $10', [0xA5, 0x10]),                   # through a macro
    ('ldm $1234', [0xAD, 0x34, 0x12]),
])
def test_the_value_selects_the_form(tmp_path, source, expected):
    assert _bytes(tmp_path, f'{source}\n') == expected


@pytest.mark.parametrize('source', [
    'ZP = $20\nlda ZP\n',
    'lda ZP\nZP = $20\n',                        # a constant defined later
    'lda ZP+1\nZP = $1F\n',
])
def test_constants_select_the_form_wherever_they_are_defined(tmp_path, source):
    assert _bytes(tmp_path, source) == [0xA5, 0x20]


def test_a_label_placed_in_zero_page_later_in_the_source_selects_zero_page(tmp_path):
    source = (
        '.org $0200\n'
        'lda counter\n'
        'lda table\n'
        '.memzone ZERO_PAGE\n'
        '.org $40\n'
        'counter: .byte 0\n'
        '.memzone GLOBAL\n'
        '.org $0300\n'
        'table: .byte 1\n'
    )
    binary = _bytes(tmp_path, source, start=0x200)
    assert binary[:5] == [0xA5, 0x40, 0xAD, 0x00, 0x03]


def test_labels_after_a_relaxed_line_move_down(tmp_path):
    assert _bytes(tmp_path, '.org $0200\nlda $10\nhere: jmp here\n', start=0x200) == [0xA5, 0x10, 0x4C, 0x02, 0x02]


def test_relaxation_repeats_until_no_line_changes(tmp_path):
    """At $FA, `t` starts at $100, outside zero page. `lda $10` relaxes first, which moves `t`
    to $FF, so `lda t` relaxes next and `t` settles at $FE."""
    source = '.org $FA\nlda $10\nlda t\nt: nop\n'
    assert _bytes(tmp_path, source, start=0xFA) == [0xA5, 0x10, 0xA5, 0xFE, 0xEA]


def test_a_line_whose_value_only_fits_after_it_shrinks_stays_absolute(tmp_path):
    """Both lines would fit in zero page if both were 2 bytes, but `t` is $100 while they are 3,
    and lines only ever shrink from the larger form."""
    source = '.org $FA\nlda t\nlda t\nt: nop\n'
    assert _bytes(tmp_path, source, start=0xFA) == [0xAD, 0x00, 0x01, 0xAD, 0x00, 0x01, 0xEA]


def test_a_zero_page_only_instruction_takes_its_form_before_the_value_is_known(tmp_path):
    source = '.org $0200\nstz counter\n.memzone ZERO_PAGE\ncounter: .byte 0\n'
    assert _bytes(tmp_path, source, start=0x200)[:2] == [0x64, 0x00]


@pytest.mark.parametrize(('source', 'expected'), [
    # `$1FF - t` is $FF while the lines are 3 bytes, and $101 once they are 2.
    ('.org $FA\nlda $10\nlda $1FF - t\nt: nop\n', '"$1FF - t" is $0101, outside memory zone ZERO_PAGE'),
    ('stz $1234\n', '"$1234" is $1234, outside memory zone ZERO_PAGE'),
])
def test_a_value_that_leaves_its_zone_is_an_error(tmp_path, source, expected):
    message = _error(tmp_path, source)
    assert expected in message
    assert 'its instruction was sized for that zone' in message


def test_a_value_selected_form_longer_than_the_form_it_replaces_is_an_error(tmp_path):
    config = _config()
    config['operand_sets']['zero_page']['operand_values']['zp']['argument'] = {
        'size': 24, 'word_align': True, 'memory_zone': 'ZERO_PAGE',
    }
    message = _error(tmp_path, 'lda $10\n', config)
    assert 'the form that select_by_value selects for "lda $10" is 4 words, longer than the 3-word form' in message


def test_duplicate_labels_are_still_an_error(tmp_path):
    message = _error(tmp_path, 'here: lda $10\nhere: nop\n')
    assert 'label "here" is defined multiple times' in message


def test_pass_one_warnings_are_reported_once(tmp_path):
    _, stderr = _assemble(tmp_path, '.org $10\nlda $10\n.zerountil $05\n')
    assert stderr.count('.zerountil target address is before the current address') == 1


def test_operand_labels_follow_the_relaxed_line(tmp_path):
    source = '.org $0200\nlda $10\nlda @value: $1234\njmp value\n'
    # `lda $10` is 2 bytes, so the second `lda`'s operand starts at $0203.
    assert _bytes(tmp_path, source, start=0x200)[-3:] == [0x4C, 0x03, 0x02]


def test_a_provisional_layout_may_overflow_a_zone_that_the_final_layout_fits(tmp_path):
    """Before relaxation both lines are 3 bytes and overrun the 4-byte zone; relaxed, they fit."""
    config = _config()
    config['predefined']['memory_zones'].append({'name': 'SMALL', 'start': 0x300, 'end': 0x303})
    source = '.memzone SMALL\nlda $10\nlda $20\n'
    assert _bytes(tmp_path, source, config, start=0x300) == [0xA5, 0x10, 0xA5, 0x20]


def test_an_undefined_label_is_reported_as_unknown(tmp_path):
    assert 'unknown label "nowhere"' in _error(tmp_path, 'lda nowhere\n')
