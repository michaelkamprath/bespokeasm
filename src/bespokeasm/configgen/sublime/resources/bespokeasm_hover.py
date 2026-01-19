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
LABEL_DEFINITION_PATTERN = re.compile(r'^\s*(##LABEL_PATTERN##)\s*:')
CONSTANT_DEFINITION_PATTERN = re.compile(r'^\s*(##LABEL_PATTERN##)\s*(?:=|\bEQU\b)')
INCLUDE_PATTERN = re.compile(r'^\s*#include\s+(?:"([^"]+)"|<([^>]+)>|(\S+))', re.IGNORECASE)
PACKAGE_NAME = '##PACKAGE_NAME##'

LABEL_USAGE_SCOPE = 'variable.other.label.usage'
CONSTANT_USAGE_SCOPE = 'variable.other.constant.usage'
INSTRUCTION_COLOR = '#ffa83f'
INLINE_CODE_COLOR = '#6fb1ff'
TABLE_HEADER_COLOR = '#D98C8C'
TABLE_CELL_BOUNDARY_PIXELS = 2
TABLE_ROW_VERT_MARGIN_PIXELS = 1
TABLE_CELL_BOUNDARY_COLOR = '#5F748A'
TABLE_MAX_COLUMN_CHARS = 32
TABLE_MAX_DESCRIPTION_CHARS = 48
TABLE_MIN_COLUMN_CHARS = 6
TABLE_MAX_TOTAL_CHARS = 120
TABLE_CELL_LEFT_PAD = 1
TABLE_CELL_RIGHT_PAD = 2
DEFAULT_HOVER_COLORS = {
    'instruction': INSTRUCTION_COLOR,
    'parameter': '#abd7ed',
    'number': '#fffd80',
    'punctuation': '#ed80a2',
}

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
_PENDING_SEMANTIC = set()


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
    lines = []
    for line_region in view.lines(sublime.Region(0, view.size())):
        lines.append(view.substr(line_region))
    return lines


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


