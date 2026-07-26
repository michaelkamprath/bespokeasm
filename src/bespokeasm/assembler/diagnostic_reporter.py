from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass

from bespokeasm.assembler.line_identifier import LineIdentifier


class DiagnosticReporter:
    @dataclass(frozen=True)
    class Diagnostic:
        level: str
        line_id: LineIdentifier | None
        message: str
        category: str

    def __init__(
        self,
        warnings_as_errors: bool = False,
        verbosity: int = 0,
        categories_elevated: Iterable[str] | None = None,
    ) -> None:
        self._warnings_as_errors = warnings_as_errors
        self._verbosity = verbosity
        self._categories_elevated = set(categories_elevated or {'user', 'flow'})
        self._diagnostics: list[DiagnosticReporter.Diagnostic] = []

    @property
    def warnings_as_errors(self) -> bool:
        return self._warnings_as_errors

    @property
    def verbosity(self) -> int:
        return self._verbosity

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._diagnostics)

    def _format(self, prefix: str, line_id: LineIdentifier | None, message: str) -> str:
        if line_id is None:
            return f'{prefix}: {message}'
        return f'{prefix}: {line_id} - {message}'

    def error(self, line_id: LineIdentifier | None, message: str, category: str = 'user') -> None:
        self._diagnostics.append(self.Diagnostic('error', line_id, message, category))
        text = self._format('ERROR', line_id, message)
        sys.exit(text)

    def warn(self, line_id: LineIdentifier | None, message: str, category: str = 'user') -> None:
        if self._warnings_as_errors and category in self._categories_elevated:
            self.error(line_id, message, category=category)
            return
        self._diagnostics.append(self.Diagnostic('warning', line_id, message, category))
        text = self._format('WARNING', line_id, message)
        print(text, file=sys.stderr)

    def info(
        self,
        line_id: LineIdentifier | None,
        message: str,
        min_verbosity: int = 1,
        category: str = 'info',
    ) -> None:
        if self._verbosity < min_verbosity:
            return
        self._diagnostics.append(self.Diagnostic('info', line_id, message, category))
        text = self._format('INFO', line_id, message)
        print(text, file=sys.stderr)
