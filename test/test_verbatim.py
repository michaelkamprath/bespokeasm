"""Tests for #verbatim blocks: reading them, the verbatim generator, and where else they appear."""
import contextlib
import copy
import importlib.resources as pkg_resources
import io
import json

import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.docsgen.documentation_model import DocumentationModel
from bespokeasm.docsgen.markdown_generator import MarkdownGenerator
from ruamel.yaml import YAML

from test import config_files

SCRIPT_ANNOTATION = {
    'verbatim': {'documentation': {'description': 'Script text copied into the script file.'}},
    'arguments': {'name': {'type': 'string'}},
}
# A format with the blocks after the exports, in an optional group, as the xmin format does.
SCRIPT_FORMAT = {
    'template': 'begin\n{exports}{?\n\n{script}}\n',
    'sections': {
        'exports': {'generator': 'exports', 'annotation': 'script', 'lines_key': 'kind', 'lines': {'x': '{name}'}},
        'script': {'generator': 'verbatim', 'namespace': 'script'},
    },
}


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _write_config(tmp_path, annotations=None, output_formats=None) -> str:
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    annotation = copy.deepcopy(SCRIPT_ANNOTATION)
    annotation['arguments']['kind'] = {'type': 'enum', 'values': ['x'], 'default': 'x'}
    config['annotations'] = copy.deepcopy(annotations) if annotations is not None else {'script': annotation}
    config['output_formats'] = copy.deepcopy(output_formats) if output_formats is not None else {'script': SCRIPT_FORMAT}
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    return str(path)


def _run(tmp_path, source: str, config_path: str, fmt: str = 'script', files: dict[str, str] | None = None):
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    (tmp_path / 'main.asm').write_text(source)
    for name, text in (files or {}).items():
        (tmp_path / name).write_text(text)
    output_path = tmp_path / 'out.txt'
    stderr = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
        assembler = Assembler(
            str(tmp_path / 'main.asm'), config_path, False, None, 0, None, 0,
            True, fmt, str(output_path), 0, [], [],
        )
        assembler.assemble_bytecode()
    return output_path.read_text(), stderr.getvalue(), assembler


def _error(tmp_path, source: str, config_path: str | None = None, fmt: str = 'script') -> str:
    with pytest.raises(SystemExit) as exc_info:
        _run(tmp_path, source, config_path or _write_config(tmp_path), fmt)
    return str(exc_info.value)


ANNOTATED = '#annotate script\nstart:\n    ld a, b, c\n'


# ---- reading blocks ----------------------------------------------------------------------

def test_block_text_is_copied_exactly(tmp_path):
    source = ANNOTATED + '\n'.join([
        '#verbatim script ; the wrapper',
        '',
        'def go(char x):   ',
        '  ; not a comment, x = $10',
        '',
        '#if NOT_A_DIRECTIVE',
        '\tcall start',
        '',
        '#endverbatim ; done',
        '    ld a, b, c',
    ]) + '\n'
    output, warnings, _ = _run(tmp_path, source, _write_config(tmp_path))
    assert warnings == ''
    # Trailing spaces and the blank lines at the block's ends are removed; the rest is as written.
    assert output == 'begin\nstart\n\ndef go(char x):\n  ; not a comment, x = $10\n\n#if NOT_A_DIRECTIVE\n\tcall start\n'


def test_blocks_in_source_order_across_includes(tmp_path):
    source = ANNOTATED + '#verbatim script\none\n#endverbatim\n#include "lib.asm"\n#verbatim script\nthree\n#endverbatim\n'
    lib = '#verbatim script\ntwo\n#endverbatim\n'
    output, _, assembler = _run(tmp_path, source, _write_config(tmp_path), files={'lib.asm': lib})
    assert output == 'begin\nstart\n\none\n\ntwo\n\nthree\n'
    assert [block.line_id.filename.rsplit('/', 1)[-1] for block in assembler.export_model.verbatim_blocks] == [
        'main.asm', 'lib.asm', 'main.asm',
    ]


