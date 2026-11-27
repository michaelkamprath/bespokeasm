"""Migrates one source file with one dialect's rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

from bespokeasm.migrate.dialects import Dialect
from bespokeasm.migrate.lexer import directive_name
from bespokeasm.migrate.lexer import Line
from bespokeasm.migrate.rules import MigrationContext

_INCLUDE_ARGUMENT = re.compile(r'\s*["<]?([^">;\s]+)')


@dataclass
class RuleCount:
    kind: str
    lines: int


@dataclass
class MigrationResult:
    lines: list[Line]
    rule_counts: list[RuleCount]
    trailing_newline: bool
    # The source's line ending, which the migrated text keeps.
    newline: str = '\n'

    @property
    def text(self) -> str:
        text = self.newline.join(line.rendered() for line in self.lines)
        return text + self.newline if self.trailing_newline else text

    @property
    def reported(self) -> list[Line]:
        """The lines that couldn't be converted, without the inner lines of a reported block."""
        return [line for line in self.lines if line.reports and not line.quiet]

    @property
    def reported_line_count(self) -> int:
        return sum(1 for line in self.lines if line.reports)

    @property
    def noted(self) -> list[Line]:
        return [line for line in self.lines if line.notes]


def migrate(text: str, dialect: Dialect, context: MigrationContext) -> MigrationResult:
    source_lines = text.splitlines()
    lines = [Line(number, line, dialect.doubled_quotes) for number, line in enumerate(source_lines, start=1)]
    counts = []
    for rule in dialect.rules:
        before = [_state(line) for line in lines]
        rule.apply(lines, context)
        changed = sum(1 for line, state in zip(lines, before) if _state(line) != state)
        counts.append(RuleCount(rule.kind, changed))
    for line in lines:
        statement = line.statement()
        if line.active and directive_name(statement.head) == 'include' and statement.head.startswith('#'):
            argument = _INCLUDE_ARGUMENT.match(line.text, statement.operands_start)
            name = argument.group(1) if argument else 'a file'
            line.notes.append(f'includes {name}; migrate it separately')
    newline = '\r\n' if '\r\n' in text else '\n'
    return MigrationResult(lines, counts, text.endswith(('\n', '\r')), newline)


def _state(line: Line) -> tuple:
    return line.text, len(line.reports), line.dropped
