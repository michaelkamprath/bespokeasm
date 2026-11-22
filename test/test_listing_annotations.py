"""Tests for the framework's ``listing`` annotation namespace in ``-t listing`` output."""
import contextlib
import copy
import importlib.resources as pkg_resources
import io
import json

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML

from test import config_files


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _config(tmp_path, output_formats=None) -> str:
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    if output_formats is not None:
        config['output_formats'] = copy.deepcopy(output_formats)
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    return str(path)


def _listing(tmp_path, source: str, fmt: str = 'listing', output_formats=None) -> tuple[str, str]:
    """The listing text and the warnings, for a source that ends with a newline."""
    # Each run starts clean: the global symbol scope is cached across assemblies in one process.
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    source_path = tmp_path / 'main.asm'
    source_path.write_text(source)
    output_path = tmp_path / 'out.txt'
    stderr = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
        Assembler(
            str(source_path), _config(tmp_path, output_formats), False, None, 0, None, 0,
            True, fmt, str(output_path), 0, [], [],
        ).assemble_bytecode()
    return output_path.read_text(), stderr.getvalue()


def _rows(listing: str) -> list[str]:
    """The listing's rows, without the file header and with trailing spaces removed."""
    rows = []
    for line in (line.rstrip() for line in listing.split('\n')):
        is_border = line.startswith('-') and '+' in line
        if line and not is_border and not line.startswith(('File:', '\f', ' line ')):
            rows.append(line)
    return rows


def _instructions(listing: str) -> list[str]:
    """The instruction column of each row (or the whole line for rows outside the table)."""
    result = []
    for row in _rows(listing):
        parts = row.split('|')
        result.append(parts[3].strip() if len(parts) > 3 else row.strip())
    return result


# ---- heading and page_break ---------------------------------------------------------------

def test_heading_comes_before_the_symbols_annotations(tmp_path):
    source = 'start:\n    ld a, b, c\n#annotate listing heading="Lookup tables"\ntable:\n    .byte 1\n'
    listing, warnings = _listing(tmp_path, source)
    assert warnings == ''
    assert _instructions(listing) == [
        'start:', 'ld a, b, c',
        'Lookup tables', '-------------',
        '#annotate listing heading="Lookup tables"', 'table:', '.byte 1',
    ]


def test_page_break_repeats_the_headers(tmp_path):
    source = 'start:\n    ld a, b, c\n#annotate listing page_break\nnext:\n    .byte 1\n'
    listing, _ = _listing(tmp_path, source)
    first, second = listing.split('\f')
    assert first.count('File: ') == 1 and second.count('File: ') == 1
    # The repeated header says the same file continues.
    assert '(continued)' not in first and 'main.asm (continued)\n' in second
    assert 'next:' not in first and second.index('File: ') < second.index('next:')


def test_page_break_on_the_first_line_of_a_file_writes_one_header(tmp_path):
    listing, _ = _listing(tmp_path, '#annotate listing page_break heading="Start"\nstart:\n    ld a, b, c\n')
    assert listing.count('File: ') == 1 and '(continued)' not in listing
    assert listing.index('\f') < listing.index('File: ') < listing.index('Start\n-----')


# ---- collapse ------------------------------------------------------------------------------

def test_collapse_shows_the_first_row_and_counts_the_rest(tmp_path):
    source = '\n'.join([
        'start:',
        '    ld a, b, c',
        '#annotate listing collapse',
        'table:',
        '    .byte 1, 2, 3, 4, 5, 6, 7, 8, 9, 10',
        '    ; inside the run',
        '    .byte 11, 12',
        'after:',
        '    .byte 99',
    ]) + '\n'
    listing, warnings = _listing(tmp_path, source)
    assert warnings == ''
    rows = _rows(listing)
    assert '| 01 02 03 04 05 06 |     .byte 1, 2, 3, 4, 5, 6, 7, 8, 9, 10' in rows[4]
    # 12 bytes in the run, 6 shown: the summary gives the address of the 7th and counts 6.
    assert rows[5].split('|')[1].strip() == '0009'
    assert rows[5].split('|')[3].strip() == '... 6 more bytes'
    assert _instructions(listing)[6:] == ['after:', '.byte 99']
    assert 'inside the run' not in listing and '0b 0c' not in listing


def test_collapse_counts_every_line_after_the_first_row(tmp_path):
    # The first data line's 3 bytes fill its row; the summary counts the next line's 2.
    source = '#annotate listing collapse\ntable:\n    .byte 1, 2, 3\n    .byte 4, 5\nnext:\n    ld a, b, c\n'
    listing, _ = _listing(tmp_path, source)
    rows = _rows(listing)
    assert rows[3].split('|')[3].strip() == '... 2 more bytes'
    assert rows[3].split('|')[1].strip() == '0003'


