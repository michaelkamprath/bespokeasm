from __future__ import annotations

import enum

from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.diagnostic_reporter import InternalAssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.utilities import DEFAULT_ENCLOSURE
from bespokeasm.utilities import ENCLOSURES


class OperandType(enum.Enum):
    # these values double as sort order for processing in an operand set
    UNKNOWN = -1
    EMPTY = 1
    NUMERIC = 10
    NUMERIC_BYTECODE = 13
    REGISTER = 9
    INDEXED_REGISTER = 7
    DICTIONARY_KEY = 8
    INDIRECT_REGISTER = 2
    INDIRECT_INDEXED_REGISTER = 3
    INDIRECT_NUMERIC = 4
    INDIRECT_INDEXED_NUMERIC = 5
    DEFERRED_NUMERIC = 6
    ADDRESS = 11
    RELATIVE_ADDRESS = 12


class OperandBytecodePositionType(enum.Enum):
    PREFIX = 1
    SUFFIX = 2


# An enclosure and a depth, as ('parentheses', 1) for `(vec)` or ('brackets', 2) for `[[vec]]`.
EnclosureRequirement = tuple[str, int]


def allowed_by_enclosure(operand: Operand, requirement: EnclosureRequirement | None) -> bool:
    """Whether ``operand`` may take source text that must be read as ``requirement``.

    When an instruction configures an enclosed form at an operand position, an operand there
    wrapped wholly in that enclosure is that form: `lda ($10)` can't be `lda $10` when `lda`
    has a `( )` form. An enclosed operand takes only text in its own enclosure, and registers
    and enumeration keys never match a parenthesized operand, so the depth alone decides."""
    return requirement is None or operand.enclosure_depth >= requirement[1]


class Operand:
    def __init__(
        self,
        operand_id,
        arg_config_dict,
        default_multi_word_endian,
        default_intra_word_endian,
        word_size,
        word_segment_size,
        diagnostic_reporter: DiagnosticReporter,
    ):
        if diagnostic_reporter is None:
            raise ValueError('DiagnosticReporter is required for Operand construction')
        self._id = operand_id
        self._config = arg_config_dict
        self._default_multi_word_endian = default_multi_word_endian
        self._default_intra_word_endian = default_intra_word_endian
        self._default_numeric_base = 'decimal'
        self._word_size = word_size
        self._word_segment_size = word_segment_size
        self._diagnostic_reporter = diagnostic_reporter

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
    def default_numeric_base(self) -> str:
        return self._default_numeric_base

    @default_numeric_base.setter
    def default_numeric_base(self, value: str):
        self._default_numeric_base = value

    @property
    def null_operand(self) -> bool:
        '''Indicates whether this operand object expects a non-empty string to be parsed.'''
        return False

    @property
    def enclosure(self) -> str:
        '''What the operand is written in when it is indirect: `brackets` or `parentheses`.'''
        return self._config.get('enclosure', DEFAULT_ENCLOSURE)

    @property
    def enclosure_delimiters(self) -> tuple[str, str]:
        return ENCLOSURES[self.enclosure]

    @property
    def enclosure_depth(self) -> int:
        '''How many pairs of its enclosure wrap the operand in source: 1 for an indirect operand
        such as `[vec]` or an enclosed relative address such as `{label}`, 2 for a deferred one
        such as `[[vec]]`, and 0 for a bare operand.'''
        return 0

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
        # Suffix unless the operand's own bytecode says otherwise. An operand without bytecode of
        # its own can still emit some from its index operands, as `[hl + a]` can.
        if self.has_bytecode:
            pos_str = self._config['bytecode'].get('position', 'suffix')
            if pos_str == 'suffix':
                return OperandBytecodePositionType.SUFFIX
            elif pos_str == 'prefix':
                return OperandBytecodePositionType.PREFIX
            else:
                raise AssemblerError(
                    None,
                    f'ISA configuration assigned operand "{self.id}" with unknown bytecode position "{pos_str}"',
                )
        return OperandBytecodePositionType.SUFFIX

    @property
    def match_pattern(self) -> str:
        return ''

    @property
    def operand_argument_string(self) -> str:
        raise InternalAssemblerError(None, f'tried to fetch operand argument string for an unsupported operand type: {self}')

    @property
    def operand_register_string(self) -> str:
        raise InternalAssemblerError(None, f'tried to fetch operand register string for an unsupported operand type: {self}')

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
        diagnostic_reporter: DiagnosticReporter,
        require_arg: bool = True,
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
            diagnostic_reporter,
        )
        if require_arg and 'argument' not in self._config:
            diagnostic_reporter.error(
                None,
                f'configuration for numeric operand {self} does not have an argument configuration',
            )

    @property
    def has_argument(self) -> bool:
        return 'argument' in self._config

    @property
    def argument_size(self) -> int:
        """Returns the bytecode size of the argument for this operand. Must be configured."""
        if 'size' not in self._config['argument']:
            raise AssemblerError(None, f'Operand {self} does not have a configured argument size')
        return self._config['argument']['size']

    @property
    def argument_word_align(self) -> bool:
        if 'word_align' not in self._config['argument']:
            raise AssemblerError(None, f'Operand {self} does not have a configured argument word_align setting')
        return self._config['argument']['word_align']

    @property
    def argument_endian(self) -> str:
        self._diagnostic_reporter.warn(
            None,
            f"The 'endian' option for argument configuration in operand configuration {self} is "
            f'deprecated and will be removed in a future version. '
            f"Replace with 'multi_word_endian' and 'intra_word_endian'.",
            category='deprecation',
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
        operand_label: str | None = None,
        trailing_arguments: list[ByteCodePart] | None = None,
    ):
        self._operand = operand
        self._bytecode = bytecode
        self._argument = argument
        # Arguments emitted after `argument`, such as the offset of an indirect_indexed_numeric
        # operand's index. `argument` stays the operand's value for operand labels and `@ARG`.
        self._trailing_arguments = trailing_arguments or []
        self._operand_str = operand_str
        self._word_size = word_size
        self._word_segment_size = word_segment_size
        self._operand_label = operand_label

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
    def arguments(self) -> list[ByteCodePart]:
        """Every argument the operand emits, in order."""
        return ([self._argument] if self._argument is not None else []) + self._trailing_arguments

    @property
    def operand_string(self) -> str:
        return self._operand_str

    @property
    def operand_label(self) -> str | None:
        return self._operand_label

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
