import html
import json
import os
import re
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlparse

import sublime
import sublime_plugin


WORD_PATTERN = re.compile(r'(?:##MNEMONIC_PATTERN##|##LABEL_PATTERN##)', re.IGNORECASE)
LABEL_DEFINITION_PATTERN = re.compile(r'^\s*(?P<name>##LABEL_PATTERN##)\s*:')
OPERAND_LABEL_DEFINITION_PATTERN = re.compile(r'@(?P<name>##LABEL_PATTERN##):\s*')
CONSTANT_DEFINITION_PATTERN = re.compile(r'^\s*(?P<name>##LABEL_PATTERN##)\s*(?:=|\bEQU\b)')
CONSTANT_VALUE_PATTERN = re.compile(r'^\s*##LABEL_PATTERN##\s*(?:=|\bEQU\b)\s*(?P<value>.+?)(?:\s*;.*)?$')
COMPILER_DIRECTIVE_PATTERN = re.compile(r'\.(\w+)\b', re.IGNORECASE)
PREPROCESSOR_DIRECTIVE_PATTERN = re.compile(r'#(\S+)\b', re.IGNORECASE)
REGISTER_PATTERN = re.compile(r'(?i)(?:##REGISTERS##)')
INCLUDE_PATTERN = re.compile(r'^\s*#include\s+(?:"([^"]+)"|<([^>]+)>|(\S+))', re.IGNORECASE)
PACKAGE_NAME = '##PACKAGE_NAME##'

LABEL_USAGE_SCOPE = 'variable.other.label.usage'
CONSTANT_USAGE_SCOPE = 'variable.other.constant.usage'
TABLE_CELL_BOUNDARY_PIXELS = 2
TABLE_ROW_VERT_MARGIN_PIXELS = 1
TABLE_MAX_COLUMN_CHARS = 32
TABLE_MAX_DESCRIPTION_CHARS = 48
TABLE_MIN_COLUMN_CHARS = 6
TABLE_MAX_TOTAL_CHARS = 120
TABLE_CELL_LEFT_PAD = 1
TABLE_CELL_RIGHT_PAD = 2
HOVER_EXTRA_BOTTOM_PADDING_PIXELS = 8
DEFAULT_HOVER_COLORS = {
    'instruction': '##HOVER_COLOR_INSTRUCTION##',
    'compiler_label': '##HOVER_COLOR_COMPILER_LABEL##',
    'label_usage': '##HOVER_COLOR_LABEL_USAGE##',
    'constant_usage': '##HOVER_COLOR_CONSTANT_USAGE##',
    'parameter': '##HOVER_COLOR_PARAMETER##',
    'number': '##HOVER_COLOR_NUMBER##',
    'punctuation': '##HOVER_COLOR_PUNCTUATION##',
    'inline_code': '##HOVER_COLOR_INLINE_CODE##',
    'table_header': '##HOVER_COLOR_TABLE_HEADER##',
    'table_boundary': '##HOVER_COLOR_TABLE_BOUNDARY##',
    'preprocessor': '##HOVER_COLOR_PREPROCESSOR##',
    'directive': '##HOVER_COLOR_DIRECTIVE##',
    'data_type': '##HOVER_COLOR_DATA_TYPE##',
    'register': '##HOVER_COLOR_REGISTER##',
    'punctuation_preprocessor': '##HOVER_COLOR_PUNCTUATION_PREPROCESSOR##',
    'operator': '##HOVER_COLOR_OPERATOR##',
}
INLINE_CODE_COLOR = DEFAULT_HOVER_COLORS['inline_code']
TABLE_HEADER_COLOR = DEFAULT_HOVER_COLORS['table_header']
TABLE_CELL_BOUNDARY_COLOR = DEFAULT_HOVER_COLORS['table_boundary']

DEFAULT_HOVER_SETTINGS = {
    'mnemonics': True,
    'labels': True,
    'constants': True,
}
DEFAULT_HOVER_MAX_WIDTH = 900
HOVER_VIEWPORT_MARGIN = 80
DEFAULT_SEMANTIC_HIGHLIGHTING = True

_DOCS_CACHE = {}
_COLOR_CACHE = {}
_VIEW_CACHE = {}
_PENDING_SEMANTIC = {}
SEMANTIC_DEBOUNCE_MS = 350


def _is_bespokeasm_view(view):
    if not view or view.is_scratch() or view.settings().get('is_widget'):
        return False
    if not view.match_selector(0, 'source.bespokeasm'):
        return False
    expected = _get_expected_package_name()
    if expected:
        return _get_package_name(view) == expected
    return True


def _get_expected_package_name():
    if not PACKAGE_NAME or '##PACKAGE_NAME##' in PACKAGE_NAME:
        return None
    return PACKAGE_NAME


def _get_package_name(view):
    syntax = view.settings().get('syntax') or ''
    match = re.match(r'^Packages/([^/]+)/', syntax)
    return match.group(1) if match else None


def _get_package_settings(view):
    package_name = _get_package_name(view)
    if not package_name:
        return None
    return sublime.load_settings('{}.sublime-settings'.format(package_name))


def _get_hover_setting(view, key, default):
    view_key = 'bespokeasm.hover.{}'.format(key)
    if view.settings().has(view_key):
        return bool(view.settings().get(view_key))
    settings = _get_package_settings(view)
    if settings:
        hover_settings = settings.get('hover') or {}
        if isinstance(hover_settings, dict) and key in hover_settings:
            return bool(hover_settings.get(key))
    return default


