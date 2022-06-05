from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart, ExpressionByteCodePart
from bespokeasm.assembler.model.operand import OperandWithArgument, OperandType, ParsedOperand


class NumericExpressionOperand(OperandWithArgument):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, require_arg: bool = True) -> None:
        super().__init__(operand_id, arg_config_dict, default_endian, require_arg)

    def __str__(self):
        return f'NumericExpressionOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.NUMERIC

    @property
    def match_pattern(self) -> str:
        return r'(?:[\$\%\w\(\)\+\-\s]*[\w\)])'

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> ParsedOperand:
        # do not match if expression contains square bracks
        if "[" in operand or "]" in operand:
            return None
        bytecode_part = NumericByteCodePart(
            self.bytecode_value,
            self.bytecode_size,
            False,
            'big',
            line_id
        ) if self.bytecode_value is not None else None
        arg_part = ExpressionByteCodePart(operand, self.argument_size, self.argument_byte_align, self.argument_endian, line_id)
        if arg_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, arg_part, operand)