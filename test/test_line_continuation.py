"""Continuing data directives and embedded strings with a trailing ``\\``, and adjacent strings."""
import contextlib
import importlib.resources as pkg_resources
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope

from test import config_files

# The Minimal 64x4 copy: 8-bit words, embedded strings allowed, and the xmin formats.
CONFIG = str(pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml'))


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _run(tmp_path, source: str, fmt: str = 'hex') -> str:
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    (tmp_path / 'main.asm').write_text(source)
    output_path = tmp_path / 'out.txt'
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        Assembler(
            str(tmp_path / 'main.asm'), CONFIG, False, None, 0, None, 0, True, fmt, str(output_path), 0, [], [],
        ).assemble_bytecode()
    return output_path.read_text()


def _bytes(tmp_path, source: str) -> list[int]:
    """The bytes of a hex dump: each row is an address, 16 bytes (`--` past the end), then text."""
    rows = _run(tmp_path, source).splitlines()
    return [int(word, 16) for row in rows for word in row.split('|')[0].split()[1:] if word != '--']


def _error(tmp_path, source: str) -> str:
    with pytest.raises(SystemExit) as exc_info:
        _run(tmp_path, source)
    return str(exc_info.value)


@pytest.mark.parametrize(('continued', 'one_line'), [
    ('message: .cstr "Hello, " \\\n    "world"\n', 'message: .cstr "Hello, world"\n'),
    ('.cstr "a" \\\n  "b" \\\n  "c"   ; the last line can have a comment\n', '.cstr "abc"\n'),
    ('.asciiz "ab" \\\n "cd"\n', '.asciiz "abcd"\n'),
    ('.byte 1, 2, \\\n  3, 4\n', '.byte 1, 2, 3, 4\n'),
    ('.byte "ab", \\\n  0\n', '.byte "ab", 0\n'),
    ('.2byte $1234, \\\n  $5678\n', '.2byte $1234, $5678\n'),
    ('"emb" \\\n  "edded"\n', '"embedded"\n'),
])
def test_a_continued_line_assembles_as_one_line(tmp_path, continued, one_line):
    assert _bytes(tmp_path, continued) == _bytes(tmp_path, one_line)


@pytest.mark.parametrize(('adjacent', 'one_string'), [
    ('.cstr "ab" "cd"\n', '.cstr "abcd"\n'),
    ('.cstr "ab"  "cd" "e"\n', '.cstr "abcde"\n'),
    (".cstr 'ab' 'cd'\n", '.cstr "abcd"\n'),                 # either quote style
    ('.cstr "ab" \'cd\'\n', '.cstr "abcd"\n'),
    ('.byte "ab" "c", 0\n', '.byte "abc", 0\n'),
    ('"ab" "cd"\n', '"abcd"\n'),                              # an embedded string: one terminator
    ('.cstr "\\x41" "1"\n', '.cstr "A1"\n'),                  # escapes apply within each string
    ('.cstr "say \\"hi\\"" "!"\n', '.cstr "say \\"hi\\"!"\n'),
])
def test_adjacent_strings_are_one_string(tmp_path, adjacent, one_string):
    assert _bytes(tmp_path, adjacent) == _bytes(tmp_path, one_string)


# ---- quotes inside strings ------------------------------------------------------------------
# A quote of the string's own kind is escaped (\" or \') to be part of the string. An unescaped one
# ends the string: what follows is an adjacent string, joined to it, or an error.

@pytest.mark.parametrize(('source', 'expected'), [
    # Escaped quotes are characters of the string.
    ('.cstr "ab\\"  \\"cd"\n', b'ab"  "cd\0'),
    ('.byte "ab\\"  \\"cd", 0\n', b'ab"  "cd\0'),
    ('"ab\\"  \\"cd"\n', b'ab"  "cd\0'),                      # an embedded string
    (".cstr 'it\\'s'\n", b"it's\0"),
    ('.cstr "a\\\\" "b"\n', b'a\\b\0'),                       # \\ is a backslash; the quote after it ends the string
    # A quote of the other kind needs no escape.
    ('.cstr "it\'s"\n', b"it's\0"),
    ('.cstr \'say "hi"\'\n', b'say "hi"\0'),
    ('"it\'s"\n', b"it's\0"),
    # An unescaped quote of the string's own kind ends it; a string right after is joined to it.
    ('.cstr "ab" "cd"\n', b'abcd\0'),
    ('.cstr "ab""cd"\n', b'abcd\0'),                           # joined, not an escaped quote
    ('"ab" "cd"\n', b'abcd\0'),                                # one embedded string, one terminator
    # Commas separate .byte values, so these are two strings with no terminator between them.
    ('.byte "ab", "cd"\n', b'abcd'),
])
def test_quotes_inside_strings(tmp_path, source, expected):
    assert _bytes(tmp_path, source) == list(expected)


@pytest.mark.parametrize(('source', 'expected'), [
    # An unescaped quote that leaves text outside any string is an error, not part of the string.
    ('.cstr "ab"cd"\n', 'line 1 - unterminated string in data directive'),
    ('.cstr "ab" cd"\n', 'line 1 - unterminated string in data directive'),
    ('.cstr "abc\n', 'line 1 - unterminated string in data directive'),
    ('"ab"cd"\n', 'line 1 - unknown instruction'),
    ('"abc\n', 'line 1 - unknown instruction'),
    # .cstr takes one string: a comma does not join strings.
    ('.cstr "ab", "cd"\n', 'line 1 - .cstr data directive used with non-string value'),
])
def test_unescaped_quotes_that_do_not_make_a_string_are_errors(tmp_path, source, expected):
    assert expected in _error(tmp_path, source)


def test_continuation_lines_do_not_end_an_annotated_labels_data(tmp_path):
    source = (
        '.memzone XMIN_USER_CODE\n'
        '#annotate xmin kind=var type=char array name=kMsg\n'
        'message:\n'
        '  .byte "Hello, " \\\n'
        '        "world"\n'
        '  .byte "!"\n'
    )
    assert 'char kMsg[13] @ 0x0100' in _run(tmp_path, source, fmt='xmin')


def test_a_continued_line_inside_a_false_if_is_skipped_as_a_whole(tmp_path):
    source = '#if 0\n.cstr "a" \\\n#endif\n#endif\n.byte 7\n'
    assert _bytes(tmp_path, source) == [7]


def test_the_listing_shows_each_physical_line(tmp_path):
    source = 'message: .cstr "ab" \\\n    "cd"   ; done\n.byte 9\n'
    listing = _run(tmp_path, source, fmt='listing')
    rows = [row for row in listing.split('\n') if row.strip()[:1].isdigit()]
    assert '.cstr "ab" \\' in rows[1] and '61 62 63 64 00' in rows[1] and 'done' not in rows[1]
    assert '"cd"' in rows[2] and rows[2].rstrip().endswith('done')
    assert rows[2].split('|')[2].strip() == ''          # no bytes on the continuation row


def test_backslash_inside_a_string_does_not_continue(tmp_path):
    assert 'unterminated string' in _error(tmp_path, '.cstr "abc\\\n.byte 1\n')


def test_an_instruction_does_not_continue(tmp_path):
    """Only #annotate, data directives and embedded strings continue."""
    assert 'line 1' in _error(tmp_path, 'nop \\\nnop\n')


@pytest.mark.parametrize(('source', 'expected'), [
    ('.cstr "a" \\\n\n"b"\n', 'line 1 - .cstr ends with \\ but line 2 is blank'),
    ('.byte 1, \\\n', 'line 1 - .byte ends with \\ but the file ends at line 1'),
    ('"a" \\\n', 'line 1 - the string ends with \\ but the file ends at line 1'),
    ('msg: .CSTR "a" \\\n\n', 'line 1 - .cstr ends with \\ but line 2 is blank'),
])
def test_a_continued_line_needs_a_next_line(tmp_path, source, expected):
    assert expected in _error(tmp_path, source)