def _get_hover_numeric_setting(view, key, default=None):
    view_key = 'bespokeasm.hover.{}'.format(key)
    if view.settings().has(view_key):
        value = view.settings().get(view_key)
        if isinstance(value, (int, float)):
            return int(value)
    settings = _get_package_settings(view)
    if settings:
        hover_settings = settings.get('hover') or {}
        if isinstance(hover_settings, dict) and key in hover_settings:
            value = hover_settings.get(key)
            if isinstance(value, (int, float)):
                return int(value)
    return default


def _get_hover_max_width(view, default_width):
    configured = _get_hover_numeric_setting(view, 'max_width')
    if configured is not None and configured > 0:
        return configured
    viewport_width = 0
    try:
        viewport_width = int(view.viewport_extent()[0])
    except Exception:
        viewport_width = 0
    if viewport_width > 0:
        return max(320, viewport_width - HOVER_VIEWPORT_MARGIN)
    return default_width


def _get_semantic_setting(view):
    view_key = 'bespokeasm.semantic_highlighting'
    if view.settings().has(view_key):
        return bool(view.settings().get(view_key))
    settings = _get_package_settings(view)
    if settings:
        return bool(settings.get('semantic_highlighting', DEFAULT_SEMANTIC_HIGHLIGHTING))
    return DEFAULT_SEMANTIC_HIGHLIGHTING


def _load_instruction_docs(view):
    package_name = _get_package_name(view)
    if not package_name:
        return None
    cached = _DOCS_CACHE.get(package_name)
    if cached is not None:
        return cached
    resource_path = 'Packages/{}/instruction-docs.json'.format(package_name)
    try:
        raw = sublime.load_resource(resource_path)
        docs = json.loads(raw)
    except Exception:
        docs = None
    _DOCS_CACHE[package_name] = docs
    return docs


def _load_hover_colors(view):
    package_name = _get_package_name(view)
    if not package_name:
        return DEFAULT_HOVER_COLORS
    cached = _COLOR_CACHE.get(package_name)
    if cached is not None:
        return cached
    resource_path = 'Packages/{}/hover-colors.json'.format(package_name)
    try:
        raw = sublime.load_resource(resource_path)
        colors = json.loads(raw)
    except Exception:
        colors = DEFAULT_HOVER_COLORS
    _COLOR_CACHE[package_name] = colors
    return colors


def _parse_include_path(line):
    match = INCLUDE_PATTERN.match(line)
    if not match:
        return None
    return match.group(1) or match.group(2) or match.group(3)


def _collect_lines(view):
    return view.substr(sublime.Region(0, view.size())).splitlines()


def _collect_included_files(lines, base_dir, visited=None):
    if visited is None:
        visited = set()
    entries = []
    for line in lines:
        include_path = _parse_include_path(line)
        if not include_path:
            continue
        resolved = include_path
        if base_dir and not os.path.isabs(resolved):
            resolved = os.path.normpath(os.path.join(base_dir, include_path))
        if resolved in visited:
            continue
        try:
            with open(resolved, encoding='utf-8') as handle:
                include_lines = handle.read().splitlines()
        except OSError:
            continue
        visited.add(resolved)
        entries.append({'path': resolved, 'lines': include_lines})
        include_base_dir = os.path.dirname(resolved)
        entries.extend(_collect_included_files(include_lines, include_base_dir, visited))
    return entries


def _get_code_regions(text):
    ranges = []
    segment_start = 0
    in_quote = None
    escaped = False

    for idx, ch in enumerate(text):
        if in_quote is not None:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == in_quote:
                in_quote = None
                segment_start = idx + 1
            continue

        if ch in ('"', "'"):
            if segment_start < idx:
                ranges.append((segment_start, idx))
            in_quote = ch
            continue

        if ch == ';':
            if segment_start < idx:
                ranges.append((segment_start, idx))
            return ranges

    if in_quote is None and segment_start < len(text):
        ranges.append((segment_start, len(text)))
    return ranges


def _is_offset_in_code_region(text, offset):
    for start, end in _get_code_regions(text):
        if start <= offset < end:
            return True
    return False


def _iter_label_definitions(text):
    definitions = []

    line_label_match = LABEL_DEFINITION_PATTERN.match(text)
    if line_label_match:
        name = line_label_match.group('name')
        col = line_label_match.start('name')
        if _is_offset_in_code_region(text, col):
            definitions.append((name, col))

    for start, end in _get_code_regions(text):
        segment = text[start:end]
        for match in OPERAND_LABEL_DEFINITION_PATTERN.finditer(segment):
            name = match.group('name')
            col = start + match.start('name')
            definitions.append((name, col))

    definitions.sort(key=lambda item: item[1])
    return definitions


def _iter_constant_definitions(text):
    match = CONSTANT_DEFINITION_PATTERN.match(text)
    if not match:
        return []
    name = match.group('name')
    col = match.start('name')
    if not _is_offset_in_code_region(text, col):
        return []
    return [(name, col)]


def _build_definition_map(entries, definition_kind):
    definitions = {}
    for entry in entries:
        path = entry.get('path')
        for line_index, text in enumerate(entry.get('lines', [])):
            if definition_kind == 'label':
                line_definitions = _iter_label_definitions(text)
            else:
                line_definitions = _iter_constant_definitions(text)
            for name, col in line_definitions:
                if name in definitions:
                    continue
                definitions[name] = {
                    'line': line_index,
                    'col': col,
                    'path': path
                }
    return definitions


