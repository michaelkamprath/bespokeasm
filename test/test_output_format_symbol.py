"""The ``__OUTPUT_FORMAT__`` preprocessor symbol: the selected output format, or 0 when none is."""
import contextlib
import importlib.resources as pkg_resources
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope

from test import config_files

# The Minimal 64x4 copy, whose xmin formats define the XMIN_USER_CODE zone.
CONFIG = str(pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml'))

# The last byte says which branch was assembled.
WHICH_FORMAT = (
    '#if __OUTPUT_FORMAT__ == 0\n.byte 0\n'
    '#elif __OUTPUT_FORMAT__ == listing\n.byte 1\n'
    '#elif __OUTPUT_FORMAT__ == "hex"\n.byte 2\n'
    '#elif __OUTPUT_FORMAT__ == xmin\n.byte 3\n'
    '#elif __OUTPUT_FORMAT__ == xmin_listing\n.byte 4\n'
    '#else\n.byte 9\n#endif\n'
)


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assemble(tmp_path, source, pretty_print=True, fmt='listing', explicit=True, warnings_as_errors=False):
    """The binary's bytes and the diagnostics of assembling ``source``."""
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    (tmp_path / 'main.asm').write_text(source)
    assembler = Assembler(
        str(tmp_path / 'main.asm'), CONFIG, True, str(tmp_path / 'out.bin'), 0, None, 0,
        pretty_print, fmt, str(tmp_path / 'out.txt'), 0, [], [],
        warnings_as_errors=warnings_as_errors, pretty_print_format_explicit=explicit,
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return list((tmp_path / 'out.bin').read_bytes()), assembler._diagnostic_reporter.diagnostics


def _error(tmp_path, source, **options) -> str:
    with pytest.raises(SystemExit) as exc_info:
        _assemble(tmp_path, source, **options)
    return str(exc_info.value)


def _warnings(diagnostics) -> list[str]:
    return [d.message for d in diagnostics if d.level == 'warning']


@pytest.mark.parametrize(('pretty_print', 'fmt', 'explicit', 'branch'), [
    (False, 'listing', False, 0),       # no -p: no format is selected
    (False, 'xmin', True, 0),           # -t without -p selects none either
    (True, 'listing', False, 1),        # -p alone: the default format
    (True, 'LISTING', True, 1),         # a built-in name as the format spells it
    (True, 'hex', True, 2),             # a quoted name
    (True, 'xmin', True, 3),
    (True, 'xmin_listing', True, 4),
])
def test_the_symbol_names_the_selected_format(tmp_path, pretty_print, fmt, explicit, branch):
    found, _ = _assemble(tmp_path, WHICH_FORMAT, pretty_print=pretty_print, fmt=fmt, explicit=explicit)
    assert found[-1] == branch


def test_source_uses_a_format_zone_only_when_that_format_is_selected(tmp_path):
    source = (
        '#if __OUTPUT_FORMAT__ == xmin\n.memzone XMIN_USER_CODE\n'
        '#else\n.org $0200\n#endif\n'
        '.byte $aa\n'
    )
    as_xmin, _ = _assemble(tmp_path, source, fmt='xmin')
    as_binary, _ = _assemble(tmp_path, source, pretty_print=False)
    assert len(as_xmin) == 0x0101 and as_xmin[-1] == 0xaa        # XMIN_USER_CODE starts at 0x0100
    assert len(as_binary) == 0x0201 and as_binary[-1] == 0xaa


@pytest.mark.parametrize(('pretty_print', 'expected'), [(True, [1, 3]), (False, [1, 2])])
def test_the_symbol_is_always_defined_and_alone_tests_whether_a_format_is_selected(
    tmp_path, pretty_print, expected,
):
    source = (
        '#ifdef __OUTPUT_FORMAT__\n.byte 1\n#endif\n'
        '#if __OUTPUT_FORMAT__\n.byte 3\n#else\n.byte 2\n#endif\n'
    )
    found, _ = _assemble(tmp_path, source, pretty_print=pretty_print)
    assert found == expected


def test_a_name_that_is_not_a_format_is_one_warning(tmp_path):
    source = '#if __OUTPUT_FORMAT__ == xmn\n.byte 1\n#endif\n#if __OUTPUT_FORMAT__ != LISTING\n.byte 2\n#endif\n'
    found, diagnostics = _assemble(tmp_path, source)
    assert found == [2]
    assert _warnings(diagnostics) == [
        '"xmn" is not an output format of this instruction set; '
        'its formats are: listing, hex, intel_hex, symbols, xmin, xmin_listing',
        '"LISTING" is not an output format of this instruction set; '
        'its formats are: listing, hex, intel_hex, symbols, xmin, xmin_listing',
    ]


def test_known_names_and_zero_are_not_warned_about(tmp_path):
    _, diagnostics = _assemble(tmp_path, WHICH_FORMAT + '#if __OUTPUT_FORMAT__ != intel_hex\n#endif\n')
    assert _warnings(diagnostics) == []


def test_the_warning_can_be_an_error(tmp_path):
    assert '"xmn" is not an output format' in _error(
        tmp_path, '#if __OUTPUT_FORMAT__ == xmn\n#endif\n', warnings_as_errors=True,
    )


@pytest.mark.parametrize(('pretty_print', 'fmt', 'expected'), [
    (True, 'listing', 'output format requirement not met: __OUTPUT_FORMAT__ == xmin (the selected format is listing)'),
    (False, 'listing', 'output format requirement not met: __OUTPUT_FORMAT__ == xmin (no output format is selected)'),
])
def test_require_names_the_selected_format(tmp_path, pretty_print, fmt, expected):
    assert expected in _error(tmp_path, '#require __OUTPUT_FORMAT__ == xmin\n', pretty_print=pretty_print, fmt=fmt)


def test_require_is_met_by_the_selected_format(tmp_path):
    found, _ = _assemble(tmp_path, '#require __OUTPUT_FORMAT__ == xmin\n.byte 7\n', fmt='xmin')
    assert found == [7]


def test_the_symbol_takes_one_comparison(tmp_path):
    assert 'Mixed expressions' in _error(tmp_path, '#if __OUTPUT_FORMAT__ == xmin || 1\n#endif\n')


def test_the_symbol_is_substituted_in_strings_like_the_other_built_in_symbols(tmp_path):
    found, _ = _assemble(tmp_path, '.cstr "__OUTPUT_FORMAT__"\n', fmt='xmin')
    assert found == list(b'xmin\0')
