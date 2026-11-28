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
from test.isa_configs import json_config_copy

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
    (
        '#verbatim script extra\nx\n#endverbatim\n',
        "line 1 - annotation 'script' has no #verbatim part 'extra'; it declares no parts",
    ),
    (
        '#verbatim script a b\nx\n#endverbatim\n',
        'the #verbatim line takes an annotation namespace and an optional part, such as "#verbatim xmin" or '
        '"#verbatim xmin header", not "script a b"',
    ),
    ('ld a, b, c\n#verbatim script\nx\n', 'line 2 - #verbatim block started on line 2 has no #endverbatim'),
    ('ld a, b, c\n#endverbatim\n', 'line 2 - #endverbatim without a #verbatim block'),
    ('#verbatim script\nx\n#endverbatim now\n', 'line 3 - #endverbatim takes no arguments'),
])
def test_source_errors(tmp_path, source, expected):
    assert expected in _error(tmp_path, source)


def test_unterminated_block_is_an_error_even_when_excluded(tmp_path):
    message = _error(tmp_path, ANNOTATED + '#if 0\n#verbatim script\n#endif\n')
    assert '#verbatim block started on line 5 has no #endverbatim' in message


def test_verbatim_can_name_a_label(tmp_path):
    """Directives are written with their `#`, so their names aren't reserved."""
    _, stderr, _ = _run(tmp_path, 'verbatim:\n    ld a, b, c\n', _write_config(tmp_path))
    assert 'keyword' not in stderr


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
        'annotations.script.verbatim.documentaton is not a verbatim setting; verbatim takes documentation and parts',
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


# ---- parts ---------------------------------------------------------------------------------------

def _parts_config(tmp_path) -> str:
    """The script namespace with a ``header`` part, placed first by its own section."""
    annotation = copy.deepcopy(SCRIPT_ANNOTATION)
    annotation['arguments']['kind'] = {'type': 'enum', 'values': ['x'], 'default': 'x'}
    annotation['verbatim']['parts'] = {'header': {'documentation': {'description': 'Comments at the top of the file.'}}}
    output_format = copy.deepcopy(SCRIPT_FORMAT)
    output_format['template'] = 'begin\n{?{header}\n\n}{exports}{?\n\n{script}}\n'
    output_format['sections']['header'] = {'generator': 'verbatim', 'namespace': 'script', 'part': 'header'}
    return _write_config(tmp_path, annotations={'script': annotation}, output_formats={'script': output_format})


def test_a_part_is_placed_by_its_own_section(tmp_path):
    source = (
        ANNOTATED
        + '#verbatim script\nfunctions\n#endverbatim\n'
        + '#verbatim script header  ; the file comment\n# top\n#endverbatim\n'
    )
    output, _, _ = _run(tmp_path, source, _parts_config(tmp_path))
    assert output == 'begin\n# top\n\nstart\n\nfunctions\n'


def test_without_the_part_the_optional_group_writes_nothing(tmp_path):
    output, _, _ = _run(tmp_path, ANNOTATED + '#verbatim script\nfunctions\n#endverbatim\n', _parts_config(tmp_path))
    assert output == 'begin\nstart\n\nfunctions\n'


def test_unknown_part_lists_the_parts(tmp_path):
    message = _error(tmp_path, '#verbatim script headr\nx\n#endverbatim\n', _parts_config(tmp_path))
    assert "line 1 - annotation 'script' has no #verbatim part 'headr'; its parts are: header" in message


def test_unknown_part_in_an_excluded_block_is_not_checked(tmp_path):
    output, _, _ = _run(
        tmp_path, ANNOTATED + '#if 0\n#verbatim script headr\nx\n#endverbatim\n#endif\n', _parts_config(tmp_path),
    )
    assert output == 'begin\nstart\n'


def test_symbols_gives_the_part(tmp_path):
    source = ANNOTATED + '#verbatim script header\n# top\n#endverbatim\n'
    output, _, _ = _run(tmp_path, source, _parts_config(tmp_path), fmt='symbols')
    assert json.loads(output)['verbatim'][0]['part'] == 'header'