@pytest.mark.parametrize(('condition', 'expected'), [
    ('1', 'begin\nstart\n\nkept\n#else\n#endif\n'),
    ('0', 'begin\nstart\n'),
])
def test_conditional_compilation_applies_to_the_whole_block(tmp_path, condition, expected):
    # The #else and #endif inside the block are text, not preprocessor lines.
    source = ANNOTATED + f'#if {condition}\n#verbatim script\nkept\n#else\n#endif\n#endverbatim\n#endif\n'
    output, _, _ = _run(tmp_path, source, _write_config(tmp_path))
    assert output == expected


def test_format_without_blocks_gets_no_extra_lines(tmp_path):
    output, _, _ = _run(tmp_path, ANNOTATED, _write_config(tmp_path))
    assert output == 'begin\nstart\n'


def test_an_empty_block_writes_nothing(tmp_path):
    source = ANNOTATED + '#verbatim script\n\n   \n#endverbatim\n#verbatim script\nonly\n#endverbatim\n'
    output, _, _ = _run(tmp_path, source, _write_config(tmp_path))
    assert output == 'begin\nstart\n\nonly\n'


def test_separator_option(tmp_path):
    output_format = copy.deepcopy(SCRIPT_FORMAT)
    output_format['sections']['script']['separator'] = '\n# ----\n'
    config = _write_config(tmp_path, output_formats={'script': output_format})
    source = ANNOTATED + '#verbatim script\none\n#endverbatim\n#verbatim script\ntwo\n#endverbatim\n'
    output, _, _ = _run(tmp_path, source, config)
    assert output == 'begin\nstart\n\none\n# ----\ntwo\n'


def test_block_between_annotate_and_definition_is_an_error(tmp_path):
    message = _error(tmp_path, '#annotate script\n#verbatim script\nx\n#endverbatim\nstart:\n')
    assert '#annotate must be directly above a label or constant definition, but line 2 is a #verbatim block' in message


@pytest.mark.parametrize(('source', 'expected'), [
    ('#verbatim\nx\n#endverbatim\n', 'line 1 - #verbatim requires an annotation namespace, for example "#verbatim script"'),
    (
        '#verbatim scrpt\nx\n#endverbatim\n',
        "line 1 - annotation 'scrpt' does not accept #verbatim blocks; namespaces that do: script",
    ),
    (
        '#verbatim listing\nx\n#endverbatim\n',
        "annotation 'listing' does not accept #verbatim blocks; namespaces that do: script",
    ),
    ('#verbatim script extra\nx\n#endverbatim\n', '#verbatim takes one annotation namespace, such as "#verbatim xmin"'),
    ('ld a, b, c\n#verbatim script\nx\n', 'line 2 - #verbatim block started on line 2 has no #endverbatim'),
    ('ld a, b, c\n#endverbatim\n', 'line 2 - #endverbatim without a #verbatim block'),
    ('#verbatim script\nx\n#endverbatim now\n', 'line 3 - #endverbatim takes no arguments'),
])
def test_source_errors(tmp_path, source, expected):
    assert expected in _error(tmp_path, source)


def test_unterminated_block_is_an_error_even_when_excluded(tmp_path):
    message = _error(tmp_path, ANNOTATED + '#if 0\n#verbatim script\n#endif\n')
    assert '#verbatim block started on line 5 has no #endverbatim' in message


def test_verbatim_is_a_reserved_word(tmp_path):
    assert '"verbatim" is an assembler keyword' in _error(tmp_path, 'verbatim:\n    ld a, b, c\n')


# ---- configuration ---------------------------------------------------------------------------

