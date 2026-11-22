"""The column model shared by table-writing generators (``exports`` with ``columns``, and later
``byte_lines``).

``columns`` is a list in output order. Each entry names a ``field`` and can set ``header``
(default empty), ``format`` (a Python format spec), ``align`` (``left`` or ``right``, default
``left``) and ``min_width`` (default 0). Instead of ``field``, a column can choose its field per
row: ``by`` names an enum argument and ``cases`` maps its values to ``{field, format}``; a row
whose value has no case gets an empty cell. Every value is formatted first; each column is then as
wide as the largest of its ``min_width``, its header and its widest value. Columns are joined
with ``separator`` (default two spaces), the last column is not padded, and trailing spaces are
removed from each line. A header row is written unless every header is empty.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import NoReturn

from bespokeasm.assembler.output_format.template import check_format_spec
from bespokeasm.assembler.output_format.template import format_value

# error(path below the option, problem); the path is '' for the option itself.
ColumnErrorFn = Callable[[str, str], NoReturn]

COLUMN_KEYS = ('field', 'by', 'cases', 'header', 'format', 'align', 'min_width')
CASE_KEYS = ('field', 'format')
ALIGNMENTS = ('left', 'right')
DEFAULT_SEPARATOR = '  '


@dataclass(frozen=True)
class Column:
    field: str | None
    header: str = ''
    format: str = ''
    align: str = 'left'
    min_width: int = 0
    by: str | None = None
    cases: tuple[tuple[str, str, str], ...] = ()   # (value of ``by``, field, format spec)

    def cell(self, row: dict[str, Any], key: dict[str, Any]) -> str:
        """This column's text for a row; ``key`` holds the values ``by`` is looked up in."""
        if self.by is None:
            return format_value(row.get(self.field), self.format)
        selected = key.get(self.by)
        for value, field, spec in self.cases:
            if value == selected:
                return format_value(row.get(field), spec)
        return ''


class ColumnTable:
    def __init__(self, columns: tuple[Column, ...], separator: str) -> None:
        self._columns = columns
        self._separator = separator

    @property
    def columns(self) -> tuple[Column, ...]:
        return self._columns

    @property
    def field_names(self) -> set[str]:
        names = {column.field for column in self._columns if column.field is not None}
        for column in self._columns:
            names.update(field for _, field, _ in column.cases)
        return names

    @classmethod
    def load(
        cls,
        columns: Any,
        separator: Any,
        fields: dict[str, Any],
        error: ColumnErrorFn,
        enum_fields: dict[str, tuple[str, ...]] | None = None,
    ) -> ColumnTable:
        """Check a ``columns`` list and ``separator`` against the fields a generator offers.

        ``fields`` maps each field name to a sample value of its type, to check format specs.
        ``enum_fields`` maps each field a column may choose its field ``by`` to its values.
        """
        enum_fields = enum_fields or {}
        if separator is None:
            separator = DEFAULT_SEPARATOR
        elif not isinstance(separator, str):
            error('separator', 'must be a string')
        if not isinstance(columns, list) or not columns:
            error('columns', 'must be a non-empty list of columns, each a mapping with a field')
        loaded = []
        for index, entry in enumerate(columns):
            path = f'columns[{index}]'
            if not isinstance(entry, dict):
                error(path, 'must be a mapping with a field')
            for key in entry:
                if key not in COLUMN_KEYS:
                    error(f'{path}.{key}', f'is not a column setting; columns take {", ".join(COLUMN_KEYS)}')
            field = entry.get('field')
            by = entry.get('by')
            if field is not None and (by is not None or 'cases' in entry):
                error(path, 'has a field and also by or cases; give a field, or by and cases')
            if field is None and by is None:
                error(path, 'needs a field, or by and cases')
            cases: tuple[tuple[str, str, str], ...] = ()
            if by is not None:
                cases = cls._load_cases(entry, path, fields, enum_fields, error)
            elif field not in fields:
                error(f'{path}.field', f'names unknown field "{field}"; known fields are {", ".join(sorted(fields))}')
            header = entry.get('header', '')
            if not isinstance(header, str):
                error(f'{path}.header', 'must be a string')
            spec = entry.get('format', '')
            if by is not None and 'format' in entry:
                error(f'{path}.format', 'is set per case when a column has by and cases')
            if not isinstance(spec, str):
                error(f'{path}.format', 'must be a string with a format spec, such as "04x"')
            if spec:
                check_format_spec(field, fields[field], spec, lambda problem: error(f'{path}.format', problem))
            align = entry.get('align', 'left')
            if align not in ALIGNMENTS:
                error(f'{path}.align', f'must be left or right, not "{align}"')
            min_width = entry.get('min_width', 0)
            if isinstance(min_width, bool) or not isinstance(min_width, int) or min_width < 0:
                error(f'{path}.min_width', 'must be a whole number, 0 or more')
            loaded.append(Column(field, header, spec, align, min_width, by, cases))
        return ColumnTable(tuple(loaded), separator)

    @staticmethod
    def _load_cases(
        entry: dict,
        path: str,
        fields: dict[str, Any],
        enum_fields: dict[str, tuple[str, ...]],
        error: ColumnErrorFn,
    ) -> tuple[tuple[str, str, str], ...]:
        by = entry['by']
        if by not in enum_fields:
            known = ', '.join(sorted(enum_fields)) or 'none here'
            error(f'{path}.by', f'must name an enum argument; enum arguments are {known}')
        cases = entry.get('cases')
        if not isinstance(cases, dict) or not cases:
            error(f'{path}.cases', f"must map values of '{by}' to a field, as {{value: {{field: ..., format: ...}}}}")
        loaded = []
        for value, case in cases.items():
            case_path = f'{path}.cases.{value}'
            if str(value) not in enum_fields[by]:
                error(case_path, f"is not a value of argument '{by}'")
            if not isinstance(case, dict) or 'field' not in case:
                error(case_path, 'must be a mapping with a field')
            for key in case:
                if key not in CASE_KEYS:
                    error(f'{case_path}.{key}', f'is not a case setting; cases take {", ".join(CASE_KEYS)}')
            field = case['field']
            if field not in fields:
                error(f'{case_path}.field', f'names unknown field "{field}"; known fields are {", ".join(sorted(fields))}')
            spec = case.get('format', '')
            if not isinstance(spec, str):
                error(f'{case_path}.format', 'must be a string with a format spec, such as "04x"')
            if spec:
                check_format_spec(field, fields[field], spec, lambda problem: error(f'{case_path}.format', problem))
            loaded.append((str(value), field, spec))
        return tuple(loaded)

    def render(self, rows: list[dict[str, Any]], keys: list[dict[str, Any]] | None = None) -> str:
        """The table for these rows, each a mapping of field name to value. ``keys`` holds, per row,
        the values that ``by`` columns are looked up in (default: the rows themselves)."""
        keys = keys if keys is not None else rows
        cells = [[column.cell(row, key) for column in self._columns] for row, key in zip(rows, keys)]
        headers = [column.header for column in self._columns]
        if any(headers):
            cells.insert(0, headers)
        widths = [
            max([column.min_width] + [len(line[index]) for line in cells])
            for index, column in enumerate(self._columns)
        ]
        lines = []
        for line in cells:
            texts = []
            last = len(self._columns) - 1
            for index, (column, text) in enumerate(zip(self._columns, line)):
                if column.align == 'right':
                    texts.append(text.rjust(widths[index]))
                elif index == last:
                    texts.append(text)
                else:
                    texts.append(text.ljust(widths[index]))
            lines.append(self._separator.join(texts).rstrip())
        return '\n'.join(lines)
