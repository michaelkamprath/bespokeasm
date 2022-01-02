from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart, NumericByteCodePart
from bespokeasm.assembler.model.operand import Operand, OperandType

class RegisterOperand(Operand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)

    def __str__(self):
        return f'RegisterOperand<{self.id},register={self.register}>'
    @property
    def type(self) -> OperandType:
        return OperandType.REGISTER
    @property
    def register(self) -> str:
        return self._config['register']

    @property
    def match_pattern(self) -> str:
        return r'{0}'.format(self.register)

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        if operand.strip() != self.register:
            return None, None
        bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) if self.bytecode_value is not None else None
        arg_part = None
        return bytecode_part, arg_part