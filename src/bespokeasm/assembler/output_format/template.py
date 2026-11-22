"""Templates for config-defined output formats.

A template is text with ``{field}`` or ``{field:spec}`` replacement fields, where
``spec`` is a Python format spec (``04x``, ``>8``, ``03o``). Field names are a fixed
set given by whoever owns the template; expressions, attribute access and
conversions are not allowed. ``{?...}`` is an optional group: it is written only when
every field inside it has a value. Groups do not nest. ``{{`` and ``}}`` are literal
braces.

A field with no value (``None`` or the empty string) prints as nothing and its
format spec is not applied.

Every problem is found by ``Template.parse`` when the configuration loads, including
format specs that cannot apply to the field's type, so rendering cannot fail.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import NoReturn

ErrorFn = Callable[[str], NoReturn]
_FIELD_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# A field that may not take a format spec (for example, a section of generated text).
NO_FORMAT_SPEC = object()


@dataclass(frozen=True)
class _Literal:
    text: str


@dataclass(frozen=True)
class _Field:
    name: str
    spec: str


@dataclass(frozen=True)
class _Group:
    parts: tuple


def has_value(value: Any) -> bool:
    return value is not None and value != ''


def _format_value(value: Any, spec: str) -> str:
    if not has_value(value):
        return ''
    if spec == '':
        return str(value)
    return format(value, spec)


class Template:
    def __init__(self, text: str, parts: tuple) -> None:
        self._text = text
        self._parts = parts

    @property
    def text(self) -> str:
        return self._text

    @property
    def field_names(self) -> set[str]:
        names: set[str] = set()
        for part in self._parts:
            if isinstance(part, _Field):
                names.add(part.name)
            elif isinstance(part, _Group):
                names.update(field.name for field in part.parts if isinstance(field, _Field))
        return names

    @classmethod
    def parse(cls, text: str, fields: dict[str, Any], error: ErrorFn) -> Template:
        """Parse and check a template.

        ``fields`` maps each allowed field name to a sample value of its type, used to
        check format specs; ``NO_FORMAT_SPEC`` marks a field that may not have one.
        ``error`` receives a problem description and must not return.
        """
        if not isinstance(text, str):
            error('must be a string')
        parts: list = []
        group: list | None = None
        literal: list[str] = []
        position = 0

        def flush() -> None:
            if literal:
                (group if group is not None else parts).append(_Literal(''.join(literal)))
                literal.clear()

        while position < len(text):
            if text.startswith('{{', position) or text.startswith('}}', position):
                literal.append(text[position])
                position += 2
            elif text.startswith('{?', position):
                if group is not None:
                    error(f'nests an optional group "{{?" inside another at position {position}; groups do not nest')
                flush()
                group = []
                position += 2
            elif text[position] == '{':
                end = text.find('}', position)
                if end == -1:
                    error(f'has a "{{" with no closing "}}" at position {position}')
                flush()
                field = cls._parse_field(text[position + 1:end], fields, error)
                (group if group is not None else parts).append(field)
                position = end + 1
            elif text[position] == '}':
                if group is None:
                    error(f'has a single "}}" at position {position}; write a literal brace as "}}}}"')
                flush()
                if not any(isinstance(part, _Field) for part in group):
                    error('has an optional group "{?...}" with no fields in it')
                parts.append(_Group(tuple(group)))
                group = None
                position += 1
            else:
                literal.append(text[position])
                position += 1
        if group is not None:
            error('has an optional group "{?" with no closing "}"')
        flush()
        return Template(text, tuple(parts))

    @staticmethod
    def _parse_field(body: str, fields: dict[str, Any], error: ErrorFn) -> _Field:
        name, _, spec = body.partition(':')
        if '{' in spec:
            error(f'has a nested replacement field in "{{{body}}}"')
        if _FIELD_NAME.match(name) is None:
            error(f'has an invalid field "{{{body}}}"; fields are plain names such as {{address}} or {{address:04x}}')
        if name not in fields:
            known = ', '.join(sorted(fields))
            error(f'uses unknown field "{name}"; known fields are {known}')
        sample = fields[name]
        if spec:
            if sample is NO_FORMAT_SPEC:
                error(f'gives field "{name}" a format spec, which it does not take')
            try:
                format(sample, spec)
            except (ValueError, TypeError) as exc:
                error(f'gives field "{name}" the format spec "{spec}", which does not apply to it: {exc}')
        return _Field(name, spec)

    def render(self, values: dict[str, Any]) -> str:
        output: list[str] = []
        for part in self._parts:
            if isinstance(part, _Literal):
                output.append(part.text)
            elif isinstance(part, _Field):
                output.append(_format_value(values.get(part.name), part.spec))
            else:
                if all(has_value(values.get(field.name)) for field in part.parts if isinstance(field, _Field)):
                    for field in part.parts:
                        if isinstance(field, _Literal):
                            output.append(field.text)
                        else:
                            output.append(_format_value(values.get(field.name), field.spec))
        return ''.join(output)
