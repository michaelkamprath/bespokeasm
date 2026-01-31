import sys

from bespokeasm.assembler.line_identifier import LineIdentifier


class WarningReporter:
    def __init__(self, warnings_as_errors: bool = False) -> None:
        self._warnings_as_errors = warnings_as_errors

    @property
    def warnings_as_errors(self) -> bool:
        return self._warnings_as_errors

    def warn(self, line_id: LineIdentifier | None, message: str) -> None:
        prefix = 'ERROR' if self._warnings_as_errors else 'WARNING'
        if line_id is None:
            text = f'{prefix}: {message}'
        else:
            text = f'{prefix}: {line_id} - {message}'
        if self._warnings_as_errors:
            sys.exit(text)
        print(text, file=sys.stderr)