def _get_view_state(view):
    view_id = view.id()
    change_count = view.change_count()
    cached = _VIEW_CACHE.get(view_id)
    if cached and cached.get('change_count') == change_count:
        return cached

    lines = _collect_lines(view)
    entries = [{'path': view.file_name(), 'lines': lines}]
    base_dir = os.path.dirname(view.file_name()) if view.file_name() else None
    if base_dir:
        entries.extend(_collect_included_files(lines, base_dir))

    label_map = _build_definition_map(entries, 'label')
    constant_map = _build_definition_map(entries, 'constant')
    state = {
        'change_count': change_count,
        'lines': lines,
        'label_map': label_map,
        'constant_map': constant_map,
        'current_path': view.file_name(),
        'included_entries': entries[1:] if len(entries) > 1 else [],
    }
    _VIEW_CACHE[view_id] = state
    return state


def _get_token_at_point(view, point):
    line_region = view.line(point)
    line_text = view.substr(line_region)
    column = point - line_region.begin()
    for match in WORD_PATTERN.finditer(line_text):
        if match.start() <= column <= match.end():
            return match.group(0)
    return None


def _is_definition_at_point(view, point, token, pattern):
    line_region = view.line(point)
    line_text = view.substr(line_region)
    column = point - line_region.begin()
    if pattern is CONSTANT_DEFINITION_PATTERN:
        definitions = _iter_constant_definitions(line_text)
    else:
        definitions = _iter_label_definitions(line_text)
    for name, start in definitions:
        if name != token:
            continue
        end = start + len(name)
        if start <= column < end:
            return True
    return False


def _build_definition_hover(name, location, current_path, token_color=None):
    line_num = location.get('line', 0) + 1
    path = location.get('path') or current_path
    filename = os.path.basename(path) if path else 'file'
    escaped_name = html.escape(name)
    if token_color:
        code_html = '<code style="color:{};">{}</code>'.format(html.escape(token_color), escaped_name)
    else:
        code_html = '<code>{}</code>'.format(escaped_name)
    if path and current_path and os.path.normcase(path) == os.path.normcase(current_path):
        location_text = 'Defined at line {}.'.format(line_num)
    else:
        location_text = 'Defined at line {} in {}.'.format(line_num, filename)
    if path:
        cmd = _build_hover_link(path, line_num, location.get('col', 0) + 1)
        return '<p>{}: {} <a href="{}">Go to definition</a></p>'.format(
            code_html,
            location_text,
            cmd
        )
    return '<p>{}: {}</p>'.format(code_html, location_text)


def _find_references(token, state):
    """Find all usage locations of a token (excluding its definition).

    Returns a list of dicts with 'line' (0-based), 'col' (0-based), and 'path'.
    """
    refs = []
    current_path = state.get('current_path')

    def _scan_lines(lines, path):
        for line_index, text in enumerate(lines):
            label_defs = None
            const_defs = None
            for start, end in _get_code_regions(text):
                segment = text[start:end]
                for match in WORD_PATTERN.finditer(segment):
                    if match.group(0) != token:
                        continue
                    col = start + match.start()
                    if label_defs is None:
                        label_defs = _iter_label_definitions(text)
                    if const_defs is None:
                        const_defs = _iter_constant_definitions(text)
                    is_def = any(n == token and c == col for n, c in label_defs)
                    is_def = is_def or any(n == token and c == col for n, c in const_defs)
                    if not is_def:
                        refs.append({'line': line_index, 'col': col, 'path': path})

    _scan_lines(state.get('lines', []), current_path)
    for entry in state.get('included_entries', []):
        _scan_lines(entry.get('lines', []), entry.get('path'))
    return refs


def _build_label_definition_self_hover(name, references, current_path, token_color=None):
    escaped_name = html.escape(name)
    if token_color:
        code_html = '<code style="color:{};">{}</code>'.format(html.escape(token_color), escaped_name)
    else:
        code_html = '<code>{}</code>'.format(escaped_name)
    if not references:
        return '<p>{}: No references found.</p>'.format(code_html)
    count = len(references)
    if count == 1:
        header = '{}: 1 reference'.format(code_html)
    else:
        header = '{}: {} references'.format(code_html, count)
    items = []
    for ref in references:
        line_num = ref['line'] + 1
        path = ref.get('path') or current_path
        filename = os.path.basename(path) if path else 'file'
        if path and current_path and os.path.normcase(path) == os.path.normcase(current_path):
            label = 'line {}'.format(line_num)
        else:
            label = 'line {} in {}'.format(line_num, html.escape(filename))
        if path:
            link = _build_hover_link(path, line_num, ref.get('col', 0) + 1)
            items.append('<a href="{}">{}</a>'.format(link, label))
        else:
            items.append(label)
    return '<p>{}</p><p>{}</p>'.format(header, ', '.join(items))


def _extract_constant_value(state, token):
    """Extract the raw value text of a constant from its definition line."""
    location = state.get('constant_map', {}).get(token)
    if not location:
        return None
    line_index = location.get('line', 0)
    lines = state.get('lines', [])
    path = location.get('path')
    if path and path != state.get('current_path'):
        for entry in state.get('included_entries', []):
            if entry.get('path') == path:
                lines = entry.get('lines', [])
                break
        else:
            return None
    if line_index < 0 or line_index >= len(lines):
        return None
    match = CONSTANT_VALUE_PATTERN.match(lines[line_index])
    if match:
        return match.group('value').strip()
    return None


