import enum

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart

class OperandType(enum.Enum):
    # these values double as sort order for processing in an operand set
    UNKNOWN = -1
    EMPTY = 1
    NUMERIC = 6
    REGISTER = 5
    INDIRECT_REGISTER = 2
    INDIRECT_INDEXED_REGISTER = 3
    INDIRECT_NUMERIC = 4

class Operand:
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
    def match_pattern(self) -> str:
        return ''

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> tuple[ByteCodePart, ByteCodePart]:
        # this should be overridden
        return None, None



