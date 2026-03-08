import importlib.util
import pathlib as pl
import re
import sys
import tempfile
import types

from bespokeasm.utilities import PATTERN_ALLOWED_LABELS


def _load_sublime_hover_module():
    sys.modules.setdefault('sublime', types.SimpleNamespace())
    sys.modules.setdefault('sublime_plugin', types.SimpleNamespace(EventListener=object))
    repo_root = pl.Path(__file__).resolve().parents[1]
    module_path = repo_root / 'src' / 'bespokeasm' / 'configgen' / 'sublime' / 'resources' / 'bespokeasm_hover.py'
    spec = importlib.util.spec_from_file_location('bespokeasm_hover', str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _install_label_patterns(hover):
    pattern = PATTERN_ALLOWED_LABELS.pattern
    if pattern.startswith('^'):
        pattern = pattern[1:]
    if pattern.endswith('$'):
        pattern = pattern[:-1]
    hover.LABEL_DEFINITION_PATTERN = re.compile(rf'^\s*(?P<name>{pattern})\s*:')
    hover.OPERAND_LABEL_DEFINITION_PATTERN = re.compile(rf'@(?P<name>{pattern}):\s*')
    hover.CONSTANT_DEFINITION_PATTERN = re.compile(rf'^\s*(?P<name>{pattern})\s*(?:=|\bEQU\b)')
    hover.WORD_PATTERN = re.compile(rf'(?:{pattern})', re.IGNORECASE)


def test_sublime_mnemonic_hover_table_renders_div_table():
    hover = _load_sublime_hover_module()
    markdown = (
        '### `LDA` : Load A immediate\n\n'
        '| Operand | Type | Value | Description |\n'
        '| --- | --- | --- | --- |\n'
        '| `zp_addr` | address | numeric | 8-bit value |\n'
    )

    html = hover._markdown_to_minihtml(markdown, {})

    assert '<div style="font-family: monospace;">' in html
    assert 'font-weight:500' in html
    assert 'border-right:2px solid' in html
    assert '&nbsp;' in html
    assert '<code' in html
    assert 'zp_addr' in html


def test_sublime_hover_wraps_only_for_description_overflow():
    hover = _load_sublime_hover_module()
    markdown = (
        '| Operand | Type | Description |\n'
        '| --- | --- | --- |\n'
        '| `op` | register | short |\n'
        '| `op2` | register | this description is intentionally long and should wrap |\n'
    )

    html = hover._markdown_to_minihtml(markdown, {})

    assert '<div style="font-family: monospace;">' in html
    assert 'description' in html.lower()
    assert '&nbsp;' in html


def test_sublime_collect_includes_transitive():
    hover = _load_sublime_hover_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = pl.Path(temp_dir)
        main_path = base_dir / 'main.asm'
        first_path = base_dir / 'first.asm'
        second_path = base_dir / 'second.asm'
        unrelated_path = base_dir / 'unrelated.asm'

        main_path.write_text('#include "first.asm"\n', encoding='utf-8')
        first_path.write_text('#include "second.asm"\nfirst:\n', encoding='utf-8')
        second_path.write_text('second:\n', encoding='utf-8')
        unrelated_path.write_text('unrelated:\n', encoding='utf-8')

        lines = main_path.read_text(encoding='utf-8').splitlines()
        entries = hover._collect_included_files(lines, str(base_dir))
        paths = {pl.Path(entry['path']).name for entry in entries}

        assert 'first.asm' in paths
        assert 'second.asm' in paths
        assert 'unrelated.asm' not in paths


def test_sublime_predefined_constant_heading_uses_compiler_label_color():
    hover = _load_sublime_hover_module()
    markdown = '### `_Start` : Predefined Constant'
    html = hover._markdown_to_minihtml(markdown, {'compiler_label': '#12AB34', 'instruction': '#445566'})
    assert '<code style="color:#12AB34;">_Start</code>' in html


def test_sublime_definition_hover_uses_usage_colors():
    hover = _load_sublime_hover_module()
    location = {'line': 4, 'col': 2, 'path': '/tmp/example.asm'}
    html = hover._build_definition_hover('target', location, '/tmp/current.asm', token_color='#123456')
    assert '<code style="color:#123456;">target</code>' in html
    assert 'Go to definition' in html


def test_sublime_hover_adds_bottom_padding_wrapper():
    hover = _load_sublime_hover_module()
    wrapped = hover._with_hover_padding('<p>content</p>')
    assert 'padding:0 0 8px 0' in wrapped
    assert '<p>content</p>' in wrapped


def test_sublime_label_definition_map_detects_operand_labels():
    hover = _load_sublime_hover_module()
    _install_label_patterns(hover)
    entries = [{
        'path': '/tmp/main.asm',
        'lines': [
            'entry:',
            'mix @first:$1111, [@second: $2222]',
            'text ".skip: here" ; @ignore: nope',
        ],
    }]
    defs = hover._build_definition_map(entries, 'label')
    assert defs['entry']['line'] == 0
    assert defs['first']['line'] == 1
    assert defs['second']['line'] == 1
    assert 'skip' not in defs
    assert 'ignore' not in defs


def test_sublime_is_definition_at_point_handles_operand_labels():
    hover = _load_sublime_hover_module()
    _install_label_patterns(hover)
    line_text = 'mix @first:$1111, [@second: $2222]'

    class _Region:
        def __init__(self, begin, end):
            self._begin = begin
            self._end = end

        def begin(self):
            return self._begin

        def end(self):
            return self._end

    class _View:
        def line(self, _point):
            return _Region(0, len(line_text))

        def substr(self, _region):
            return line_text

    view = _View()
    first_point = line_text.index('first')
    second_point = line_text.index('second')
    assert hover._is_definition_at_point(view, first_point, 'first', hover.LABEL_DEFINITION_PATTERN)
    assert hover._is_definition_at_point(view, second_point, 'second', hover.LABEL_DEFINITION_PATTERN)
    assert not hover._is_definition_at_point(view, second_point, 'first', hover.LABEL_DEFINITION_PATTERN)
