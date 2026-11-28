from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand.types.indirect_numeric import IndirectNumericOperand


class DeferredNumericOperand(IndirectNumericOperand):
    """A numeric expression in two pairs of the operand's enclosure, `[[vec]]` or `((vec))`."""

    def __str__(self):
        return f'DeferredNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.DEFERRED_NUMERIC

    @property
    def enclosure_depth(self) -> int:
        return 2
