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
    hover.CONSTANT_VALUE_PATTERN = re.compile(rf'^\s*{pattern}\s*(?:=|\bEQU\b)\s*(?P<value>.+?)(?:\s*;.*)?$')
    hover.WORD_PATTERN = re.compile(rf'(?:{pattern})', re.IGNORECASE)
    hover.REGISTER_PATTERN = re.compile(r'(?i)(?:\ba\b|\bb\b|\bsp\b)')


def _make_view_state(hover, lines, current_path='/tmp/test.asm'):
    """Build a view state dict from lines, matching _get_view_state output."""
    entries = [{'path': current_path, 'lines': lines}]
    label_map = hover._build_definition_map(entries, 'label')
    constant_map = hover._build_definition_map(entries, 'constant')
    return {
        'change_count': 0,
        'lines': lines,
        'label_map': label_map,
        'constant_map': constant_map,
        'current_path': current_path,
        'included_entries': [],
    }


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


# --- Mock helpers for hover point tests ---


class _MockRegion:
    def __init__(self, begin, end):
        self._begin = begin
        self._end = end

    def begin(self):
        return self._begin

    def end(self):
        return self._end


class _MockLineView:
    def __init__(self, text):
        self._text = text

    def line(self, _point):
        return _MockRegion(0, len(self._text))

    def substr(self, _region):
        return self._text


# --- Directive hover tests ---


def test_sublime_directive_detection_at_line_start():
    hover = _load_sublime_hover_module()

    # Preprocessor directive at line start
    view = _MockLineView('#include "file.asm"')
    assert hover._get_directive_at_point(view, 0) == 'include'
    assert hover._get_directive_at_point(view, 1) == 'include'
    assert hover._get_directive_at_point(view, 7) == 'include'
    # Past the directive name
    assert hover._get_directive_at_point(view, 9) is None

    # Compiler directive at line start
    view = _MockLineView('.org $1000')
    assert hover._get_directive_at_point(view, 0) == 'org'
    assert hover._get_directive_at_point(view, 3) == 'org'
    assert hover._get_directive_at_point(view, 4) is None


def test_sublime_directive_detection_after_label():
    hover = _load_sublime_hover_module()

    # Data type directive after a label
    line = 'my_var:  .byte 0xff'
    view = _MockLineView(line)
    dot_pos = line.index('.byte')
    assert hover._get_directive_at_point(view, dot_pos) == 'byte'
    assert hover._get_directive_at_point(view, dot_pos + 1) == 'byte'
    assert hover._get_directive_at_point(view, dot_pos + 4) == 'byte'

    # .2byte after label
    line2 = 'ptr:  .2byte 0xffff'
    view2 = _MockLineView(line2)
    dot_pos2 = line2.index('.2byte')
    assert hover._get_directive_at_point(view2, dot_pos2) == '2byte'


def test_sublime_directive_not_detected_in_string():
    hover = _load_sublime_hover_module()

    line = '.byte ".org should not match"'
    view = _MockLineView(line)
    org_pos = line.index('.org')
    assert hover._get_directive_at_point(view, org_pos) is None
    # But .byte at the start should match
    assert hover._get_directive_at_point(view, 0) == 'byte'


# --- Register hover tests ---


def test_sublime_register_detection():
    hover = _load_sublime_hover_module()
    _install_label_patterns(hover)

    line = '  lda a, b'
    view = _MockLineView(line)
    a_pos = line.index(' a,') + 1  # position of 'a'
    b_pos = line.index(' b') + 1
    assert hover._get_register_at_point(view, a_pos) == 'a'
    assert hover._get_register_at_point(view, b_pos) == 'b'
    # Position on the instruction, not a register
    assert hover._get_register_at_point(view, 2) is None


# --- Constant value preview tests ---


def test_sublime_extract_constant_value():
    hover = _load_sublime_hover_module()
    _install_label_patterns(hover)
    lines = [
        'MY_CONST = $FF',
        'OTHER EQU 42  ; a comment',
        'start:',
        '  lda MY_CONST',
    ]
    state = _make_view_state(hover, lines)
    assert hover._extract_constant_value(state, 'MY_CONST') == '$FF'
    assert hover._extract_constant_value(state, 'OTHER') == '42'
    assert hover._extract_constant_value(state, 'NONEXISTENT') is None


def test_sublime_constant_hover_includes_value():
    hover = _load_sublime_hover_module()
    location = {'line': 0, 'col': 0, 'path': '/tmp/test.asm'}
    html = hover._build_constant_hover(
        'MY_CONST', location, '/tmp/test.asm',
        value_text='$FF', token_color='#aabbcc', number_color='#112233'
    )
    assert '$FF' in html
    assert '#112233' in html
    assert '#aabbcc' in html
    assert 'Go to definition' in html


def test_sublime_constant_hover_without_value():
    hover = _load_sublime_hover_module()
    location = {'line': 5, 'col': 0, 'path': '/tmp/test.asm'}
    html = hover._build_constant_hover(
        'FOO', location, '/tmp/test.asm',
        value_text=None, token_color='#aabbcc'
    )
    assert 'FOO' in html
    assert '= ' not in html
    assert 'Defined at line 6' in html


# --- Label definition self-hover tests ---


