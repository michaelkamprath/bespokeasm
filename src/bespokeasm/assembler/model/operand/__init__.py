from __future__ import annotations

import enum
import sys
import warnings

from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class OperandType(enum.Enum):
    # these values double as sort order for processing in an operand set
    UNKNOWN = -1
    EMPTY = 1
    NUMERIC = 9
    NUMERIC_BYTECODE = 12
    REGISTER = 8
    INDEXED_REGISTER = 6
    DICTIONARY_KEY = 7
    INDIRECT_REGISTER = 2
    INDIRECT_INDEXED_REGISTER = 3
    INDIRECT_NUMERIC = 4
    DEFERRED_NUMERIC = 5
    ADDRESS = 10
    RELATIVE_ADDRESS = 11


class OperandBytecodePositionType(enum.Enum):
    PREFIX = 1
    SUFFIX = 2


class Operand:
    def __init__(
        self,
        operand_id,
        arg_config_dict,
        default_multi_word_endian,
        default_intra_word_endian,
        word_size,
        word_segment_size,
    ):
        self._id = operand_id
        self._config = arg_config_dict
        self._default_multi_word_endian = default_multi_word_endian
        self._default_intra_word_endian = default_intra_word_endian
        self._word_size = word_size
        self._word_segment_size = word_segment_size

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'Operand<{self.id}>'

    @property
    def config(self) -> dict:
        return self._config

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
    def bytecode_position(self) -> OperandBytecodePositionType:
        if self.has_bytecode:
            pos_str = self._config['bytecode'].get('position', 'suffix')
            if pos_str == 'suffix':
                return OperandBytecodePositionType.SUFFIX
            elif pos_str == 'prefix':
                return OperandBytecodePositionType.PREFIX
            else:
                sys.exit(f'ERROR - ISA configuration assigned operand "{self.id}" with unknown bytecode position "{pos_str}"')
        else:
            return None

    @property
    def match_pattern(self) -> str:
        return ''

    @property
    def operand_argument_string(self) -> str:
        sys.exit(f'ERROR: INTERNAL - tried to fetch operand argument string for an unsupported operand type: {self}')

    @property
    def operand_register_string(self) -> str:
        sys.exit(f'ERROR: INTERNAL - tried to fetch operand register string for an unsupported operand type: {self}')

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
        word_size: int,
        word_segment_size: int,
    ) -> ParsedOperand:
        # this should be overridden
        raise NotImplementedError


class OperandWithArgument(Operand):
    def __init__(
        self,
        operand_id,
        arg_config_dict,
        default_multi_word_endian,
        default_intra_word_endian,
        word_size,
        word_segment_size,
        require_arg: bool = True,
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
        )
        if require_arg and 'argument' not in self._config:
            sys.exit(f'ERROR: configuration for numeric operand {self} does not have an argument configuration')

    @property
    def has_argument(self) -> bool:
        return 'argument' in self._config

    @property
    def argument_size(self) -> int:
        """Returns the bytecode size of the argument for this operand. Must be configured."""
        if 'size' not in self._config['argument']:
            sys.exit(f'ERROR: Operand {self} does not have a configured argument size')
        return self._config['argument']['size']

    @property
    def argument_word_align(self) -> bool:
        if 'word_align' not in self._config['argument']:
            warnings.warn(
                f"The 'byte_align' option for argument configuration in operand configuration {self} is "
                f"deprecated and will be removed in a future version. Replace with 'word_align'.",
                DeprecationWarning,
                stacklevel=2
            )
            return self._config['argument']['byte_align']
        return self._config['argument']['word_align']

    @property
    def argument_endian(self) -> str:
        warnings.warn(
            f"The 'endian' option for argument configuration in operand configuration {self} is "
            f'deprecated and will be removed in a future version. '
            f"Replace with 'multi_word_endian' and 'intra_word_endian'.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.argument_multi_word_endian

    @property
    def argument_multi_word_endian(self) -> str:
        return self._config['argument'].get('multi_word_endian', self._default_multi_word_endian)

    @property
    def argument_intra_word_endian(self) -> str:
        """Returns the endianess of the argument for this operand. Defaults to the configured default endian."""
        return self._config['argument'].get('intra_word_endian', self._default_intra_word_endian)


class ParsedOperand:
    '''A structure class to contain the results of a operand parsing.'''
    def __init__(
        self,
        operand: Operand,
        bytecode: ByteCodePart,
        argument: ByteCodePart,
        operand_str: str,
        word_size: int,
        word_segment_size: int,
    ):
        self._operand = operand
        self._bytecode = bytecode
        self._argument = argument
        self._operand_str = operand_str
        self._word_size = word_size
        self._word_segment_size = word_segment_size

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'ParsedOperand<{self.operand},{self.bytecode},{self.argument}>'

    @property
    def operand(self) -> Operand:
        return self._operand

    @property
    def operand_id(self) -> str:
        return self.operand.id

    @property
    def bytecode(self) -> ByteCodePart:
        return self._bytecode

    @property
    def argument(self) -> ByteCodePart:
        return self._argument

    @property
    def operand_string(self) -> str:
        return self._operand_str

    @property
    def operand_argument_string(self) -> str:
        if self.argument is None:
            return None
        return self.argument.instruction_string

    @property
    def operand_register_string(self) -> str:
        if self.operand is None:
            return None
        return self.operand.operand_register_string
