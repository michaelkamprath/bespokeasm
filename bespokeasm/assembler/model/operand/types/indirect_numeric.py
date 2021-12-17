import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart, NumericByteCodePart, ExpressionByteCodePart
from bespokeasm.assembler.model.operand import Operand, OperandType

from .numeric_expression import NumericExpressionOperand



class IndirectNumericOperand(NumericExpressionOperand):
    OPERAND_PATTERN = re.compile(r'^\[([\s\w\+\-\*\/\&\|\^\(\)\$\%]+)\]$', flags=re.IGNORECASE|re.MULTILINE)

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)

    def __str__(self):
        return f'IndirectNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_NUMERIC

    @property
    def match_pattern(self) -> str:
        return r'\[\s*(?:{0})\s*\]'.format(super().match_pattern)

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        match = re.match(IndirectNumericOperand.OPERAND_PATTERN, operand.strip())
        if match is not None and len(match.groups()) > 0:
            bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) \
                if self.bytecode_value is not None else None
            arg_part = ExpressionByteCodePart(match.group(1).strip(), self.argument_size, self.argument_byte_align, self.argument_endian, line_id)
            if arg_part.contains_register_labels(register_labels):
                return None,None
            return bytecode_part, arg_part
        else:
            return None, None
