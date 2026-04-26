import re
import sys

from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.decorators import get_decorator_regex_pattern
from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import ParsedOperand


class RegisterOperand(Operand):
    _OPERAND_PATTERN_TEMPLATE = r'{0}{1}'

    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        regsiters: set[str],
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
    ):
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
            diagnostic_reporter,
        )
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
    def operand_register_string(self) -> str:
        return self.register

    @property
    def has_decorator(self) -> bool:
        return 'decorator' in self._config

    @property
    def decorator_pattern(self) -> str:
        if self.has_decorator:
            return get_decorator_regex_pattern(
                self._config['decorator'],
                context=(
                    f'ISA configation declares register based operand "{self.id}" '
                    f'for register "{self.register}"'
                ),
            )
        return ''

    @property
    def decorator_is_prefix(self) -> bool:
        if self.has_decorator:
            return self._config['decorator'].get('is_prefix', False)
        return False

    @property
    def match_pattern(self) -> str:
        if not self.has_decorator:
            return fr'\b{self.register}\b'
        elif self.decorator_is_prefix:
            return fr'(?<!(?:\+|\-|\d|\w)){self.decorator_pattern}{self.register}\b'
        else:
            return fr'\b{self.register}{self.decorator_pattern}(?!(?:\+|\-|\d|\w))'

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        match = re.match(
            fr'^{self.match_pattern}$',
            operand.strip(),
            flags=re.IGNORECASE,
        )
        if match is not None:
            bytecode_part = NumericByteCodePart(
                self.bytecode_value,
                self.bytecode_size,
                False,
                self._default_multi_word_endian,
                self._default_intra_word_endian,
                line_id,
                self._word_size,
                self._word_segment_size,
            ) if self.bytecode_value is not None else None
            arg_part = None
            return ParsedOperand(
                self,
                bytecode_part,
                arg_part,
                operand,
                self._word_size,
                self._word_segment_size,
            )
        return None