def _build_definition_map(entries, pattern):
    definitions = {}
    for entry in entries:
        path = entry.get('path')
        for line_index, text in enumerate(entry.get('lines', [])):
            match = pattern.match(text)
            if not match:
                continue
            name = match.group(1)
            if name in definitions:
                continue
            definitions[name] = {
                'line': line_index,
                'col': text.find(name),
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

    label_map = _build_definition_map(entries, LABEL_DEFINITION_PATTERN)
    constant_map = _build_definition_map(entries, CONSTANT_DEFINITION_PATTERN)
    state = {
        'change_count': change_count,
        'lines': lines,
        'label_map': label_map,
        'constant_map': constant_map
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
    match = pattern.match(line_text)
    if not match or match.group(1) != token:
        return False
    column = point - line_region.begin()
    start = match.start(1)
    end = match.end(1)
    return start <= column < end


def _build_definition_hover(name, location, current_path):
    line_num = location.get('line', 0) + 1
    path = location.get('path') or current_path
    filename = os.path.basename(path) if path else 'file'
    if path and current_path and os.path.normcase(path) == os.path.normcase(current_path):
        location_text = 'Defined at line {}.'.format(line_num)
    else:
        location_text = 'Defined at line {} in {}.'.format(line_num, filename)
    if path:
        cmd = _build_hover_link(path, line_num, location.get('col', 0) + 1)
        return '<p><code>{}</code>: {} <a href="{}">Go to definition</a></p>'.format(
            name,
            location_text,
            cmd
        )
    return '<p><code>{}</code>: {}</p>'.format(name, location_text)


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
    view.show_popup(
        html,
        location=location,
        max_width=max_width,
        on_navigate=lambda href: _handle_hover_navigate(view, href)
    )


def _render_markdown(markdown_text, hover_colors):
    return _markdown_to_minihtml(markdown_text, hover_colors)


def _markdown_to_minihtml(markdown_text, hover_colors):
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
            content = _render_inline(heading_match.group(2), code_color=INSTRUCTION_COLOR)
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


def _render_inline(text, code_color=INLINE_CODE_COLOR):
    escaped = html.escape(text)
    escaped = re.sub(
        r'`([^`]+)`',
        r'<code style="color:{};">\1</code>'.format(code_color),
        escaped
    )
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', escaped)
    return escaped


def _render_code_block(lines, hover_colors):
    instruction_color = hover_colors.get('instruction', INSTRUCTION_COLOR)
    parameter_color = hover_colors.get('parameter', DEFAULT_HOVER_COLORS['parameter'])
    number_color = hover_colors.get('number', DEFAULT_HOVER_COLORS['number'])
    punctuation_color = hover_colors.get('punctuation', DEFAULT_HOVER_COLORS['punctuation'])

    token_re = re.compile(
        r'\s+|'
        r'0x[0-9a-fA-F]+|\$[0-9a-fA-F]+|\d+|'
        r'[A-Za-z_][\w\d_]*|'
        r'.'
    )

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
    if view_id in _PENDING_SEMANTIC:
        return
    _PENDING_SEMANTIC.add(view_id)

    def _run():
        _PENDING_SEMANTIC.discard(view_id)
        _update_semantic_regions(view)

    sublime.set_timeout_async(_run, 120)


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
    for line_index, text in enumerate(state['lines']):
        label_def = LABEL_DEFINITION_PATTERN.match(text)
        label_def_name = label_def.group(1) if label_def else None
        label_def_start = label_def.start(1) if label_def else None
        const_def = CONSTANT_DEFINITION_PATTERN.match(text)
        const_def_name = const_def.group(1) if const_def else None
        const_def_start = const_def.start(1) if const_def else None

        for match in WORD_PATTERN.finditer(text):
            word = match.group(0)
            start = view.text_point(line_index, match.start())
            end = view.text_point(line_index, match.end())
            if _is_in_comment(view, start, end):
                continue
            if word in constants:
                if const_def_name == word and match.start() == const_def_start:
                    continue
                constant_regions.append(sublime.Region(start, end))
                continue
            if word in labels:
                if label_def_name == word and match.start() == label_def_start:
                    continue
                label_regions.append(sublime.Region(start, end))

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


def _is_in_comment(view, start, end):
    if view.match_selector(start, 'comment'):
        return True
    if end > start and view.match_selector(end - 1, 'comment'):
        return True
    return False


class BespokeAsmHoverListener(sublime_plugin.EventListener):
    def on_hover(self, view, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT or not _is_bespokeasm_view(view):
            return
        token = _get_token_at_point(view, point)
        if not token:
            return
        hover_mnemonics = _get_hover_setting(view, 'mnemonics', DEFAULT_HOVER_SETTINGS['mnemonics'])
        hover_labels = _get_hover_setting(view, 'labels', DEFAULT_HOVER_SETTINGS['labels'])
        hover_constants = _get_hover_setting(view, 'constants', DEFAULT_HOVER_SETTINGS['constants'])
        docs = _load_instruction_docs(view)
        if docs and hover_mnemonics:
            instruction_docs = docs.get('instructions', {})
            macro_docs = docs.get('macros', {})
            doc = instruction_docs.get(token.upper()) or macro_docs.get(token.upper())
            if doc:
                hover_colors = _load_hover_colors(view)
                html = _render_markdown(doc, hover_colors)
                max_width = _get_hover_max_width(view, DEFAULT_HOVER_MAX_WIDTH)
                _show_popup(view, html, point, max_width)
                return

        state = _get_view_state(view)
        if hover_constants and token in state['constant_map'] and not _is_definition_at_point(
            view, point, token, CONSTANT_DEFINITION_PATTERN
        ):
            location = state['constant_map'][token]
            html = _build_definition_hover(token, location, view.file_name())
            max_width = _get_hover_max_width(view, DEFAULT_HOVER_MAX_WIDTH)
            _show_popup(view, html, point, max_width)
            return
        if hover_labels and token in state['label_map'] and not _is_definition_at_point(
            view, point, token, LABEL_DEFINITION_PATTERN
        ):
            location = state['label_map'][token]
            html = _build_definition_hover(token, location, view.file_name())
            max_width = _get_hover_max_width(view, DEFAULT_HOVER_MAX_WIDTH)
            _show_popup(view, html, point, max_width)


class BespokeAsmSemanticListener(sublime_plugin.EventListener):
    def on_load_async(self, view):
        _schedule_semantic_update(view)

    def on_modified_async(self, view):
        _schedule_semantic_update(view)

    def on_activated_async(self, view):
        _schedule_semantic_update(view)

    def on_post_save_async(self, view):
        _schedule_semantic_update(view)
