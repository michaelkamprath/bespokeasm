from __future__ import annotations
from functools import reduce
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.expression import parse_expression

from .packed_bits import PackedBits


class ByteCodePart:
    def __init__(self, value_size: int, byte_align: bool, endian: str, line_id: LineIdentifier) -> None:
        self._value_size = value_size
        self._byte_align = byte_align
        self._endian = endian
        self._line_id = line_id

    @property
    def value_size(self) -> int:
        return self._value_size

    @property
    def byte_align(self) -> bool:
        return self._byte_align

    @property
    def endian(self) -> str:
        return self._endian

    @property
    def line_id(self) -> LineIdentifier:
        return self._line_id

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        raise NotImplementedError

    def __eq__(self, other: ByteCodePart) -> bool:
        return \
            self._value_size == other._value_size \
            and self._byte_align == other._byte_align \
            and self._endian == other._endian

    @property
    def instruction_string(self) -> str:
        sys.exit(f'ERROR: INTERNAL - fetching ByteCodePart instruction string unimplemented for: {self}')

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        # this should be overridden
        raise NotImplementedError

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        return False


class NumericByteCodePart(ByteCodePart):
    def __init__(self, value: int, value_size: int, byte_align: bool, endian: str, line_id: LineIdentifier) -> None:
        super().__init__(value_size, byte_align, endian, line_id)
        self._value = value

    @property
    def instruction_string(self) -> str:
        return str(self._value)

    def __str__(self) -> str:
        return f'NumericByteCodePart<value={self._value},size={self.value_size}>'

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        return self._value


class ExpressionByteCodePart(ByteCodePart):
    def __init__(
        self,
        value_expression: str,
        value_size: int,
        byte_align: bool,
        endian: str,
        line_id: LineIdentifier,
    ) -> None:
        super().__init__(value_size, byte_align, endian, line_id)
        self._expression = value_expression
        self._parsed_expression = parse_expression(self.line_id, self._expression)

    @property
    def instruction_string(self) -> str:
        return self._expression.strip()

    def __str__(self) -> str:
        return f'ExpressionByteCodePart<expression="{self._expression}",size={self.value_size}>'

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        value = self._parsed_expression.get_value(label_scope, self.line_id)
        if isinstance(value, str):
            sys.exit(f'ERROR: {self.line_id} - expression "{self._expression}" did not resolve to an int, got: {value}')
        return value

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        return self._parsed_expression.contains_register_labels(register_labels)


class ExpressionByteCodePartWithValidation(ExpressionByteCodePart):
    def __init__(
                self,
                max_value: int,
                min_value: int,
                value_expression: str,
                value_size: int,
                byte_align: bool,
                endian: str,
                line_id: LineIdentifier
            ) -> None:
        super().__init__(value_expression, value_size, byte_align, endian, line_id)
        self._max = max_value
        self._min = min_value

    def __str__(self) -> str:
        return f'ExpressionByteCodePartWithValidation<expression="{self._expression}",max={self._max},min={self._min}>'

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        value = super().get_value(label_scope, instruction_address, instruction_size)
        if self._max is not None and value > self._max:
            sys.exit(f'ERROR: {self.line_id} - operand value of {value} exceeds maximun allowed of {self._max}')
        if self._min is not None and value < self._min:
            sys.exit(f'ERROR: {self.line_id} - operand value of {value} is less than minimum allowed of {self._min}')
        return value


class ExpressionByteCodePartInMemoryZone(ExpressionByteCodePart):
    def __init__(
        self,
        memzone: MemoryZone,
        value_expression: str,
        value_size: int,
        byte_align: bool,
        endian: str,
        line_id: LineIdentifier,
    ) -> None:
        super().__init__(value_expression, value_size, byte_align, endian, line_id)
        self._memzone = memzone

    def __str__(self) -> str:
        return f'ExpressionByteCodePartInMemoryZone<expression="{self._expression}",zone={self._memzone}>'

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        value = super().get_value(label_scope, instruction_address, instruction_size)
        if self._memzone is not None:
            if value > self._memzone.end:
                sys.exit(
                    f'ERROR: {self.line_id} - address value of {value} exceeds maximun allowed '
                    f'address of {self._memzone.end} in memory zone {self._memzone.name}'
                )
            if value < self._memzone.start:
                sys.exit(
                    f'ERROR: {self.line_id} - address value of {value} is less than minimum allowed '
                    f'address of {self._memzone.start} in memory zone {self._memzone.name}'
                )
        return value


class ExpressionEnumerationByteCodePart(ExpressionByteCodePart):
    def __init__(
                self,
                value_dict: dict[int, int],
                value_expression: str,
                value_size: int,
                byte_align: bool,
                endian: str,
                line_id: LineIdentifier
            ) -> None:
        super().__init__(value_expression, value_size, byte_align, endian, line_id)
        self._value_dict = value_dict

    def __str__(self) -> str:
        return f'ExpressionEnumerationByteCodePart<expression="{self._expression}",value_dict={self._value_dict}>'

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        value = super().get_value(label_scope, instruction_address, instruction_size)
        if value not in self._value_dict:
            sys.exit(
                f'ERROR: {self.line_id} - numeric expression value of {value} is '
                f'not an allowed value for numeric enumeration.'
            )
        return self._value_dict[value]


class CompositeByteCodePart(ByteCodePart):
    _parts_list: list[ByteCodePart]

    def __init__(self, bytecode_parts: list[ByteCodePart], byte_align: bool, endian: str, line_id: LineIdentifier) -> None:
        total_size = reduce(lambda a, b: a+b.value_size, bytecode_parts, 0)
        super().__init__(total_size, byte_align, endian, line_id)
        self._parts_list = bytecode_parts

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        bits = PackedBits()
        for p in self._parts_list:
            bits.append_bits(
                p.get_value(
                    label_scope,
                    instruction_address,
                    instruction_size,
                ),
                p.value_size,
                False,
                self.endian,
            )
        value = int.from_bytes(bits.get_bytes(), self.endian)
        if self.value_size % 8 != 0:
            shift_count = 8 - (self.value_size % 8)
            value = value >> shift_count
        return value
