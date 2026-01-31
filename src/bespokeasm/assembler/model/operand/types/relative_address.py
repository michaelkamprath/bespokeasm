import re
import sys
from functools import cached_property

from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePartInMemoryZone
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import OperandWithArgument
from bespokeasm.assembler.model.operand import ParsedOperand
from bespokeasm.expression import EXPRESSION_PARTS_PATTERN


class RelativeAddressByteCodePart(ExpressionByteCodePartInMemoryZone):
    def __init__(
                self,
                value_expression: str,
                value_size: int,
                byte_align: bool,
                multi_word_endian: str,
                intra_word_endian: str,
                line_id: LineIdentifier,
                min_relative_value: int,
                max_relative_value: int,
                memzone: MemoryZone,
                offset_from_instruction_end: bool,
                word_size: int,
                word_segment_size: int,
            ) -> None:
        super().__init__(
            memzone,
            value_expression,
            value_size,
            byte_align,
            multi_word_endian,
            intra_word_endian,
            line_id,
            word_size,
            word_segment_size,
        )
        self._min_relative_value = min_relative_value
        self._max_relative_value = max_relative_value
        self._offset_from_instruction_end = offset_from_instruction_end

    def get_value(
        self,
        label_scope: LabelScope,
        active_named_scopes: ActiveNamedScopeList,
        instruction_address: int,
        instruction_size: int,
    ) -> int:
        if instruction_address is None:
            raise ValueError('RelativeAddressByteCodePart.get_value had no instruction_address passed')
        expression_value = super().get_value(label_scope, active_named_scopes, instruction_address, instruction_size)
        relative_value = expression_value - instruction_address
        if self._offset_from_instruction_end:
            # minus one to account for the current address being 1 byte of instruction size
            relative_value -= instruction_size - 1
        if self._max_relative_value is not None and relative_value > self._max_relative_value:
            sys.exit(
                f'ERROR: {self.line_id} - Relative address offset is larger than configured '
                f'maximum value of {self._max_relative_value}'
            )
        if self._min_relative_value is not None and relative_value < self._min_relative_value:
            sys.exit(
                f'ERROR: {self.line_id} - Relative address offset is smaller than configured '
                f'minimum value of {self._min_relative_value}'
            )
        return relative_value


class RelativeAddressOperand(OperandWithArgument):
    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
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
            require_arg=require_arg,
        )

    def __str__(self):
        return f'RelativeAddressOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.RELATIVE_ADDRESS

    @cached_property
    def match_pattern(self) -> str:
        base_match_str = fr'((?:{EXPRESSION_PARTS_PATTERN}|\s)+)'
        if self.uses_curly_braces:
            return fr'\{{\s*{base_match_str}\s*\}}'
        else:
            return base_match_str

    @property
    def uses_curly_braces(self) -> bool:
        return self.config.get('use_curly_braces', False)

    @property
    def max_offset(self) -> int:
        return self.config['argument'].get('max', None)

    @property
    def min_offset(self) -> int:
        return self.config['argument'].get('min', None)

    @property
    def offset_from_instruction_end(self) -> bool:
        return self.config.get('offset_from_instruction_end', False)

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # find argument per the required pattern
        match = re.match(self.match_pattern, operand.strip())
        if match is None or len(match.groups()) != 1:
            return None
        # do not match if expression contains square bracks
        if '[' in operand or ']' in operand:
            return None
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
        arg_part = RelativeAddressByteCodePart(
            match.group(1).strip(),
            self.argument_size,
            self.argument_word_align,
            self.argument_multi_word_endian,
            self.argument_intra_word_endian,
            line_id,
            self.min_offset,
            self.max_offset,
            memzone_manager.global_zone,
            self.offset_from_instruction_end,
            self._word_size,
            self._word_segment_size,
        )
        if arg_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, arg_part, operand, self._word_size, self._word_segment_size)
