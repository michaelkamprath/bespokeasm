import re
import sys
from functools import cached_property

from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePart
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import ParsedOperand

from .register import RegisterOperand


class IndirectRegisterOperand(RegisterOperand):
    _BASE_PATTERN_TEMPLATE = r'\[\s*({0})\s*(?:(\+|\-)\s*([\s\w\+\-\*\/\&\|\^\(\)\$\%]+)\s*)?\]'

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
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            regsiters,
            word_size,
            word_segment_size,
            diagnostic_reporter,
        )
        self._parse_pattern = re.compile(
            fr'^{self.match_pattern}$',
            flags=re.IGNORECASE | re.MULTILINE
        )
        if self.has_offset:
            if 'size' not in self._config['offset']:
                sys.exit(
                    f'ERROR - configuration for indirect register operand "{self.register}" is '
                    f'missing "size" setting.'
                )
            if 'word_align' not in self._config['offset']:
                sys.exit(
                    f'ERROR - configuration for indirect register operand "{self.register}" is '
                    f'missing "word_align" setting.'
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
    def offset_word_align(self) -> bool:
        return self._config['offset']['word_align']

    @property
    def offset_multi_word_endian(self) -> str:
        return self._config['offset'].get('multi_word_endian', self._default_multi_word_endian)

    @property
    def offset_intra_word_endian(self) -> str:
        return self._config['offset'].get('intra_word_endian', self._default_intra_word_endian)

    @cached_property
    def match_pattern(self) -> str:
        if not self.has_decorator:
            pattern_str = IndirectRegisterOperand._BASE_PATTERN_TEMPLATE.format(self.register)
        elif self.decorator_is_prefix:
            pattern_str = r'(?<!(?:\+|\-|\d|\w)){}{}'.format(
                self.decorator_pattern,
                IndirectRegisterOperand._BASE_PATTERN_TEMPLATE.format(self.register),
            )
        else:
            pattern_str = r'{}{}(?!(?:\+|\-|\d|\w))'.format(
                IndirectRegisterOperand._BASE_PATTERN_TEMPLATE.format(self.register),
                self.decorator_pattern,
            )
        return fr'{pattern_str}'

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        match = re.match(
            self._parse_pattern,
            operand.strip(),
        )
        if match is not None and len(match.groups()) > 0:
            bytecode_part = NumericByteCodePart(
                self.bytecode_value,
                self.bytecode_size,
                False,
                'big',
                'big',
                line_id,
                self._word_size,
                self._word_segment_size,
            ) if self.bytecode_value is not None else None
            if self.has_offset:
                if len(match.groups()) == 3 and match.group(2) is not None and match.group(3) is not None:
                    # we have an offset argument. construct the offset expression. Group 2 is the + or -
                    # sign, and our expression parser expects 2 operands for the + or - sign
                    if match.group(2).strip() == '-':
                        argument_str = f'0 {match.group(2).strip()} {match.group(3).strip()}'
                    else:
                        argument_str = match.group(3).strip()
                    arg_part = ExpressionByteCodePart(
                        argument_str,
                        self.offset_size,
                        self.offset_word_align,
                        self.offset_multi_word_endian,
                        self.offset_intra_word_endian,
                        line_id,
                        self._word_size,
                        self._word_segment_size,
                    )
                    # now test that is is a numeric expression. If not, return nothing
                    if arg_part.contains_register_labels(register_labels):
                        return None
                else:
                    # must have and offset value of 0
                    arg_part = NumericByteCodePart(
                        0,
                        self.offset_size,
                        self.offset_word_align,
                        self.offset_multi_word_endian,
                        self.offset_intra_word_endian,
                        line_id,
                        self._word_size,
                        self._word_segment_size,
                    )
            else:
                if len(match.groups()) == 3 and match.group(2) is not None and match.group(3) is not None:
                    # and offset was added for an operand that wasn't configured to have one. Error.
                    sys.exit(
                        f'ERROR: {line_id} - An offset was provided for indirect register operand "{operand}" '
                        f'when none was expected.'
                    )
                arg_part = None
            return ParsedOperand(self, bytecode_part, arg_part, operand, self._word_size, self._word_segment_size)
        else:
            return None
