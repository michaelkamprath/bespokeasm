"""MOS 6502 milestone 4: where a `relative_address` operand measures its offset from, set by
`offset_base`, and relative operands inside macros measuring from their own instruction."""
import contextlib
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope

from test.isa_configs import write_json_config

BRANCH_ARGUMENT = {'size': 8, 'word_align': True, 'min': -128, 'max': 127}


def _config(**relative) -> dict:
    """`bne` is a 2-byte branch whose offset is set by ``relative``; `jsr` is a 3-byte
    instruction with a 16-bit relative operand, so the bases differ by more than one."""
    return {
        'description': 'relative offset base test ISA',
        'general': {
            'address_size': 16, 'min_version': '0.9.0', 'multi_word_endian': 'little',
            'identifier': {'name': 'relbase', 'version': '1.0.0', 'extension': 'asm'},
        },
        'operand_sets': {
            'branch': {'operand_values': {'rel': {'type': 'relative_address', 'argument': BRANCH_ARGUMENT, **relative}}},
            'long': {'operand_values': {'rel': {
                'type': 'relative_address', 'argument': {'size': 16, 'word_align': True}, **relative,
            }}},
        },
        'instructions': {
            'nop': {'bytecode': {'value': 0xEA, 'size': 8}},
            'bne': {'bytecode': {'value': 0xD0, 'size': 8}, 'operands': {'count': 1, 'operand_sets': {'list': ['branch']}}},
            'jsr': {'bytecode': {'value': 0x20, 'size': 8}, 'operands': {'count': 1, 'operand_sets': {'list': ['long']}}},
        },
        'macros': {
            # The branch is the macro's second instruction.
            'skip': [{'operands': {'count': 1, 'operand_sets': {'list': ['branch']}}, 'instructions': ['nop', 'bne @ARG(0)']}],
            # The branch is the macro's first instruction, and another instruction follows it.
            'bnop': [{'operands': {'count': 1, 'operand_sets': {'list': ['branch']}}, 'instructions': ['bne @ARG(0)', 'nop']}],
            # A macro using a macro.
            'skip2': [{
                'operands': {'count': 1, 'operand_sets': {'list': ['branch']}}, 'instructions': ['nop', 'skip @ARG(0)'],
            }],
        },
    }


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assemble(tmp_path, source: str, config: dict) -> bytes:
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    config_path = write_json_config(config, tmp_path)
    (tmp_path / 'main.asm').write_text(source)
    assembler = Assembler(
        str(tmp_path / 'main.asm'), config_path, True, str(tmp_path / 'out.bin'), 0, None, 0,
        False, None, None, 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.bin').read_bytes()


def _assembly_error(tmp_path, source: str, config: dict) -> str:
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, source, config)
    return str(info.value)


@pytest.mark.parametrize(('relative', 'expected'), [
    ({}, [0xD0, 0x00, 0x20, 0xFE, 0xFF]),
    ({'offset_base': 'instruction_start'}, [0xD0, 0x00, 0x20, 0xFE, 0xFF]),
    ({'offset_base': 'last_word'}, [0xD0, 0xFF, 0x20, 0xFC, 0xFF]),
    ({'offset_base': 'next_instruction'}, [0xD0, 0xFE, 0x20, 0xFB, 0xFF]),
    # Legacy: `offset_from_instruction_end: true` is `offset_base: last_word`.
    ({'offset_from_instruction_end': True}, [0xD0, 0xFF, 0x20, 0xFC, 0xFF]),
    ({'offset_from_instruction_end': False}, [0xD0, 0x00, 0x20, 0xFE, 0xFF]),
])
def test_offset_base_sets_where_the_offset_is_measured_from(tmp_path, relative, expected):
    # `here` is at 0, `jsr` at 2: its 3 bytes end at 4 and the next instruction is at 5.
    assert _assemble(tmp_path, 'here: bne here\njsr here\n', _config(**relative)) == bytes(expected)


def test_a_6502_branch_to_itself(tmp_path):
    assert _assemble(tmp_path, 'here: bne here\n', _config(offset_base='next_instruction')) == bytes([0xD0, 0xFE])


@pytest.mark.parametrize(('target', 'fitting', 'offset', 'expected'), [
    # The branch is at $100, so offsets are measured from $102.
    ('$102 + 128', '$102 + 127', 0x7F, 'Relative address offset is larger than configured maximum value of 127'),
    ('$102 - 129', '$102 - 128', 0x80, 'Relative address offset is smaller than configured minimum value of -128'),
])
def test_the_range_applies_to_the_offset_from_the_base(tmp_path, target, fitting, offset, expected):
    config = _config(offset_base='next_instruction')
    assert expected in _assembly_error(tmp_path, f'.org $100\nbne {target}\n', config)
    assert _assemble(tmp_path, f'.org $100\nbne {fitting}\n', config)[-2:] == bytes([0xD0, offset])


@pytest.mark.parametrize(('base', 'expected'), [
    # `skip here` at 0 is `nop` at 0, then `bne here` at 1.
    ('instruction_start', [0xEA, 0xD0, 0xFF]),
    ('last_word', [0xEA, 0xD0, 0xFE]),
    ('next_instruction', [0xEA, 0xD0, 0xFD]),
])
def test_a_branch_in_a_macro_measures_from_its_own_instruction(tmp_path, base, expected):
    assert _assemble(tmp_path, 'here: skip here\n', _config(offset_base=base)) == bytes(expected)


@pytest.mark.parametrize(('base', 'expected'), [
    # `bnop there` at 0 is `bne there` at 0, then `nop` at 2; `there` is 3.
    ('last_word', [0xD0, 0x02, 0xEA]),
    ('next_instruction', [0xD0, 0x01, 0xEA]),
])
def test_a_branch_followed_by_more_of_its_macro_measures_from_its_own_end(tmp_path, base, expected):
    assert _assemble(tmp_path, 'bnop there\nthere:\n', _config(offset_base=base)) == bytes(expected)


def test_a_branch_in_a_nested_macro_measures_from_its_own_instruction(tmp_path):
    # `skip2 here` at 0 is `nop` at 0, then `skip here`: `nop` at 1, then `bne here` at 2.
    config = _config(offset_base='next_instruction')
    assert _assemble(tmp_path, 'here: skip2 here\n', config) == bytes([0xEA, 0xEA, 0xD0, 0xFC])


def test_the_current_address_in_a_macro_is_the_macro_line_address(tmp_path):
    # `*` is where the macro line starts, 1 here, as written; the branch is at 2.
    config = _config(offset_base='next_instruction')
    config['general']['current_address'] = 'instruction_start'
    assert _assemble(tmp_path, 'nop\nskip *\n', config) == bytes([0xEA, 0xEA, 0xD0, 0xFD])