@pytest.mark.parametrize(('change', 'expected'), [
    (
        lambda config: config['annotations']['script'].pop('verbatim'),
        "output_formats.script.sections.script.namespace names 'script', which does not accept #verbatim blocks; "
        'no annotation namespace of this configuration does',
    ),
    (
        lambda config: config['output_formats']['script']['sections']['script'].update(namespace='listing'),
        "namespace names 'listing', which does not accept #verbatim blocks; namespaces that do: script",
    ),
    (
        lambda config: config['output_formats']['script']['sections']['script'].pop('namespace'),
        "output_formats.script.sections.script uses generator 'verbatim', which requires option 'namespace'",
    ),
    (
        lambda config: config['output_formats']['script']['sections']['script'].update(separator=3),
        'output_formats.script.sections.script.separator must be a string',
    ),
    (
        lambda config: config['annotations']['script'].update(verbatim='yes'),
        'annotations.script.verbatim must be a mapping',
    ),
    (
        lambda config: config['annotations']['script'].update(verbatim={'documentaton': {}}),
        'annotations.script.verbatim.documentaton is not a verbatim setting; verbatim takes documentation',
    ),
    (
        lambda config: config['annotations']['script'].update(verbatim={'documentation': {'title': 'x'}}),
        'annotations.script.verbatim.documentation.title is not a documentation setting',
    ),
])
def test_config_errors(tmp_path, change, expected):
    path = _write_config(tmp_path)
    config = json.loads(open(path).read())
    change(config)
    open(path, 'w').write(json.dumps(config))
    assert expected in _error(tmp_path, 'ld a, b, c\n', path, fmt='listing')


def test_namespace_with_only_verbatim(tmp_path):
    """A namespace that only carries text needs no arguments."""
    output_format = {'template': '{script}\n', 'sections': {'script': {'generator': 'verbatim', 'namespace': 'text'}}}
    config = _write_config(tmp_path, annotations={'text': {'verbatim': {}}}, output_formats={'text': output_format})
    output, _, _ = _run(tmp_path, 'ld a, b, c\n#verbatim text\nhello\n#endverbatim\n', config, fmt='text')
    assert output == 'hello\n'


# ---- elsewhere ---------------------------------------------------------------------------------

def test_listing_shows_the_block_lines(tmp_path):
    source = ANNOTATED + '#verbatim script\n  def go():\n#endverbatim\n    ld a, b, c\n'
    output, _, _ = _run(tmp_path, source, _write_config(tmp_path), fmt='listing')
    rows = {row.split('|')[0].strip(): row for row in output.split('\n') if row.strip()[:1].isdigit()}
    assert set(rows) == {'1', '2', '3', '4', '5', '6', '7'}
    assert 'def go():' in rows['5'] and '#endverbatim' in rows['6']
    assert all(rows[number].split('|')[2].strip() == '' for number in ('4', '5', '6'))


def test_listing_hide_does_not_hide_a_block(tmp_path):
    source = (
        '#annotate listing hide\nstart:\n    ld a, b, c\n'
        '#verbatim script\ntext\n#endverbatim\n    ld a, b, c\nnext:\n    ld a, b, c\n'
    )
    output, _, _ = _run(tmp_path, source, _write_config(tmp_path), fmt='listing')
    numbers = [row.split('|')[0].strip() for row in output.split('\n') if row.strip()[:1].isdigit()]
    # The label's own lines (1-3 and 7) are hidden; the block's (4-6) are not.
    assert numbers == ['4', '5', '6', '8', '9']


def test_symbols_lists_the_blocks(tmp_path):
    source = ANNOTATED + '#verbatim script\n  one\n#endverbatim\n#if 0\n#verbatim script\nskipped\n#endverbatim\n#endif\n'
    output, _, _ = _run(tmp_path, source, _write_config(tmp_path), fmt='symbols')
    assert json.loads(output)['verbatim'] == [{'namespace': 'script', 'file': 'main.asm', 'line': 4, 'text': '  one'}]


def test_generated_docs_say_which_namespaces_accept_blocks(tmp_path):
    model = AssemblerModel(_write_config(tmp_path), 0, DiagnosticReporter())
    assert model.verbatim_namespaces == ['script']
    markdown = MarkdownGenerator(DocumentationModel(model)).generate()
    assert 'Accepts `#verbatim script` text blocks: Script text copied into the script file.' in markdown


def test_xmin_format_writes_blocks_after_the_declarations(tmp_path):
    """The Minimal 64x4 xmin format, from the copied config."""
    config = str(pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml'))
    source = (
        '.memzone XMIN_USER_CODE\n'
        '#annotate xmin kind=addr name=Go\ngo: RTS\n'
        '#verbatim xmin\ndef run():\n  call Go\n#endverbatim\n'
    )
    output, warnings, _ = _run(tmp_path, source, config, fmt='xmin')
    assert warnings == ''
    assert output.endswith('\nint Go := 0x0100\n\ndef run():\n  call Go\n')
