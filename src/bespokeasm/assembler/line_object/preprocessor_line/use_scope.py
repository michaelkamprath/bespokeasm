import re
import sys

from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel


class UseScopeLine(PreprocessorLine):
    """Preprocessor line for #use-scope directive."""

    PATTERN_USE_SCOPE = re.compile(
        r'^#use-scope\s+"([^"]+)"\s*$',
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
    ) -> None:
        """Activate a named scope for the current file."""
        super().__init__(line_id, instruction, comment, memzone)

        use_match = re.search(UseScopeLine.PATTERN_USE_SCOPE, instruction.strip())
        if use_match is not None:
            scope_name = use_match.group(1)

            # Validate input
            if not scope_name:
                sys.exit(f'ERROR: {line_id} - Scope name cannot be empty')

            # Activate the scope
            self._scope_name = scope_name
            self._filename = filename

            if isa_model is not None:
                isa_model.diagnostic_reporter.info(
                    line_id,
                    f'Activated named scope "{scope_name}" for file "{filename}"',
                    min_verbosity=2,
                )
        else:
            sys.exit(f'ERROR: {line_id} - Invalid #use-scope directive syntax: {instruction}')

    @property
    def scope_name(self) -> str:
        return self._scope_name

    @property
    def filename(self) -> str:
        return self._filename

    def __repr__(self) -> str:
        return f'UseScopeLine<{self._scope_name}, file="{self._filename}">'
