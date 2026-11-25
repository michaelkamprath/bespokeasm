"""Continuing an ``#annotate`` directive onto the next physical lines with a trailing ``\\``.

Only ``#annotate`` lines continue. A line continues when it ends, after trailing spaces, with a
``\\`` that is outside a quoted value and not in a ``;`` comment, so a continued line cannot carry
a comment; the directive's last line can. The ``\\`` and the line break become one space.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.parsing import split_line_comment

_ANNOTATE_PATTERN = re.compile(r'#annotate(?=\s|$)')


@dataclass(frozen=True)
class ContinuedDirective:
    """An ``#annotate`` directive written over several physical lines."""
    text: str                                   # the joined directive, without its comment
    comment: str                                # the last line's comment
    first_line: str                             # the first physical line's code, as written
    continuation: tuple[tuple[int, str], ...]   # (line number, stripped text) of each later line


def is_annotate_line(line_str: str) -> bool:
    return _ANNOTATE_PATTERN.match(line_str) is not None


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
    """Whether the end of this code is inside a quoted value, as in ``x="a\\``."""
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


def read_continued_annotate(
    source_lines: list[str],
    index: int,
    line_id: LineIdentifier,
) -> ContinuedDirective | None:
    """The directive starting at ``source_lines[index]`` when that ``#annotate`` line continues.

    Returns None for a line that does not continue. Errors report the directive's first line.
    """
    first = source_lines[index].strip()
    code = _continued_code(first)
    if code is None:
        return None
    parts = [code]
    continuation: list[tuple[int, str]] = []
    comment = ''
    while code is not None:
        index += 1
        if index >= len(source_lines):
            raise AssemblerError(
                line_id, f'#annotate ends with \\ but the file ends at line {index}',
            )
        line_str = source_lines[index].strip()
        if not line_str:
            raise AssemblerError(line_id, f'#annotate ends with \\ but line {index + 1} is blank')
        continuation.append((index + 1, line_str))
        code = _continued_code(line_str)
        if code is None:
            line_code, comment = split_line_comment(line_str)
            parts.append(line_code.strip())
        else:
            parts.append(code)
    return ContinuedDirective(
        text=' '.join(parts),
        comment=comment.strip(),
        first_line=split_line_comment(first)[0].strip(),
        continuation=tuple(continuation),
    )
