import re
import sys

from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel


class DeactivateScopeLine(PreprocessorLine):
    """Preprocessor line for #deactivate-scope directive."""

    PATTERN_DEACTIVATE_SCOPE = re.compile(
        r'^#deactivate-scope\s+"([^"]+)"\s*$',
        re.IGNORECASE
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        named_scope_manager: NamedScopeManager,
        filename: str,
        log_verbosity: int
    ) -> None:
        """Deactivate a named scope for the current file."""
        super().__init__(line_id, instruction, comment, memzone)

        deactivate_match = re.search(DeactivateScopeLine.PATTERN_DEACTIVATE_SCOPE, instruction.strip())
        if deactivate_match is not None:
            scope_name = deactivate_match.group(1)

            # Validate input
            if not scope_name:
                sys.exit(f'ERROR: {line_id} - Scope name cannot be empty')

            self._scope_name = scope_name
            self._filename = filename

            if log_verbosity >= 2:
                print(f'INFO: {line_id} - Deactivated named scope "{scope_name}" for file "{filename}"')
        else:
            sys.exit(f'ERROR: {line_id} - Invalid #deactivate-scope directive syntax: {instruction}')

    @property
    def scope_name(self) -> str:
        return self._scope_name

    @property
    def filename(self) -> str:
        return self._filename

    def __repr__(self) -> str:
        return f'DeactivateScopeLine<{self._scope_name}, file="{self._filename}">'