def _build_constant_hover(name, location, current_path, value_text=None, token_color=None, number_color=None):
    line_num = location.get('line', 0) + 1
    path = location.get('path') or current_path
    filename = os.path.basename(path) if path else 'file'
    escaped_name = html.escape(name)
    if token_color:
        code_html = '<code style="color:{};">{}</code>'.format(html.escape(token_color), escaped_name)
    else:
        code_html = '<code>{}</code>'.format(escaped_name)
    if path and current_path and os.path.normcase(path) == os.path.normcase(current_path):
        location_text = 'Defined at line {}.'.format(line_num)
    else:
        location_text = 'Defined at line {} in {}.'.format(line_num, filename)
    parts = [code_html]
    if value_text:
        escaped_value = html.escape(value_text)
        if number_color:
            parts.append(' = <code style="color:{};">{}</code>'.format(html.escape(number_color), escaped_value))
        else:
            parts.append(' = <code>{}</code>'.format(escaped_value))
    parts.append('<br>{}'.format(location_text))
    if path:
        cmd = _build_hover_link(path, line_num, location.get('col', 0) + 1)
        parts.append(' <a href="{}">Go to definition</a>'.format(cmd))
    return '<p>{}</p>'.format(''.join(parts))


def _get_directive_at_point(view, point):
    """Check if the point is on a directive and return its name (without prefix)."""
    line_region = view.line(point)
    line_text = view.substr(line_region)
    column = point - line_region.begin()
    for match in COMPILER_DIRECTIVE_PATTERN.finditer(line_text):
        dir_start = match.start(1) - 1  # include the dot
        dir_end = match.end(1)
        if dir_start <= column < dir_end:
            if _is_offset_in_code_region(line_text, match.start()):
                return match.group(1).lower()
    for match in PREPROCESSOR_DIRECTIVE_PATTERN.finditer(line_text):
        dir_start = match.start(1) - 1  # include the hash
        dir_end = match.end(1)
        if dir_start <= column < dir_end:
            if _is_offset_in_code_region(line_text, match.start()):
                return match.group(1).lower()
    return None


def _get_register_at_point(view, point):
    """Check if the point is on a register token and return its name."""
    line_region = view.line(point)
    line_text = view.substr(line_region)
    column = point - line_region.begin()
    for match in REGISTER_PATTERN.finditer(line_text):
        if match.start() <= column < match.end():
            if _is_offset_in_code_region(line_text, match.start()):
                return match.group(0).lower()
    return None


def _build_hover_link(path, line_num, column):
    return 'bespokeasm://open?path={}&line={}&col={}'.format(
        quote(path),
        line_num,
        column
    )


def _handle_hover_navigate(view, href):
    parsed = urlparse(href)
    if parsed.scheme == 'bespokeasm' and parsed.netloc == 'open':
        params = parse_qs(parsed.query)
        path = params.get('path', [''])[0]
        if not path:
            return
        path = unquote(path)
        line = int(params.get('line', [1])[0])
        col = int(params.get('col', [1])[0])
        window = view.window()
        if window:
            window.open_file('{}:{}:{}'.format(path, line, col), sublime.ENCODED_POSITION)
        return
    if parsed.scheme in ('http', 'https', 'file'):
        window = view.window()
        if window:
            window.run_command('open_url', {'url': href})


def _show_popup(view, html, location, max_width):
    wrapped_html = _with_hover_padding(html)
    view.show_popup(
        wrapped_html,
        location=location,
        max_width=max_width,
        on_navigate=lambda href: _handle_hover_navigate(view, href)
    )


def _with_hover_padding(html):
    return '<div style="padding:0 0 {}px 0;">{}</div>'.format(HOVER_EXTRA_BOTTOM_PADDING_PIXELS, html)


def _render_markdown(markdown_text, hover_colors, heading_color=None, heading_prefix_color=None):
    return _markdown_to_minihtml(
        markdown_text, hover_colors,
        heading_color=heading_color, heading_prefix_color=heading_prefix_color
    )