@pytest.mark.parametrize(('change', 'expected'), [
    (
        lambda config: config['output_formats']['script']['sections']['header'].update(part='footer'),
        "output_formats.script.sections.header.part names 'footer', which is not a #verbatim part of annotation "
        "'script'; its parts are: header",
    ),
    (
        lambda config: config['annotations']['script']['verbatim'].update(parts={}),
        'annotations.script.verbatim.parts must be a non-empty mapping of part names',
    ),
    (
        lambda config: config['annotations']['script']['verbatim'].update(parts=['header']),
        'annotations.script.verbatim.parts must be a non-empty mapping of part names',
    ),
    (
        lambda config: config['annotations']['script']['verbatim'].update(parts={'2nd': {}, 'header': {}}),
        'annotations.script.verbatim.parts.2nd is not a part name',
    ),
    (
        lambda config: config['annotations']['script']['verbatim'].update(parts={'header': {'title': 'x'}}),
        'annotations.script.verbatim.parts.header.title is not a part setting; a part takes documentation',
    ),
])
def test_part_config_errors(tmp_path, change, expected):
    path = _parts_config(tmp_path)
    config = json.loads(open(path).read())
    change(config)
    open(path, 'w').write(json.dumps(config))
    assert expected in _error(tmp_path, 'ld a, b, c\n', path, fmt='listing')


def test_generated_docs_list_the_parts(tmp_path):
    model = AssemblerModel(_parts_config(tmp_path), 0, DiagnosticReporter())
    markdown = MarkdownGenerator(DocumentationModel(model)).generate()
    assert (
        'A block can name a part, which an output format places separately:\n\n'
        '- `#verbatim script header`: Comments at the top of the file.'
    ) in markdown


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
    assert json.loads(output)['verbatim'] == [
        {'namespace': 'script', 'part': None, 'file': 'main.asm', 'line': 4, 'text': '  one'},
    ]


def test_generated_docs_say_which_namespaces_accept_blocks(tmp_path):
    model = AssemblerModel(_write_config(tmp_path), 0, DiagnosticReporter())
    assert model.verbatim_namespaces == ['script']
    markdown = MarkdownGenerator(DocumentationModel(model)).generate()
    assert 'Accepts `#verbatim script` text blocks: Script text copied into the script file.' in markdown


def test_xmin_format_writes_the_header_part_after_the_generated_line(tmp_path):
    """The Minimal 64x4 xmin format, from the copied config: a header block, wherever it is in
    the source, comes right after the generated-by line, then a blank line and the declarations."""
    config = json_config_copy(pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml'), tmp_path)
    source = (
        '.memzone XMIN_USER_CODE\n'
        '#annotate xmin kind=addr name=Go\ngo: RTS\n'
        '#verbatim xmin header\n# GoLib\n#\n# Calls go.\n#endverbatim\n'
    )
    output, warnings, _ = _run(tmp_path, source, config, fmt='xmin')
    assert warnings == ''
    lines = output.split('\n')
    assert lines[0].startswith('# main.asm: generated by BespokeASM')
    assert lines[1:7] == ['# GoLib', '#', '# Calls go.', '', 'int Go := 0x0100', '']


def test_xmin_format_writes_blocks_between_the_declarations_and_the_asm_block(tmp_path):
    """The Minimal 64x4 xmin format, from the copied config."""
    config = json_config_copy(pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml'), tmp_path)
    source = (
        '.memzone XMIN_USER_CODE\n'
        '#annotate xmin kind=addr name=Go\ngo: RTS\n'
        '#verbatim xmin\ndef run():\n  call Go\n#endverbatim\n'
    )
    output, warnings, _ = _run(tmp_path, source, config, fmt='xmin')
    assert warnings == ''
    assert '\nint Go := 0x0100\n\ndef run():\n  call Go\n\nasm\n:' in output
