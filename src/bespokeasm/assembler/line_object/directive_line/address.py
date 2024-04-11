import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.expression import parse_expression, ExpressionNode
from .memzone import SetMemoryZoneLine


class AddressOrgLine(SetMemoryZoneLine):
    def __init__(
            self,
            line_id:
            LineIdentifier,
            instruction: str,
            comment: str,
            address_expression: str,
            memzone_name: str,
            memzone_manager: MemoryZoneManager,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone_name, memzone_manager)
        self._parsed_memzone_name = memzone_name
        self._address_expr: ExpressionNode = parse_expression(line_id, address_expression)

    @property
    def address(self) -> int:
        """Returns the adjusted address value set by the .org directive.
        """
        offset_value = self._address_expr.get_value(self.label_scope, self.line_id)
        if self._parsed_memzone_name is None:
            value = offset_value
        else:
            value = self.memory_zone.start + offset_value
        if value < self.memzone_manager.global_zone.start:
            sys.exit(
                f'ERROR: {self.line_id} - .org address value of {value} is less than the minimum '
                f'address of {self.memzone_manager.global_zone.start} in memory zone {self._memzone.name}'
            )
        if value > self.memzone_manager.global_zone.end:
            sys.exit(
                f'ERROR: {self.line_id} - .org address value of {value} is greater than the maximum '
                f'address of {self.memzone_manager.global_zone.end} in memory zone {self._memzone.name}'
            )
        return value

    def set_start_address(self, address: int):
        """A no-op for the .org directive
        """
        return
