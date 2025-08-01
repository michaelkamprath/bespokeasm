from functools import cached_property

from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand.types.indirect_numeric import IndirectNumericOperand


class DeferredNumericOperand(IndirectNumericOperand):

    def __str__(self):
        return f'DeferredNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.DEFERRED_NUMERIC

    @cached_property
    def match_pattern(self) -> str:
        return fr'^\[\s*\[\s*({super(DeferredNumericOperand.__bases__[0], self).match_pattern})\s*\]\s*\]$'
