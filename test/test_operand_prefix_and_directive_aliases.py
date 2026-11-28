"""MOS 6502 milestone 2, end to end: the `#` immediate prefix on numeric operands, directive
aliases such as `.word` for `.2byte`, and `.fill` with only a count, assembled from source.

Unit tests and messages live with their modules: test_instruction_parsing (the operand),
test_directive_lines and test_data_line_word_sizes (directives), test_error_diagnostics
(messages and config errors), test_configgen and test_sublime_hover (editors), and
test_docsgen (hovers and generated docs)."""
import contextlib
import copy
import importlib.resources as pkg_resources
import io
import pathlib
import re

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML

from test import config_files

BASE_CONFIG = pkg_resources.files(config_files).joinpath('test_default_numeric_base.yaml')


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _config(**general) -> dict:
    """An instruction set with a 6502-style `lda`: `lda #$10` is $A9 $10 and `lda $1234` is
    $AD $34 $12, from the opcode's high nibble and each operand's low nibble. Its `ldi` takes a
    numeric operand with no prefix."""
    with open(BASE_CONFIG) as handle:
        config = copy.deepcopy(YAML(typ='safe').load(handle))
    config['general'].update({
        'default_numeric_base': 'decimal', 'multi_word_endian': 'little', 'low_high_operators': 'tight',
    })
    config['general'].update(general)
    config['operand_sets']['imm_or_abs'] = {'operand_values': {
        'imm': {
            'type': 'numeric', 'prefix': '#',
            'bytecode': {'value': 9, 'size': 4}, 'argument': {'size': 8, 'word_align': True},
        },
        'abs': {
            'type': 'numeric',
            'bytecode': {'value': 13, 'size': 4}, 'argument': {'size': 16, 'word_align': True},
        },
    }}
    config['operand_sets']['imm_only'] = {'operand_values': {
        'imm': {'type': 'numeric', 'prefix': '#', 'argument': {'size': 8, 'word_align': True}},
    }}
    config['instructions']['lda'] = {
        'bytecode': {'value': 10, 'size': 4},
        'operands': {'count': 1, 'operand_sets': {'list': ['imm_or_abs']}},
    }
    config['instructions']['adc'] = {
        'bytecode': {'value': 0x69, 'size': 8},
        'operands': {'count': 1, 'operand_sets': {'list': ['imm_only']}},
    }
    return config


ALIASES = {'word': '2byte', 'addr': '2byte', 'res': 'fill', 'text': 'byte'}


def _write_config(tmp_path, config: dict):
    config_path = tmp_path / 'isa.yaml'
    with open(config_path, 'w') as handle:
        YAML().dump(config, handle)
    return config_path


def _assemble(tmp_path, config: dict, source: str, listing: bool = False):
    """The binary of ``source``, or with ``listing`` its listing text."""
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    config_path = _write_config(tmp_path, config)
    (tmp_path / 'main.asm').write_text(source)
    listing_path = tmp_path / 'out.lst'
    assembler = Assembler(
        str(tmp_path / 'main.asm'), str(config_path), not listing, str(tmp_path / 'out.bin'), 0, None, 0,
        listing, 'listing' if listing else None, str(listing_path) if listing else None, 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return listing_path.read_text() if listing else (tmp_path / 'out.bin').read_bytes()


def _assembly_error(tmp_path, config: dict, source: str) -> str:
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, config, source)
    return str(info.value)


# --- The `#` immediate prefix ---------------------------------------------------------------

@pytest.mark.parametrize(('source', 'expected'), [
    ('lda #$10', [0xA9, 0x10]),
    ('lda # $10', [0xA9, 0x10]),            # space after `#` is allowed
    ('lda $1234', [0xAD, 0x34, 0x12]),
    ('lda $10', [0xAD, 0x10, 0x00]),        # without `#` it is never the immediate form
    ('lda #(1+2)*3', [0xA9, 0x09]),
    ("lda #'A'", [0xA9, 0x41]),
    ('lda #<$1234', [0xA9, 0x34]),
    ('lda #>$1234', [0xA9, 0x12]),
    ('adc #5', [0x69, 0x05]),
])
def test_the_prefix_selects_the_immediate_form(tmp_path, source, expected):
    assert _assemble(tmp_path, _config(), f'{source}\n') == bytes(expected)


# --- Directive aliases ----------------------------------------------------------------------

def test_aliases_assemble_as_the_directive_they_stand_for(tmp_path):
    source = (
        'start:\n'
        '  .word start+$1234, $5678\n'
        '  .ADDR start\n'             # directive names ignore case
        '  .res 3\n'
        '  .res 2, $EA\n'
        '  .text "Hi", 0\n'
    )
    expected = [0x34, 0x12, 0x78, 0x56, 0x00, 0x00, 0, 0, 0, 0xEA, 0xEA, 0x48, 0x69, 0x00]
    assert _assemble(tmp_path, _config(directive_aliases=ALIASES), source) == bytes(expected)


def test_the_listing_shows_the_alias_as_written(tmp_path):
    listing = _assemble(tmp_path, _config(directive_aliases=ALIASES), '.word $1234\n.res 2, 1\n', listing=True)
    assert re.search(r'\| 34 12 +\| +\.word \$1234 ', listing)
    assert re.search(r'\| 01 01 +\| +\.res 2, 1 ', listing)
    assert '.2byte' not in listing and '.fill' not in listing


def test_an_alias_name_with_a_colon_is_still_a_local_label(tmp_path):
    source = 'start:\n.word: .byte 7\n  .2byte .word\n'
    assert _assemble(tmp_path, _config(directive_aliases=ALIASES), source) == bytes([7, 0, 0])


def test_aliases_exist_only_where_the_instruction_set_defines_them(tmp_path):
    assert 'unknown directive ".word"' in _assembly_error(tmp_path, _config(), '.word 1\n')


def test_an_alias_follows_the_flow_rules_of_its_directive(tmp_path):
    """`.res` is `.fill`, so a flow expression may be its fill value but not its count."""
    harness = pathlib.Path(__file__).resolve().parent / 'flow_harnesses' / 'm1' / 'flow-counters-m1.yaml'
    with open(harness) as handle:
        config = YAML(typ='safe').load(handle)
    config['general']['directive_aliases'] = {'res': 'fill'}
    tracked = '#track stack\n{}\n#endtrack stack\n'
    assert _assemble(tmp_path, config, tracked.format('.res 2, COUNTER(stack)')) == bytes([0, 0])
    message = _assembly_error(tmp_path, config, tracked.format('.res COUNTER(stack)'))
    assert 'flow expressions are not allowed in fill-count expressions' in message


# --- `.fill` with only a count ----------------------------------------------------------------

def test_fill_with_only_a_count_fills_with_zero(tmp_path):
    assert _assemble(tmp_path, _config(), '.fill 3\n.byte 1\n.fill 2, $FF\n') == bytes([0, 0, 0, 1, 0xFF, 0xFF])


def test_upper_case_data_directives_assemble(tmp_path):
    """`.BYTE` used to fail with a KeyError."""
    assert _assemble(tmp_path, _config(), '.BYTE 1\n.2BYTE $1234\n') == bytes([1, 0x34, 0x12])