def _markdown_to_minihtml(markdown_text, hover_colors, heading_color=None, heading_prefix_color=None):
    lines = markdown_text.splitlines()
    html_parts = []
    paragraph_lines = []
    list_items = []
    table_rows = []
    in_code_block = False
    code_lines = []

    def flush_paragraph():
        if not paragraph_lines:
            return
        text = '<br>'.join(paragraph_lines)
        html_parts.append('<p>{}</p>'.format(_render_inline(text)))
        paragraph_lines[:] = []

    def flush_list():
        if not list_items:
            return
        items = ''.join('<li>{}</li>'.format(_render_inline(item)) for item in list_items)
        html_parts.append('<ul>{}</ul>'.format(items))
        list_items[:] = []

    def flush_table():
        if not table_rows:
            return
        html_parts.append(_render_table(table_rows))
        table_rows[:] = []

    def flush_code():
        if not code_lines:
            return
        html_parts.append(_render_code_block(code_lines, hover_colors))
        code_lines[:] = []

    for line in lines:
        stripped = line.strip()
        if table_rows:
            if _is_table_row(stripped):
                parsed = _parse_table_row(stripped)
                if parsed is not None:
                    table_rows.append(parsed)
                continue
            flush_table()
        if in_code_block:
            if stripped.startswith('```'):
                in_code_block = False
                flush_code()
            else:
                code_lines.append(line)
            continue

        if stripped.startswith('```'):
            flush_paragraph()
            flush_list()
            flush_table()
            in_code_block = True
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            flush_table()
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            flush_table()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2)
            content = _render_inline(
                heading_text,
                code_color=_heading_code_color(heading_text, hover_colors, color_override=heading_color),
                prefix_color=heading_prefix_color
            )
            html_parts.append('<h{0}>{1}</h{0}>'.format(level, content))
            continue

        if re.match(r'^(---+|\*\*\*+)$', stripped):
            flush_paragraph()
            flush_list()
            flush_table()
            html_parts.append('<hr>')
            continue

        list_match = re.match(r'^[-*]\s+(.*)$', stripped)
        if list_match:
            flush_paragraph()
            flush_table()
            list_items.append(list_match.group(1))
            continue

        if _is_table_row(stripped):
            flush_paragraph()
            flush_list()
            parsed = _parse_table_row(stripped)
            if parsed is not None:
                table_rows.append(parsed)
            continue

        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()
    flush_table()
    if in_code_block:
        flush_code()

    return ''.join(html_parts)


def _render_inline(text, code_color=INLINE_CODE_COLOR, prefix_color=None):
    escaped = html.escape(text)

    def _replace_code(match):
        content = match.group(1)
        if prefix_color:
            # Split directive prefix (#/.) from name for separate coloring
            prefix_match = re.match(r'^([#.])(\S+)$', content)
            if prefix_match:
                return (
                    '<code>'
                    '<span style="color:{};">{}</span>'
                    '<span style="color:{};">{}</span>'
                    '</code>'
                ).format(prefix_color, prefix_match.group(1), code_color, prefix_match.group(2))
        return '<code style="color:{};">{}</code>'.format(code_color, content)

    escaped = re.sub(r'`([^`]+)`', _replace_code, escaped)
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', escaped)
    return escaped


def _heading_code_color(heading_text, hover_colors, color_override=None):
    if color_override:
        return color_override
    if re.search(r':\s*Predefined Constant\s*$', heading_text):
        return hover_colors.get('compiler_label', DEFAULT_HOVER_COLORS['compiler_label'])
    if re.search(r':\s*Register\s*$', heading_text):
        return hover_colors.get('register', DEFAULT_HOVER_COLORS['register'])
    return hover_colors.get('instruction', DEFAULT_HOVER_COLORS['instruction'])


def _render_code_block(lines, hover_colors):
    instruction_color = hover_colors.get('instruction', DEFAULT_HOVER_COLORS['instruction'])
    parameter_color = hover_colors.get('parameter', DEFAULT_HOVER_COLORS['parameter'])
    number_color = hover_colors.get('number', DEFAULT_HOVER_COLORS['number'])
    punctuation_color = hover_colors.get('punctuation', DEFAULT_HOVER_COLORS['punctuation'])
    preprocessor_color = hover_colors.get('preprocessor', DEFAULT_HOVER_COLORS.get('preprocessor', instruction_color))
    directive_color = hover_colors.get('directive', DEFAULT_HOVER_COLORS.get('directive', instruction_color))
    data_type_color = hover_colors.get('data_type', DEFAULT_HOVER_COLORS.get('data_type', instruction_color))
    punctuation_preproc_color = hover_colors.get(
        'punctuation_preprocessor', DEFAULT_HOVER_COLORS.get('punctuation_preprocessor', punctuation_color)
    )

    # Tokenizer: directive forms (.2byte, #include) must precede generic
    # number/word patterns so they are captured as single tokens.
    token_re = re.compile(
        r'\s+|'
        r'#\S+|'
        r'\.\d*[A-Za-z]\w*|'
        r'0x[0-9a-fA-F]+|\$[0-9a-fA-F]+|\d+|'
        r'[A-Za-z_][\w\d_]*|'
        r'.'
    )

    # Known directive names for code block coloring
    preprocessor_names = {
        'include', 'require', 'error', 'create_memzone', 'print',
        'define', 'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
        'mute', 'unmute', 'emit', 'create-scope', 'use-scope', 'deactivate-scope',
    }
    compiler_directive_names = {'org', 'memzone', 'align'}
    data_type_names = {
        'fill', 'zero', 'zerountil',
        'byte', '2byte', '4byte', '8byte', '16byte', 'cstr', 'asciiz',
    }

    def _classify_directive_token(token_text):
        """Return (prefix_color, name_color) for a directive token, or None."""
        if token_text.startswith('#'):
            name = token_text[1:].lower()
            if name in preprocessor_names:
                return punctuation_preproc_color, preprocessor_color
        elif token_text.startswith('.'):
            name = token_text[1:].lower()
            if name in data_type_names:
                return data_type_color, data_type_color
            if name in compiler_directive_names:
                return directive_color, directive_color
        return None

    rendered_lines = []
    for line in lines:
        parts = []
        seen_mnemonic = False

        for match in token_re.finditer(line):
            token = match.group(0)
            if token.isspace():
                token = token.replace('\t', '    ')
                parts.append(token.replace(' ', '&nbsp;'))
                continue
            # Check for directive tokens (.byte, .2byte, #include, etc.)
            if not seen_mnemonic and (token.startswith('.') or token.startswith('#')):
                dir_colors = _classify_directive_token(token)
                if dir_colors:
                    prefix_color, name_color = dir_colors
                    prefix = token[0]
                    name = token[1:]
                    parts.append('<span style="color:{};">{}</span>'.format(
                        prefix_color, html.escape(prefix)
                    ))
                    parts.append('<span style="color:{};">{}</span>'.format(
                        name_color, html.escape(name)
                    ))
                    seen_mnemonic = True
                    continue
            if re.match(r'^(0x[0-9a-fA-F]+|\$[0-9a-fA-F]+|\d+)$', token):
                color = number_color
            elif re.match(r'^[A-Za-z_][\w\d_]*$', token):
                if not seen_mnemonic:
                    color = instruction_color
                    seen_mnemonic = True
                else:
                    color = parameter_color
            else:
                color = punctuation_color
            escaped = html.escape(token)
            parts.append('<span style="color:{};">{}</span>'.format(color, escaped))
        rendered_lines.append(''.join(parts))

    html_lines = '<br>'.join(rendered_lines)
    return '<div style="font-family: monospace;">{}</div>'.format(html_lines)


