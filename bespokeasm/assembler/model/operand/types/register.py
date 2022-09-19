import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class RegisterOperand(Operand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, regsiters: set[str]):
        super().__init__(operand_id, arg_config_dict, default_endian)
        if self.register not in regsiters:
            sys.exit(f'ERROR - ISA configation declares register based operand {self} but the '
                     f'register label "{self.register}" is not a declared register.')

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

    @property
    def operand_register_string(self) -> str:
        return self.register

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        if operand.strip() != self.register:
            return None
        bytecode_part = NumericByteCodePart(
            self.bytecode_value,
            self.bytecode_size,
            False,
            'big',
            line_id
        ) if self.bytecode_value is not None else None
        arg_part = None
        return ParsedOperand(self, bytecode_part, arg_part, operand)
