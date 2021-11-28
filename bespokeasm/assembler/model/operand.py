import enum
import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart, NumericByteCodePart, ExpressionByteCodePart
from bespokeasm.utilities import is_string_numeric, parse_numeric_string

class OperandType(enum.Enum):
    # these values double as sort order for processing in an operand set
    UNKNOWN = -1
    EMPTY = 1
    NUMERIC = 5
    REGISTER = 4
    INDIRECT_REGISTER = 2
    INDIRECT_NUMERIC = 3

class Operand:
    def factory(operand_id: str, arg_config_dict: dict, default_endian: str):
        type_str = arg_config_dict['type']
        if type_str == 'numeric':
            return NumericExpressionOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'register':
            return RegisterOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'indirect_register':
            return IndirectRegisterOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'indirect_numeric':
            return IndirectNumericOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'empty':
            return EmptyOperand(operand_id, arg_config_dict, default_endian)
        else:
            return None

    def __init__(self, operand_id, arg_config_dict, default_endian):
        self._id = operand_id
        self._config = arg_config_dict
        self._default_endian = default_endian

    def __repr__(self):
        return str(self)
    def __str__(self):
        return f'Operand<{self.id}>'

    @property
    def id(self) -> str:
        return self._id
    @property
    def type(self) -> OperandType:
        return OperandType.UNKNOWN
    @property
    def null_operand(self) -> bool:
        '''Indicates whether this operand object expects a non-empty string to be parsed.'''
        return False
    @property
    def has_bytecode(self) -> bool:
        return ('bytecode' in self._config)
    @property
    def bytecode_value(self) -> int:
        if self.has_bytecode:
            return self._config['bytecode']['value']
        else:
            return None
    @property
    def bytecode_size(self) -> int:
        if self.has_bytecode:
            return self._config['bytecode']['size']
        else:
            return None
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

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # this should be overridden
        return None, None

class EmptyOperand(Operand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)

    def __str__(self):
        return f'EmptyOperand<{self.id}>'
    @property
    def type(self) -> OperandType:
        return OperandType.EMPTY
    def null_operand(self) -> bool:
        '''This operand type does not parse any thing from teh instruction'''
        return True

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) if self.bytecode_value is not None else None
        return bytecode_part, None

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

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        if operand.strip() != self.register:
            return None, None
        bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) if self.bytecode_value is not None else None
        arg_part = None
        return bytecode_part, arg_part

class IndirectRegisterOperand(RegisterOperand):
    OPERAND_PATTERN_TEMPLATE = '^\[\s*({0})\s*(?:(\+|\-)\s*([\s\w\+\-\*\/\&\|\^\(\)\$\%]+)\s*)?\]$'

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)
        self._match_pattern = re.compile(
            self.OPERAND_PATTERN_TEMPLATE.format(self.register),
            flags=re.IGNORECASE|re.MULTILINE
        )
    def __str__(self):
        return f'IndirectRegisterOperand<{self.id},register={self.register}>'
    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_REGISTER

    @property
    def has_offset(self) -> bool:
        return ('offset' in self._config)
    @property
    def offset_size(self) -> int:
        return self._config['offset']['size']
    @property
    def offset_byte_align(self) -> bool:
        return self._config['offset']['byte_align']
    @property
    def offset_endian(self) -> str:
        return self._config['offset'].get('endian', self._default_endian)
    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # first check that operand is what we expect
        match = re.match(self._match_pattern, operand.strip())
        if match is not None and len(match.groups()) > 0:
            bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) \
                if self.bytecode_value is not None else None
            if self.has_offset:
                if len(match.groups()) == 3 and match.group(2) is not None and match.group(3) is not None:
                    # we have an offset argument. construct the offset expression. Group 2 is the + or - sign, and our expression
                    # parser expects 2 operands for the + or - sign
                    argument_str = f'0 {match.group(2).strip()} {match.group(3).strip()}'
                    arg_part = ExpressionByteCodePart(argument_str, self.offset_size, self.offset_byte_align, self.offset_endian, line_id)
                else:
                    # must have and offset value of 0
                    arg_part = NumericByteCodePart(0, self.offset_size, self.offset_byte_align, self.offset_endian, line_id)
            else:
                if len(match.groups()) == 3 and match.group(2) is not None and match.group(3) is not None:
                    # and offset was added for an operand that wasn't configured to have one. Error.
                    sys.exit(f'ERROR: {line_id} - An offset was provided for indirect register operand "{operand}" when none was expected.')
                arg_part = None
            return bytecode_part, arg_part
        else:
            return None, None


class IndirectNumericOperand(NumericExpressionOperand):
    OPERAND_PATTERN = re.compile(r'^\[([\s\w\+\-\*\/\&\|\^\(\)\$\%]+)\]$', flags=re.IGNORECASE|re.MULTILINE)

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)

    def __str__(self):
        return f'IndirectNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.REGISTER

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