def test_collapse_with_nothing_to_omit_adds_no_row(tmp_path):
    listing, _ = _listing(tmp_path, '#annotate listing collapse\ntable:\n    .byte 1, 2\n')
    assert 'more byte' not in listing


def test_collapse_one_omitted_byte_is_singular(tmp_path):
    listing, _ = _listing(tmp_path, '#annotate listing collapse\ntable:\n    .byte 1, 2, 3, 4, 5, 6, 7\n')
    assert '... 1 more byte ' in listing


@pytest.mark.parametrize('source', [
    '#annotate listing collapse\ncode:\n    ld a, b, c\n',
    '#annotate listing collapse\nLIMIT = 5\nld a, b, c\n',
])
def test_collapse_without_data_is_a_warning(tmp_path, source):
    _, warnings = _listing(tmp_path, source)
    assert "'#annotate listing collapse' on" in warnings
    assert 'has no effect: no data follows it' in warnings


# ---- hide ----------------------------------------------------------------------------------

def test_hide_omits_a_label_up_to_the_next_label(tmp_path):
    source = '\n'.join([
        'start:',
        '    ld a, b, c',
        '#annotate listing hide',
        'scratch:',
        '    .byte 1, 2',
        '    ; hidden too',
        '.inner:',
        '    .byte 3',
        'after:',
        '    .byte 4',
    ]) + '\n'
    listing, warnings = _listing(tmp_path, source)
    assert warnings == ''
    # Hiding stops at the next label of any scope, here the local .inner.
    assert _instructions(listing) == ['start:', 'ld a, b, c', '.inner:', '.byte 3', 'after:', '.byte 4']


def test_hide_on_a_constant_omits_only_its_line(tmp_path):
    source = '#annotate listing hide\nLIMIT = 5\nstart:\n    ld a, b, c\n'
    listing, _ = _listing(tmp_path, source)
    assert _instructions(listing) == ['start:', 'ld a, b, c']


def test_hide_wins_over_heading_and_hidden_lines_do_not_widen_columns(tmp_path):
    long_name = 'a_very_long_label_name_that_would_widen_the_instruction_column'
    source = f'start:\n    ld a, b, c\n#annotate listing hide heading="Never"\n{long_name}:\n    .byte 1\n'
    listing, _ = _listing(tmp_path, source)
    assert 'Never' not in listing and long_name not in listing
    # The table is as wide as it would be without the hidden lines at all.
    without, _ = _listing(tmp_path, 'start:\n    ld a, b, c\n')
    border = next(line for line in listing.split('\n') if line.startswith('---'))
    assert border == next(line for line in without.split('\n') if line.startswith('---'))


def test_hidden_bytes_are_still_assembled(tmp_path):
    source = 'start:\n    ld a, b, c\n#annotate listing hide\ndata:\n    .byte $aa\n'
    hex_text, _ = _listing(tmp_path, source, fmt='hex')
    assert 'AA' in hex_text.upper()


# ---- other formats ----------------------------------------------------------------------------

def test_the_listing_generator_applies_listing_annotations(tmp_path):
    formats = {'with_listing': {'template': '{code}\n', 'sections': {'code': {'generator': 'listing'}}}}
    source = 'start:\n    ld a, b, c\n#annotate listing hide\nscratch:\n    .byte 1\n'
    listing, _ = _listing(tmp_path, source, fmt='with_listing', output_formats=formats)
    assert 'scratch' not in listing and 'start:' in listing


def test_listing_annotation_without_arguments_changes_nothing(tmp_path):
    source = 'start:\n    ld a, b, c\ntable:\n    .byte 1, 2, 3, 4, 5, 6, 7, 8\n'
    plain, _ = _listing(tmp_path, source)
    annotated, _ = _listing(tmp_path, source.replace('table:', '#annotate listing\ntable:'))
    # Only the #annotate line itself is added.
    assert [row for row in _instructions(annotated) if row != '#annotate listing'] == _instructions(plain)
    assert '\f' not in annotated and 'more byte' not in annotated


def test_two_listing_annotations_on_one_symbol(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        _listing(tmp_path, '#annotate listing hide\n#annotate listing collapse\nt: .byte 1\n')
    assert "symbol 't' already has an annotation in the 'listing' namespace" in str(exc_info.value)
