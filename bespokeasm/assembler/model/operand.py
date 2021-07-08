import enum
import re

from bespokeasm.assembler.byte_code.parts import ByteCodePart, NumericByteCodePart, ExpressionByteCodePart
from bespokeasm.utilities import is_string_numeric, parse_numeric_string

class OperandType(enum.Enum):
    # these values double as sort order for processing in an operand set
    UNKNOWN = -1
    NUMERIC = 4
    REGISTER = 3
    INDIRECT_REGISTER = 1
    INDIRECT_NUMERIC = 2

class Operand:
    def factory(arg_config_dict: dict, default_endian: str):
        type_str = arg_config_dict['type']
        if type_str == 'numeric':
            return NumericExpressionOperand(arg_config_dict, default_endian)
        elif type_str == 'register':
            return RegisterOperand(arg_config_dict, default_endian)
        elif type_str == 'indirect_register':
            return IndirectRegisterOperand(arg_config_dict, default_endian)
        elif type_str == 'indirect_numeric':
            return IndirectNumericOperand(arg_config_dict, default_endian)
        else:
            return None

    def __init__(self, arg_config_dict, default_endian):
        self._config = arg_config_dict
        self._bytecode_value = arg_config_dict.get('bytecode_value', None)
        if self._bytecode_value is not None:
            self._bytecode_size = arg_config_dict['bytecode_size']
        self._default_endian = default_endian

    def __repr__(self):
        return str(self)
    def __str__(self):
        return f'Operand<{self.type}>'

    # @property
    # def id(self) -> str:
    #     return self._config['id']
    @property
    def type(self) -> OperandType:
        return OperandType.UNKNOWN

    @property
    def has_bytecode(self) -> bool:
        return self._bytecode_value is not None
    @property
    def bytecode_value(self) -> int:
        return self._bytecode_value
    @property
    def bytecode_size(self) -> int:
        return self._bytecode_size
    @property
    def has_offset(self) -> bool:
        return False
    @property
    def offset_size(self) -> int:
        return None
    @property
    def offset_byte_align(self) -> bool:
        return None
    @property
    def offset_endian(self) -> str:
        return None
    @property
    def has_argument(self) -> bool:
        return False
    @property
    def argument_size(self) -> int:
        return None
    @property
    def argument_byte_align(self) -> bool:
        return None
    @property
    def argument_endian(self) -> str:
        return None

    def parse_operand(self, line_num: int, operand: str) -> tuple[ByteCodePart, ByteCodePart]:
        # this should be overridden
        return None, None

class NumericExpressionOperand(Operand):
    def __init__(self, arg_config_dict: dict, default_endian: str):
        super().__init__(arg_config_dict, default_endian)
        self._argument_size = arg_config_dict['argument_size']
        self._argmunet_byte_align = arg_config_dict['argument_byte_align']
        self._argmunet_endian = arg_config_dict['argument_endian'] if 'argument_endian' in arg_config_dict else default_endian

    @property
    def type(self) -> OperandType:
        return OperandType.NUMERIC

    @property
    def has_argument(self) -> bool:
        return True
    @property
    def argument_size(self) -> int:
        return self._argument_size
    @property
    def argument_byte_align(self) -> bool:
        return self._argmunet_byte_align
    @property
    def argument_endian(self) -> str:
        return self._argmunet_endian

    def parse_operand(self, line_num: int, operand: str) -> tuple[ByteCodePart, ByteCodePart]:
        bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big') if self.bytecode_value is not None else None
        arg_part = ExpressionByteCodePart(operand, self.argument_size, self.argument_byte_align, self.argument_endian)
        return bytecode_part, arg_part

class RegisterOperand(Operand):
    def __init__(self, arg_config_dict: dict, default_endian: str):
        super().__init__(arg_config_dict, default_endian)

    def __str__(self):
        return f'RegisterOperand<register={self.register}>'
    @property
    def type(self) -> OperandType:
        return OperandType.REGISTER
    @property
    def register(self) -> str:
        return self._config['register']

    def parse_operand(self, line_num: int, operand: str) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        if operand.strip() != self.register:
            return None, None
        bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big') if self.bytecode_value is not None else None
        arg_part = None
        return bytecode_part, arg_part

class IndirectRegisterOperand(Operand):
    OPERAND_PATTERN_TEMPLATE = '^\[\s*({0})\s*(?:(\+|\-)\s*([\s\w\+\-\*\/\&\|\^\(\)\$\%]+)\s*)?\]$'

    def __init__(self, arg_config_dict: dict, default_endian: str):
        super().__init__(arg_config_dict, default_endian)
        self._match_pattern = re.compile(
            self.OPERAND_PATTERN_TEMPLATE.format(self.register),
            flags=re.IGNORECASE|re.MULTILINE
        )

    @property
    def type(self) -> OperandType:
        return OperandType.REGISTER
    @property
    def register(self) -> str:
        return self._config['register']
    @property
    def has_offset(self) -> bool:
        return self._config.get('offset_enabled', False)
    @property
    def offset_size(self) -> int:
        return self._config.get('offset_size', None)
    @property
    def offset_byte_align(self) -> bool:
        return self._config.get('offset_byte_align', None)
    @property
    def offset_endian(self) -> str:
        return self._config.get('offset_endian', self._default_endian)
    def parse_operand(self, line_num: int, operand: str) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        match = re.match(self._match_pattern, operand.strip())
        if match is not None and len(match.groups()) > 0:
            bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big') if self.bytecode_value is not None else None
            if len(match.groups()) == 3 and match.group(2) is not None and match.group(3) is not None:
                # we have an offset argument. construct the offset expression. Group 2 is the + or - sign, and our expression
                # parser expects 2 operands for the + or - sign
                argument_str = f'0 {match.group(2).strip()} {match.group(3).strip()}'
                arg_part = ExpressionByteCodePart(argument_str, self.offset_size, self.offset_byte_align, self.offset_endian)
            else:
                # must have and offset value of 0
                arg_part = NumericByteCodePart(0, self.offset_size, self.offset_byte_align, self.offset_endian)
            return bytecode_part, arg_part
        else:
            return None, None


class IndirectNumericOperand(Operand):
    OPERAND_PATTERN = re.compile(r'^\[([\s\w\+\-\*\/\&\|\^\(\)\$\%]+)\]$', flags=re.IGNORECASE|re.MULTILINE)

    def __init__(self, arg_config_dict: dict, default_endian: str):
        super().__init__(arg_config_dict, default_endian)

    def __str__(self):
        return f'IndirectNumericOperand<arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.REGISTER
    @property
    def has_argument(self) -> bool:
        return True
    @property
    def argument_size(self) -> int:
        return self._config['argument_size']
    @property
    def argument_byte_align(self) -> bool:
        return self._config.get('argument_byte_align', True)
    @property
    def argument_endian(self) -> str:
        return self._config.get('argument_endian', self._default_endian)

    def parse_operand(self, line_num: int, operand: str) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        match = re.match(IndirectNumericOperand.OPERAND_PATTERN, operand.strip())
        if match is not None and len(match.groups()) > 0:
            bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big') if self.bytecode_value is not None else None
            arg_part = ExpressionByteCodePart(match.group(1).strip(), self.argument_size, self.argument_byte_align, self.argument_endian)
            return bytecode_part, arg_part
        else:
            return None, None
