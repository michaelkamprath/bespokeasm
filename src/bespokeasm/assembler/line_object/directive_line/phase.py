# The phase directives assemble code for one address while its bytes go somewhere else:
#
#   .phase X    - from here, labels and `*` see addresses starting at X, while the bytes continue
#                 at the current place in the image. A `.phase` inside a phase starts a new one
#                 from the current place in the image.
#   .dephase    - ends the phase: addresses continue from the current place in the image.
#
# A phase belongs to its memory zone, the way the zone's current address does. `.org` ends it.
import re

from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import INSTRUCTION_EXPRESSION_PATTERN
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import PATTERN_LABEL_DEFINITION
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.expression import parse_expression


class PhaseLine(LineObject):
    # Like `.org`, either may be followed by a label on the same line: `.phase 0xfc00 start:`.
    PATTERN_PHASE = re.compile(
        fr'^\.phase(?:\s+({INSTRUCTION_EXPRESSION_PATTERN}))?(?=\s*$|{PATTERN_LABEL_DEFINITION})',
        flags=re.IGNORECASE,
    )
    PATTERN_DEPHASE = re.compile(fr'^\.dephase(?=\s*$|{PATTERN_LABEL_DEFINITION})', flags=re.IGNORECASE)

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        address_expression: str | None,
        default_numeric_base: str = 'decimal',
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        self._memzone_manager = memzone_manager
        self._address_expr = None
        if address_expression is not None:
            self._address_expr = parse_expression(line_id, address_expression, default_numeric_base)

    def __repr__(self) -> str:
        return f'PhaseLine<{self.instruction}>'

    @property
    def is_dephase(self) -> bool:
        return self._address_expr is None

    def phase_address(self) -> int:
        """The address a `.phase` sets, checked against the address space."""
        value = self._address_expr.get_value(self.symbol_scope, self.active_named_scopes, self.line_id)
        zone = self._memzone_manager.global_zone
        if not zone.start <= value <= zone.end:
            raise AssemblerError(
                self.line_id,
                f'.phase address {value} ({hex(value)}) is outside the address space '
                f'({hex(zone.start)} to {hex(zone.end)})',
            )
        return value