def _is_table_row(line):
    if '|' not in line:
        return False
    stripped = line.strip()
    return stripped.startswith('|') or stripped.endswith('|')


def _is_table_separator(cells):
    if not cells:
        return False
    for cell in cells:
        token = cell.strip()
        if not token:
            return False
        token = token.replace(':', '')
        if set(token) != set('-'):
            return False
    return True


def _parse_table_row(line):
    if not _is_table_row(line):
        return None
    content = line.strip()
    if content.startswith('|'):
        content = content[1:]
    if content.endswith('|'):
        content = content[:-1]
    cells = [cell.strip() for cell in content.split('|')]
    return cells


def _render_table(rows):
    if not rows:
        return ''
    header = None
    body_rows = []
    start_index = 0
    if len(rows) >= 2 and _is_table_separator(rows[1]):
        header = rows[0]
        start_index = 2
    for idx in range(start_index, len(rows)):
        body_rows.append(rows[idx])

    def display_length(cell):
        if cell is None:
            return 0
        text = str(cell)
        text = re.sub(r'`([^`]*)`', r'\1', text)
        text = text.replace('*', '')
        return len(text)

    def wrap_text(text, width):
        if text is None:
            return ['']
        raw = str(text).strip()
        if not raw:
            return ['']
        if width <= 0:
            return [raw]
        tokens = re.findall(r'\S+|\s+', raw)
        lines = []
        current = ''
        for token in tokens:
            if token.isspace():
                if current:
                    current += ' '
                continue
            candidate = '{} {}'.format(current, token) if current else token
            if display_length(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while display_length(token) > width:
                lines.append(token[:width])
                token = token[width:]
            current = token
        if current:
            lines.append(current)
        return lines if lines else ['']

    table_rows = []
    if header:
        table_rows.append(header)
    table_rows.extend(body_rows)
    column_count = max(len(row) for row in table_rows) if table_rows else 0
    padded_rows = [
        row + [''] * (column_count - len(row))
        for row in table_rows
    ]
    raw_widths = [
        max(display_length(cell) for cell in column)
        for column in zip(*padded_rows)
    ] if column_count else []
    widths = list(raw_widths)
    last_idx = column_count - 1
    wrap_columns = set()
    if header:
        for idx, cell in enumerate(header):
            label = str(cell).strip().lower()
            if label in ('description', 'value'):
                wrap_columns.add(idx)
    capped = []
    overflow_columns = set()
    for idx, width in enumerate(widths):
        max_width = TABLE_MAX_DESCRIPTION_CHARS if idx == last_idx else TABLE_MAX_COLUMN_CHARS
        if width > max_width:
            overflow_columns.add(idx)
        capped.append(min(max(width, TABLE_MIN_COLUMN_CHARS), max_width))
    widths = capped

    total_width = sum(widths)
    total_width += (TABLE_CELL_LEFT_PAD + TABLE_CELL_RIGHT_PAD) * column_count
    total_width += TABLE_CELL_BOUNDARY_PIXELS * max(column_count - 1, 0)
    allow_wrapping = total_width > TABLE_MAX_TOTAL_CHARS or bool(overflow_columns & wrap_columns)
    wrap_set = set()
    if allow_wrapping:
        if overflow_columns:
            wrap_set = wrap_columns & overflow_columns
        elif header and last_idx >= 0:
            label = str(header[last_idx]).strip().lower()
            if label == 'description':
                wrap_set.add(last_idx)

    def render_cell_line(line, width, is_header, is_last):
        rendered = _render_inline(line) if line else ''
        line_len = display_length(line) if line else 0
        prefix = '&nbsp;' * TABLE_CELL_LEFT_PAD
        spacer = '&nbsp;' * TABLE_CELL_RIGHT_PAD
        padding_html = '&nbsp;' * max(width - line_len, 0)
        border_style = 'border-right:{}px solid {};'.format(
            TABLE_CELL_BOUNDARY_PIXELS,
            TABLE_CELL_BOUNDARY_COLOR
        ) \
            if not is_last else ''
        style = (
            'display:inline-block;vertical-align:top;'
            'padding:3px;{border}'
        ).format(border=border_style)
        if is_header:
            style += (
                    'font-weight:500; border-bottom:{}px solid {}; color: {}; '
                    'background-color: rgba(255, 255, 255, 0.04)'
                ).format(
                    TABLE_CELL_BOUNDARY_PIXELS,
                    TABLE_CELL_BOUNDARY_COLOR,
                    TABLE_HEADER_COLOR,
                )
        return '<span style="{style}">{prefix}{text}{pad}{spacer}</span>'.format(
            style=style,
            prefix=prefix,
            text=rendered,
            pad=padding_html,
            spacer=spacer
        )

    def render_row_line(cells, is_header):
        spans = []
        for idx, cell in enumerate(cells):
            spans.append(render_cell_line(cell, widths[idx], is_header, idx == len(cells) - 1))
        return '<div>{}</div>'.format(''.join(spans))

    def render_wrapped_row(cells):
        wrapped = []
        for idx, cell in enumerate(cells):
            if allow_wrapping and idx in wrap_set:
                wrapped.append(wrap_text(cell, widths[idx]))
            else:
                wrapped.append([cell if cell is not None else ''])
        if wrapped:
            max_lines = max(len(lines) for lines in wrapped) or 1
        else:
            max_lines = 1
        parts = []
        for line_idx in range(max_lines):
            line_cells = [
                lines[line_idx] if line_idx < len(lines) else ''
                for lines in wrapped
            ]
            parts.append(render_row_line(line_cells, False))
        return ''.join(parts)

    parts = ['<div style="font-family: monospace;">']
    if header:
        parts.append(render_row_line(padded_rows[0], True))
        parts.append('<div style="margin:{}px 0;"></div>'.format(TABLE_CELL_BOUNDARY_PIXELS + 2))
        body_start = 1
    else:
        body_start = 0
    for row in padded_rows[body_start:]:
        parts.append(render_wrapped_row(row))
        parts.append('<div style="margin:{}px 0;"></div>'.format(TABLE_ROW_VERT_MARGIN_PIXELS))
    parts.append('</div>')
    return ''.join(parts)


def _schedule_semantic_update(view):
    if not _is_bespokeasm_view(view):
        return
    view_id = view.id()
    # Bump generation counter so any previously scheduled run is cancelled.
    generation = _PENDING_SEMANTIC.get(view_id, 0) + 1
    _PENDING_SEMANTIC[view_id] = generation

    def _run():
        # Only execute if no newer edit has superseded this one.
        if _PENDING_SEMANTIC.get(view_id) != generation:
            return
        _PENDING_SEMANTIC.pop(view_id, None)
        _update_semantic_regions(view)

    sublime.set_timeout_async(_run, SEMANTIC_DEBOUNCE_MS)


def _update_semantic_regions(view):
    if not _is_bespokeasm_view(view):
        return
    if not _get_semantic_setting(view):
        view.erase_regions('bespokeasm_label_usages')
        view.erase_regions('bespokeasm_constant_usages')
        return
    state = _get_view_state(view)
    labels = set(state['label_map'].keys())
    constants = set(state['constant_map'].keys())
    label_regions = []
    constant_regions = []

    # Compute line start offsets once instead of
    # calling view.text_point() per match.
    line_offsets = []
    offset = 0
    for text in state['lines']:
        line_offsets.append(offset)
        offset += len(text) + 1  # +1 for newline

    for line_index, text in enumerate(state['lines']):
        # Use pure-text code region detection instead of
        # view.match_selector() per match (avoids API round-trips).
        code_regions = _get_code_regions(text)
        if not code_regions:
            continue

        label_definition_starts = set(_iter_label_definitions(text))
        constant_definition_starts = set(_iter_constant_definitions(text))
        base_offset = line_offsets[line_index]

        for region_start, region_end in code_regions:
            segment = text[region_start:region_end]
            for match in WORD_PATTERN.finditer(segment):
                word = match.group(0)
                col = region_start + match.start()
                if word in constants:
                    if (word, col) in constant_definition_starts:
                        continue
                    start = base_offset + col
                    constant_regions.append(sublime.Region(start, start + len(word)))
                    continue
                if word in labels:
                    if (word, col) in label_definition_starts:
                        continue
                    start = base_offset + col
                    label_regions.append(sublime.Region(start, start + len(word)))

    view.add_regions(
        'bespokeasm_label_usages',
        label_regions,
        scope=LABEL_USAGE_SCOPE,
        flags=sublime.DRAW_SOLID_UNDERLINE
    )
    view.add_regions(
        'bespokeasm_constant_usages',
        constant_regions,
        scope=CONSTANT_USAGE_SCOPE,
        flags=sublime.DRAW_SOLID_UNDERLINE
    )


class BespokeAsmHoverListener(sublime_plugin.EventListener):
    def on_hover(self, view, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT or not _is_bespokeasm_view(view):
            return

        hover_mnemonics = _get_hover_setting(view, 'mnemonics', DEFAULT_HOVER_SETTINGS['mnemonics'])
        hover_labels = _get_hover_setting(view, 'labels', DEFAULT_HOVER_SETTINGS['labels'])
        hover_constants = _get_hover_setting(view, 'constants', DEFAULT_HOVER_SETTINGS['constants'])
        docs = _load_instruction_docs(view)
        hover_colors = _load_hover_colors(view)
        max_width = _get_hover_max_width(view, DEFAULT_HOVER_MAX_WIDTH)

        # Check directives first (these have their own token patterns)
        if docs and hover_mnemonics:
            all_directives = docs.get('directives', {})
            directive_name = _get_directive_at_point(view, point)
            if directive_name:
                directive_categories = [
                    ('preprocessor', 'preprocessor', 'punctuation_preprocessor'),
                    ('data_type', 'data_type', None),
                    ('compiler', 'directive', None),
                ]
                for category_key, color_key, prefix_color_key in directive_categories:
                    category_docs = all_directives.get(category_key, {})
                    if directive_name in category_docs:
                        heading_color = hover_colors.get(color_key, DEFAULT_HOVER_COLORS.get(color_key))
                        prefix_color = hover_colors.get(
                            prefix_color_key, DEFAULT_HOVER_COLORS.get(prefix_color_key)
                        ) if prefix_color_key else None
                        popup_html = _render_markdown(
                            category_docs[directive_name], hover_colors,
                            heading_color=heading_color, heading_prefix_color=prefix_color
                        )
                        _show_popup(view, popup_html, point, max_width)
                        return

        # Check registers
        if docs and hover_mnemonics:
            register_docs = docs.get('registers', {})
            register_name = _get_register_at_point(view, point)
            if register_name and register_name in register_docs:
                register_color = hover_colors.get('register', DEFAULT_HOVER_COLORS['register'])
                popup_html = _render_markdown(
                    register_docs[register_name], hover_colors, heading_color=register_color
                )
                _show_popup(view, popup_html, point, max_width)
                return

        token = _get_token_at_point(view, point)
        if not token:
            return

        predefined_docs = docs.get('predefined', {}) if docs else {}
        predefined_constant_docs = predefined_docs.get('constants', {})
        predefined_data_docs = predefined_docs.get('data', {})
        predefined_memory_zone_docs = predefined_docs.get('memory_zones', {})

        # Check instruction/macro mnemonics
        if docs and hover_mnemonics:
            instruction_docs = docs.get('instructions', {})
            macro_docs = docs.get('macros', {})
            doc = instruction_docs.get(token.upper()) or macro_docs.get(token.upper())
            if doc:
                popup_html = _render_markdown(doc, hover_colors)
                _show_popup(view, popup_html, point, max_width)
                return

        # Check expression functions (BYTE0, LSB, etc.)
        if docs and hover_mnemonics:
            expr_func_docs = docs.get('expression_functions', {})
            doc = expr_func_docs.get(token.upper())
            if doc:
                operator_color = hover_colors.get('operator', DEFAULT_HOVER_COLORS.get('operator'))
                popup_html = _render_markdown(doc, hover_colors, heading_color=operator_color)
                _show_popup(view, popup_html, point, max_width)
                return

        state = _get_view_state(view)

        # Check user-defined constants (usage hover with value preview)
        if hover_constants and token in state['constant_map'] and not _is_definition_at_point(
            view, point, token, CONSTANT_DEFINITION_PATTERN
        ):
            location = state['constant_map'][token]
            constant_color = hover_colors.get('constant_usage', DEFAULT_HOVER_COLORS['constant_usage'])
            number_color = hover_colors.get('number', DEFAULT_HOVER_COLORS['number'])
            value_text = _extract_constant_value(state, token)
            popup_html = _build_constant_hover(
                token, location, view.file_name(),
                value_text=value_text, token_color=constant_color, number_color=number_color
            )
            _show_popup(view, popup_html, point, max_width)
            return

        # Check predefined constants
        if hover_constants and token not in state['constant_map']:
            doc = predefined_constant_docs.get(token)
            if doc:
                popup_html = _render_markdown(doc, hover_colors)
                _show_popup(view, popup_html, point, max_width)
                return

        # Check user-defined labels (usage hover)
        if hover_labels and token in state['label_map'] and not _is_definition_at_point(
            view, point, token, LABEL_DEFINITION_PATTERN
        ):
            location = state['label_map'][token]
            label_color = hover_colors.get('label_usage', DEFAULT_HOVER_COLORS['label_usage'])
            popup_html = _build_definition_hover(token, location, view.file_name(), token_color=label_color)
            _show_popup(view, popup_html, point, max_width)
            return

        # Check label definition self-hover (show reference list)
        if hover_labels and token in state['label_map'] and _is_definition_at_point(
            view, point, token, LABEL_DEFINITION_PATTERN
        ):
            label_color = hover_colors.get('label_usage', DEFAULT_HOVER_COLORS['label_usage'])
            references = _find_references(token, state)
            popup_html = _build_label_definition_self_hover(
                token, references, view.file_name(), token_color=label_color
            )
            _show_popup(view, popup_html, point, max_width)
            return

        # Check predefined data/memory zones
        if hover_labels and token not in state['label_map']:
            doc = predefined_data_docs.get(token) or predefined_memory_zone_docs.get(token)
            if doc:
                popup_html = _render_markdown(doc, hover_colors)
                _show_popup(view, popup_html, point, max_width)


class BespokeAsmSemanticListener(sublime_plugin.EventListener):
    def on_load_async(self, view):
        _schedule_semantic_update(view)

    def on_modified_async(self, view):
        _schedule_semantic_update(view)

    def on_activated_async(self, view):
        _schedule_semantic_update(view)

    def on_post_save_async(self, view):
        _schedule_semantic_update(view)
