"""Splits a source line into code, string literals and comment, so rules match only code."""
from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field

# Stands in for every character of a string literal in a line's masked code, so a rule's
# pattern can't match inside a string.
MASK = '\0'
COMMENT_CHAR = ';'

# A label definition at the start of a statement: a name and a colon, or a lone colon, which
# defines an anonymous label. `:=` is an assignment, not a label.
_LABEL_FIELD = re.compile(r'\s*(?:(?P<name>[A-Za-z_.@][\w.@]*\$?)\s*:(?![=+\-<>])|(?P<anonymous>:)(?![=+\-<>:]))')
# The word that begins a statement: a directive, mnemonic or macro name.
_HEAD_WORD = re.compile(r'\s*(?P<word>[.#]?[A-Za-z_][\w.]*)')


@dataclass
class Statement:
    """The parts of a line's code, as offsets into the line."""
    label: str | None = None
    label_span: tuple[int, int] | None = None
    anonymous_label_span: tuple[int, int] | None = None
    head: str | None = None
    head_span: tuple[int, int] | None = None
    # Where the operands begin: after the head word, or where the head word would be.
    operands_start: int = 0


@dataclass
class Line:
    """One source line and what migration did to it."""
    number: int
    text: str
    doubled_quotes: bool = False
    # Why the line can't be converted. A reported line is written out as a comment.
    reports: list[str] = field(default_factory=list)
    # The line is written out as a comment, without a report.
    dropped: bool = False
    # A reported line inside a reported block: the summary lists the block's first line only.
    quiet: bool = False
    # Informational notes for the summary, such as an included file to migrate separately.
    notes: list[str] = field(default_factory=list)
    _masked: str | None = None
    _comment_start: int | None = None

    def __post_init__(self) -> None:
        self._lex()

    def _lex(self) -> None:
        self._masked, self._comment_start = mask_line(self.text, self.doubled_quotes)

    @property
    def code(self) -> str:
        """The line before its comment, with every string literal masked out."""
        return self._masked[:self._comment_start]

    @property
    def comment_start(self) -> int:
        return self._comment_start

    @property
    def active(self) -> bool:
        """Whether rules still apply: a reported or dropped line is left as it is."""
        return not self.reports and not self.dropped

    def replace(self, edits: list[tuple[int, int, str]]) -> None:
        """Replace each (start, end) span of the line's text, then lex it again."""
        text = self.text
        for start, end, replacement in sorted(edits, key=lambda edit: edit[0], reverse=True):
            text = text[:start] + replacement + text[end:]
        self.text = text
        self._lex()

    def statement(self) -> Statement:
        return parse_statement(self.code)

    def strings(self) -> list[tuple[int, int]]:
        """The (start, end) spans of the line's string literals, quotes included."""
        spans = []
        start = None
        for index, char in enumerate(self._masked[:self._comment_start]):
            if char == MASK and start is None:
                start = index
            elif char != MASK and start is not None:
                spans.append((start, index))
                start = None
        if start is not None:
            spans.append((start, self._comment_start))
        return spans

    def rendered(self) -> str:
        if self.reports:
            return f'; MIGRATE: {"; ".join(self.reports)}: {self.text}'
        if self.dropped:
            indent = len(self.text) - len(self.text.lstrip())
            return f'{self.text[:indent]}; {self.text[indent:]}'
        return self.text


def mask_line(text: str, doubled_quotes: bool = False) -> tuple[str, int]:
    """The line with each string literal replaced by MASK characters, and where its comment
    begins (the line's length when it has none).

    A string is quoted with `"` or `'`, and a backslash escapes the next character. With
    ``doubled_quotes``, a doubled quote inside a string, as in `'IT''S'`, is part of it.
    """
    chars = list(text)
    index = 0
    while index < len(text):
        char = text[index]
        if char == COMMENT_CHAR:
            return ''.join(chars), index
        if char in '"\'':
            end = _string_end(text, index, doubled_quotes)
            if end is None:
                # An unterminated quote: a lone character literal, as in `lda #'A`, or a mistake.
                # Either way, the rest of the line is not masked.
                index += 1
                continue
            for position in range(index, end):
                chars[position] = MASK
            index = end
            continue
        index += 1
    return ''.join(chars), len(text)


def _string_end(text: str, start: int, doubled_quotes: bool) -> int | None:
    quote = text[start]
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == '\\':
            index += 2
            continue
        if char == quote:
            if doubled_quotes and index + 1 < len(text) and text[index + 1] == quote:
                index += 2
                continue
            return index + 1
        index += 1
    return None


def parse_statement(code: str) -> Statement:
    statement = Statement()
    position = 0
    label = _LABEL_FIELD.match(code)
    if label is not None:
        if label.group('name') is not None:
            statement.label = label.group('name')
            statement.label_span = label.span('name')
        else:
            statement.anonymous_label_span = label.span('anonymous')
        position = label.end()
    statement.operands_start = position
    head = _HEAD_WORD.match(code, position)
    if head is not None:
        statement.head = head.group('word')
        statement.head_span = head.span('word')
        statement.operands_start = head.end()
    return statement


def directive_name(word: str | None) -> str | None:
    """A word's name as a directive: lower case, without a leading `.` or `#`."""
    if not word:
        return None
    return word.lstrip('.#').lower() or None
