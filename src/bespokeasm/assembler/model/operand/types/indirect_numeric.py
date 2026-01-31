import re
from functools import cached_property

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import ParsedOperand

from .numeric_expression import NumericExpressionOperand


class IndirectNumericOperand(NumericExpressionOperand):
    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
    ):
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
            diagnostic_reporter,
            require_arg=True,
        )

    def __str__(self):
        return f'IndirectNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_NUMERIC

    @cached_property
    def match_pattern(self) -> str:
        return fr'\[\s*({super().match_pattern})\s*\]'

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        match = re.match(f'^{self.match_pattern}$', operand.strip())
        if match is not None and len(match.groups()) > 0:
            return self._parse_bytecode_parts(
                line_id,
                match.group(1).strip(),
                register_labels,
                memzone_manager,
            )
        else:
            return None