def test_sublime_find_references():
    hover = _load_sublime_hover_module()
    _install_label_patterns(hover)
    lines = [
        'start:',
        '  jmp start',
        '  beq start',
        'other:',
        '  nop',
    ]
    state = _make_view_state(hover, lines)
    refs = hover._find_references('start', state)
    assert len(refs) == 2
    assert refs[0]['line'] == 1
    assert refs[1]['line'] == 2


def test_sublime_find_references_no_usages():
    hover = _load_sublime_hover_module()
    _install_label_patterns(hover)
    lines = [
        'unused_label:',
        '  nop',
    ]
    state = _make_view_state(hover, lines)
    refs = hover._find_references('unused_label', state)
    assert len(refs) == 0


def test_sublime_label_self_hover_with_references():
    hover = _load_sublime_hover_module()
    refs = [
        {'line': 5, 'col': 4, 'path': '/tmp/test.asm'},
        {'line': 10, 'col': 6, 'path': '/tmp/test.asm'},
    ]
    html = hover._build_label_definition_self_hover(
        'my_label', refs, '/tmp/test.asm', token_color='#aabbcc'
    )
    assert '2 references' in html
    assert 'line 6' in html
    assert 'line 11' in html
    assert 'href=' in html


def test_sublime_label_self_hover_no_references():
    hover = _load_sublime_hover_module()
    html = hover._build_label_definition_self_hover(
        'unused', [], '/tmp/test.asm', token_color='#aabbcc'
    )
    assert 'No references found' in html


def test_sublime_label_self_hover_cross_file():
    hover = _load_sublime_hover_module()
    refs = [
        {'line': 3, 'col': 2, 'path': '/tmp/other.asm'},
    ]
    html = hover._build_label_definition_self_hover(
        'ext_label', refs, '/tmp/test.asm', token_color='#aabbcc'
    )
    assert '1 reference' in html
    assert 'other.asm' in html


# --- Directive heading color tests ---


def test_sublime_directive_heading_uses_correct_colors():
    hover = _load_sublime_hover_module()
    colors = {
        'preprocessor': '#PP00PP',
        'directive': '#DD00DD',
        'data_type': '#DA7A00',
        'punctuation_preprocessor': '#PPCC00',
        'instruction': '#FF8800',
    }

    # Preprocessor: # should have punctuation_preprocessor color, name should have preprocessor color
    md = '### `#include` : Include Source File'
    html = hover._markdown_to_minihtml(
        md, colors, heading_color='#PP00PP', heading_prefix_color='#PPCC00'
    )
    assert '#PPCC00' in html  # prefix color for #
    assert '#PP00PP' in html  # name color for include

    # Compiler directive: no prefix split (. is part of directive)
    md2 = '### `.org` : Set Origin Address'
    html2 = hover._markdown_to_minihtml(
        md2, colors, heading_color='#DD00DD', heading_prefix_color=None
    )
    assert '#DD00DD' in html2
    assert '.org' in html2


# --- Code block directive coloring tests ---


def test_sublime_code_block_colors_preprocessor_directive():
    hover = _load_sublime_hover_module()
    colors = {
        'instruction': '#FF8800',
        'parameter': '#AABBCC',
        'number': '#FFFF00',
        'punctuation': '#EE8800',
        'preprocessor': '#CC80FF',
        'punctuation_preprocessor': '#ED80A2',
        'directive': '#CC80FF',
        'data_type': '#D6ADFF',
    }
    lines = ['#create_memzone NAME $1000 $3FFF']
    html = hover._render_code_block(lines, colors)
    # The # should use punctuation_preprocessor color
    assert '#ED80A2' in html
    # The directive name should use preprocessor color, not instruction
    assert '#CC80FF' in html
    # Should NOT use instruction color for the directive name
    # (instruction color would only appear if detection fails)


def test_sublime_code_block_colors_data_type_directive():
    hover = _load_sublime_hover_module()
    colors = {
        'instruction': '#FF8800',
        'parameter': '#AABBCC',
        'number': '#FFFF00',
        'punctuation': '#EE8800',
        'preprocessor': '#CC80FF',
        'punctuation_preprocessor': '#ED80A2',
        'directive': '#CC80FF',
        'data_type': '#D6ADFF',
    }
    lines = ['.byte $FF']
    html = hover._render_code_block(lines, colors)
    # Both . and byte should use data_type color
    assert '#D6ADFF' in html
    # The value should use number color
    assert '#FFFF00' in html


def test_sublime_code_block_colors_numeric_prefix_directive():
    """Directives like .2byte should be colored as a single unit, not split."""
    hover = _load_sublime_hover_module()
    colors = {
        'instruction': '#FF8800',
        'parameter': '#AABBCC',
        'number': '#FFFF00',
        'punctuation': '#EE8800',
        'preprocessor': '#CC80FF',
        'punctuation_preprocessor': '#ED80A2',
        'directive': '#CC80FF',
        'data_type': '#D6ADFF',
    }
    lines = ['.2byte 0xFFFF']
    html = hover._render_code_block(lines, colors)
    # The . and 2byte should both use data_type color
    assert html.count('#D6ADFF') >= 2  # prefix and name
    # The "2" should NOT use number color — it's part of the directive name
    # Find the span containing "2byte" and verify its color
    assert '>2byte</span>' in html
    assert 'color:#D6ADFF;">2byte</span>' in html
