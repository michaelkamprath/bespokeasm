import re
import sys

from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel


class CreateScopeLine(PreprocessorLine):
    """Preprocessor line for #create-scope directive."""

    PATTERN_CREATE_SCOPE = re.compile(
        r'^#create-scope\s+"([^"]+)"\s*(?:prefix\s*=\s*"([^"]*)")?\s*$',
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
        log_verbosity: int
    ) -> None:
        """Create a new named scope definition."""
        super().__init__(line_id, instruction, comment, memzone)

        create_match = re.search(CreateScopeLine.PATTERN_CREATE_SCOPE, instruction.strip())
        if create_match is not None:
            scope_name = create_match.group(1)
            prefix = create_match.group(2) if create_match.group(2) is not None else '_'

            # Validate inputs
            if not scope_name:
                sys.exit(f'ERROR: {line_id} - Scope name cannot be empty')

            if not prefix or prefix == '':
                sys.exit(f'ERROR: {line_id} - Scope prefix cannot be empty')

            # Create the scope
            try:
                named_scope_manager.create_scope(scope_name, prefix, line_id)
                self._scope_name = scope_name
                self._prefix = prefix

                if log_verbosity >= 2:
                    print(f'INFO: {line_id} - Created named scope "{scope_name}" with prefix "{prefix}"')

            except SystemExit:
                # Re-raise system exits (these are expected error conditions)
                raise

        else:
            sys.exit(f'ERROR: {line_id} - Invalid #create-scope directive syntax: {instruction}')

    @property
    def scope_name(self) -> str:
        return self._scope_name

    @property
    def prefix(self) -> str:
        return self._prefix

    def __repr__(self) -> str:
        return f'CreateScopeLine<{self._scope_name}, prefix="{self._prefix}">'
