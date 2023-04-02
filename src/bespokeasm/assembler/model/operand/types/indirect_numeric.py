from functools import cached_property
import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.operand import OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager

from .numeric_expression import NumericExpressionOperand


class IndirectNumericOperand(NumericExpressionOperand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)

    def __str__(self):
        return f'IndirectNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_NUMERIC

    @cached_property
    def match_pattern(self) -> str:
        return r'^\[\s*({0})\s*\]$'.format(super().match_pattern)

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        match = re.match(self.match_pattern, operand.strip())
        if match is not None and len(match.groups()) > 0:
            return self._parse_bytecode_parts(
                line_id,
                match.group(1).strip(),
                register_labels,
                memzone_manager,
            )
        else:
            return None
