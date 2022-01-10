from bespokeasm.assembler.model.operand.types.indirect_numeric import IndirectNumericOperand
from bespokeasm.assembler.model.operand import OperandType

class DeferredNumericOperand(IndirectNumericOperand):

    def __str__(self):
        return f'DeferredNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.DEFERRED_NUMERIC

    @property
    def match_pattern(self) -> str:
        return r'^\[\s*\[\s*({0})\s*\]\s*\]$'.format(super(DeferredNumericOperand.__bases__[0], self).match_pattern)