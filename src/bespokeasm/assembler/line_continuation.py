"""Continuing a line onto the next physical lines with a trailing ``\\``.

Three kinds of line continue: ``#annotate`` directives, data directives (``.byte``, ``.2byte``,
``.4byte``, ``.8byte``, ``.16byte``, ``.cstr`` and ``.asciiz``, after an optional label), and
embedded strings. A line continues when it ends, after trailing spaces, with a ``\\`` that is
outside a quoted string and not in a ``;`` comment, so a continued line cannot carry a comment;
the last line can. The ``\\`` and the line break become one space. Adjacent quoted strings are
one string, so a long string is written as one quoted piece per line::

    message: .cstr "Hello, " \\
                   "world"
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.parsing import split_line_comment

_ANNOTATE_PATTERN = re.compile(r'#annotate(?=\s|$)')
# A data directive or an embedded string, after an optional label such as `message:`.
_DATA_PATTERN = re.compile(
    r'(?:[^\s;"\':]+:\s*)?(?:(?P<directive>\.(?:byte|2byte|4byte|8byte|16byte|cstr|asciiz))\b|(?P<string>"))',
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ContinuedLine:
    """A line written over several physical lines."""
    what: str                                   # what continues, for messages: '#annotate', '.cstr', ...
    text: str                                   # the joined line, without its comment
    comment: str                                # the last line's comment
    first_line: str                             # the first physical line's code, as written
    tail: str                                   # the joined text of the later lines, without the comment
    continuation: tuple[tuple[int, str], ...]   # (line number, stripped text) of each later line

    @property
    def is_annotate(self) -> bool:
        return self.what == '#annotate'


class ContinuationLine(LineObject):
    """A later physical line of a continued line. A listing shows it as written; it emits nothing,
    and it neither ends a label's data nor interrupts an annotation."""

    def __repr__(self) -> str:
        return f'ContinuationLine<{self.instruction}>'


def continued_line_kind(line_str: str) -> str | None:
    """What a line that ends with ``\\`` continues as, or None when that kind of line does not continue."""
    if _ANNOTATE_PATTERN.match(line_str):
        return '#annotate'
    match = _DATA_PATTERN.match(line_str)
    if match is None:
        return None
    return match.group('directive').lower() if match.group('directive') else 'the string'


def _continued_code(line_str: str) -> str | None:
    """The line's code without its trailing ``\\`` when the line continues, else None."""
    code, comment = split_line_comment(line_str)
    code = code.rstrip()
    if comment or not code.endswith('\\'):
        return None
    if _ends_inside_quote(code):
        return None
    return code[:-1].rstrip()


def _ends_inside_quote(code: str) -> bool:
    """Whether the end of this code is inside a quoted string, as in ``"a\\``."""
    in_quote: str | None = None
    escaped = False
    for character in code:
        if in_quote is not None:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == in_quote:
                in_quote = None
        elif character in ('"', "'"):
            in_quote = character
    return in_quote is not None


def read_continued_line(source_lines: list[str], index: int, line_id: LineIdentifier) -> ContinuedLine | None:
    """The line starting at ``source_lines[index]`` when it continues onto the next lines.

    Returns None for a line that does not continue. Errors report the line's first line.
    """
    first = source_lines[index].strip()
    code = _continued_code(first)
    if code is None:
        return None
    what = continued_line_kind(first)
    if what is None:
        return None
    parts = [code]
    continuation: list[tuple[int, str]] = []
    comment = ''
    while code is not None:
        index += 1
        if index >= len(source_lines):
            raise AssemblerError(line_id, f'{what} ends with \\ but the file ends at line {index}')
        line_str = source_lines[index].strip()
        if not line_str:
            raise AssemblerError(line_id, f'{what} ends with \\ but line {index + 1} is blank')
        continuation.append((index + 1, line_str))
        code = _continued_code(line_str)
        if code is None:
            line_code, comment = split_line_comment(line_str)
            parts.append(line_code.strip())
        else:
            parts.append(code)
    return ContinuedLine(
        what=what,
        text=' '.join(parts),
        comment=comment.strip(),
        first_line=split_line_comment(first)[0].strip(),
        tail=' '.join(parts[1:]),
        continuation=tuple(continuation),
    )


def continuation_line_objects(
    continued: ContinuedLine, filename: str | None, memzone: MemoryZone,
) -> list[ContinuationLine]:
    """A line object for each later physical line, so a listing shows each as written. Only the
    last can carry a comment."""
    objects = []
    for position, (number, text) in enumerate(continued.continuation):
        is_last = position == len(continued.continuation) - 1
        code = split_line_comment(text)[0].strip() if is_last else text
        objects.append(ContinuationLine(
            LineIdentifier(number, filename=filename), code, continued.comment if is_last else '', memzone,
        ))
    return objects


def list_first_line(line_objects: list[LineObject], continued: ContinuedLine) -> None:
    """Have the listing show the continued line's first physical line on its first row: the parsed
    objects hold the joined text, whose later part the continuation rows already show."""
    if not continued.tail:
        return
    for line_object in reversed(line_objects):
        instruction = line_object.instruction
        if instruction.endswith(continued.tail):
            line_object.list_as(f'{instruction[:-len(continued.tail)].rstrip()} \\')
            return
