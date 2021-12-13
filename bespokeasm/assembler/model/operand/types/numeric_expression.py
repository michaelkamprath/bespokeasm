import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart, NumericByteCodePart, ExpressionByteCodePart
from bespokeasm.assembler.model.operand import Operand, OperandType


class NumericExpressionOperand(Operand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)
        # validate config
        if 'argument' not in self._config:
            sys.exit(f'ERROR: configuration for numeric operand {self} does not have an arument configuration')

    def __str__(self):
        return f'NumericExpressionOperand<{self.id}>'
    @property
    def type(self) -> OperandType:
        return OperandType.NUMERIC

    @property
    def has_argument(self) -> bool:
        return True
    @property
    def argument_size(self) -> int:
        return self._config['argument']['size']
    @property
    def argument_byte_align(self) -> bool:
        return self._config['argument']['byte_align']
    @property
    def argument_endian(self) -> str:
        return self._config['argument'].get('endian', self._default_endian)


    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # do not match if expression contains square bracks
        if "[" in operand or "]" in operand:
            return None, None
        bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) if self.bytecode_value is not None else None
        arg_part = ExpressionByteCodePart(operand, self.argument_size, self.argument_byte_align, self.argument_endian, line_id)
        if arg_part.contains_register_labels(register_labels):
            return None,None
        return bytecode_part, arg_part