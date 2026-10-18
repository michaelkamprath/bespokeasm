from __future__ import annotations

import sys
import traceback
from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import click
from bespokeasm.assembler.line_identifier import LineIdentifier


class AssemblerError(Exception):
    """A user-facing assembly or configuration error raised by code without a reporter.

    Code that cannot reach a DiagnosticReporter raises this instead of exiting. It is
    reported at a boundary that owns a reporter (see DiagnosticReporter.reporting_errors),
    which lets callers that try several interpretations discard the errors of failed ones.
    """

    def __init__(
        self,
        line_id: LineIdentifier | None,
        message: str,
        category: str = 'user',
    ) -> None:
        super().__init__(message)
        self.line_id = line_id
        self.message = message
        self.category = category


class InternalAssemblerError(RuntimeError):
    """A failed internal consistency check, meaning a bug in BespokeASM rather than in the
    user's source or configuration.

    Deliberately not an AssemblerError: callers that discard AssemblerErrors from failed
    parse attempts must not swallow a bug. When it reaches a reporting boundary it is
    reported with its traceback and the source line being processed, if known.
    """

    def __init__(self, line_id: LineIdentifier | None, message: str) -> None:
        super().__init__(message)
        self.line_id = line_id
        self.message = message


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

    def error(
        self,
        line_id: LineIdentifier | None,
        message: str,
        category: str = 'user',
        color: str | None = None,
    ) -> None:
        """Record an error and terminate, optionally coloring its display text."""
        self._diagnostics.append(self.Diagnostic('error', line_id, message, category))
        display_message = (
            click.style(message, fg=color)
            if color is not None
            else message
        )
        text = self._format('ERROR', line_id, display_message)
        sys.exit(text)

    @contextmanager
    def reporting_errors(self) -> Iterator[None]:
        """Report any AssemblerError or InternalAssemblerError raised within the block as an error."""
        try:
            yield
        except AssemblerError as err:
            self.error(err.line_id, err.message, category=err.category)
        except InternalAssemblerError as err:
            traceback.print_exc(file=sys.stderr)
            self.error(
                err.line_id,
                f'INTERNAL: {err.message} (this is a BespokeASM bug; please report it)',
                category='internal',
            )

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
