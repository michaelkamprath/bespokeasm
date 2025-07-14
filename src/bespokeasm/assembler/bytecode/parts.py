from __future__ import annotations
from functools import reduce
import sys
from typing import Literal

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.expression import parse_expression
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.bytecode.word_slice import WordSlice
from bespokeasm.assembler.bytecode.value import Value

from .packed_bits import PackedBits


class ByteCodePart:
    def __init__(
        self,
        value_size: int,
        word_align: bool,
        endian: Literal['little', 'big'],
        line_id: LineIdentifier,
        word_size: int,
        segment_size: int,
    ) -> None:
        self._value_size = value_size
        self._word_align = word_align
        self._endian = endian
        self._line_id = line_id
        self._word_size = word_size
        self._segment_size = segment_size

        # Determine whether to use WordSlice or Value based on value_size and word_size
        if value_size < word_size:
            # Use WordSlice for small values
            self._representation_type = 'word_slice'
        elif value_size > word_size and value_size % word_size == 0:
            # Use Value for large values that are multiples of word_size
            self._representation_type = 'value'
        else:
            # Use Word for values that don't fit the above criteria
            self._representation_type = 'word'

    @property
    def value_size(self) -> int:
        return self._value_size

    @property
    def word_align(self) -> bool:
        return self._word_align

    @property
    def endian(self) -> str:
        return self._endian

    @property
    def line_id(self) -> LineIdentifier:
        return self._line_id

    @property
    def word_size(self) -> int:
        return self._word_size

    @property
    def segment_size(self) -> int:
        return self._segment_size

    @property
    def representation_type(self) -> Literal['word_slice', 'word', 'value']:
        return self._representation_type

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        raise NotImplementedError

    def __eq__(self, other: ByteCodePart) -> bool:
        return \
            self._value_size == other._value_size \
            and self._word_align == other._word_align \
            and self._endian == other._endian \
            and self._word_size == other._word_size \
            and self._segment_size == other._segment_size

    @property
    def instruction_string(self) -> str:
        sys.exit(f'ERROR: INTERNAL - fetching ByteCodePart instruction string unimplemented for: {self}')

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        # this should be overridden
        raise NotImplementedError

    def word_slice(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> WordSlice:
        return WordSlice(
            self.get_value(label_scope, instruction_address, instruction_size),
            self._value_size,
        )

    def get_words(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> list:
        value = Value.from_word_slices(
            [self.word_slice(label_scope, instruction_address, instruction_size)],
            self._word_size,
            self._segment_size,
            self._endian,
            self._endian
        )
        return value.words

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        return False


class NumericByteCodePart(ByteCodePart):
    def __init__(
                self,
                value: int,
                value_size: int,
                word_align: bool,
                endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        super().__init__(value_size, word_align, endian, line_id, word_size, segment_size)
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
        word_align: bool,
        endian: Literal['little', 'big'],
        line_id: LineIdentifier,
        word_size: int,
        segment_size: int,
    ) -> None:
        super().__init__(value_size, word_align, endian, line_id, word_size, segment_size)
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
                word_align: bool,
                endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        super().__init__(value_expression, value_size, word_align, endian, line_id, word_size, segment_size)
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
        word_align: bool,
        endian: Literal['little', 'big'],
        line_id: LineIdentifier,
        word_size: int,
        segment_size: int,
    ) -> None:
        super().__init__(value_expression, value_size, word_align, endian, line_id, word_size, segment_size)
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
                word_align: bool,
                endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        super().__init__(value_expression, value_size, word_align, endian, line_id, word_size, segment_size)
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

    def __init__(
                self,
                bytecode_parts: list[ByteCodePart],
                word_align: bool,
                endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        total_size = reduce(lambda a, b: a+b.value_size, bytecode_parts, 0)
        super().__init__(total_size, word_align, endian, line_id, word_size, segment_size)
        self._parts_list = bytecode_parts

        # Validate that all Value-based ByteCodePart objects have consistent word and segment sizes
        self._validate_value_consistency()

    def _validate_value_consistency(self):
        """Validate that all Value-based ByteCodePart objects have consistent word and segment sizes."""
        for part in self._parts_list:
            if part.word_size != self.word_size:
                sys.exit(
                    f'ERROR: {self.line_id} - Value-based ByteCodePart has word_size {part.word_size}, '
                    f'expected {self.word_size}'
                )
            if part.segment_size != self.segment_size:
                sys.exit(
                    f'ERROR: {self.line_id} - Value-based ByteCodePart has segment_size {part.segment_size}, '
                    f'expected {self.segment_size}'
                )

    def __str__(self) -> str:
        return f'CompositeByteCodePart<parts="{self._parts_list}">'

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

    def get_words(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> list[Word]:
        """
        Returns a list of Word objects representing the composite bytecode part.
        Implements compaction rules for WordSlices and Values.
        """
        words = []
        current_word_slices = []
        current_bit_position = 0

        for part in self._parts_list:
            if isinstance(part, CompositeByteCodePart):
                # Flush any accumulated WordSlices before processing composite part
                if current_word_slices:
                    # Pack accumulated WordSlices into a single word if they fit
                    total_bits = sum(slice_obj.bit_size for slice_obj in current_word_slices)
                    if total_bits <= 8:
                        # Pack into a single byte
                        packed_value = 0
                        bit_position = 7  # Start from MSB
                        for slice_obj in current_word_slices:
                            slice_bits = slice_obj.get_raw_bits()
                            for i in range(slice_obj.bit_size - 1, -1, -1):
                                if (slice_bits >> i) & 1:
                                    packed_value |= (1 << bit_position)
                                bit_position -= 1
                        words.append(Word(packed_value, 8, 8, self.endian))
                    else:
                        # Use Value for larger combinations
                        new_value = Value.from_word_slices(
                            current_word_slices,
                            self.word_size,
                            self.segment_size,
                            self.endian,
                            self.endian
                        )
                        words.extend(new_value.words)
                    current_word_slices = []
                    current_bit_position = 0

                words.extend(part.get_words(label_scope, instruction_address, instruction_size))
            else:
                part_slice = part.word_slice(label_scope, instruction_address, instruction_size)

                if part.word_align:
                    # Flush accumulated WordSlices before word-aligned part
                    if current_word_slices:
                        # Pack accumulated WordSlices into a single word if they fit
                        total_bits = sum(slice_obj.bit_size for slice_obj in current_word_slices)
                        if total_bits <= 8:
                            # Pack into a single byte
                            packed_value = 0
                            bit_position = 7  # Start from MSB
                            for slice_obj in current_word_slices:
                                slice_bits = slice_obj.get_raw_bits()
                                for i in range(slice_obj.bit_size - 1, -1, -1):
                                    if (slice_bits >> i) & 1:
                                        packed_value |= (1 << bit_position)
                                    bit_position -= 1
                            words.append(Word(packed_value, 8, 8, self.endian))
                        else:
                            # Use Value for larger combinations
                            new_value = Value.from_word_slices(
                                current_word_slices,
                                self.word_size,
                                self.segment_size,
                                self.endian,
                                self.endian
                            )
                            words.extend(new_value.words)
                        current_word_slices = []
                        current_bit_position = 0

                    # Add padding if needed to align to byte boundary
                    if current_bit_position % 8 != 0:
                        padding_bits = 8 - (current_bit_position % 8)
                        padding_slice = WordSlice(0, padding_bits)
                        current_word_slices.append(padding_slice)
                        current_bit_position += padding_bits

                    # Add the word-aligned part
                    current_word_slices.append(part_slice)
                    current_bit_position += part_slice.bit_size
                else:
                    # Non-aligned part, just add to current accumulation
                    current_word_slices.append(part_slice)
                    current_bit_position += part_slice.bit_size

        # Flush any remaining word slices
        if current_word_slices:
            # Pack accumulated WordSlices into a single word if they fit
            total_bits = sum(slice_obj.bit_size for slice_obj in current_word_slices)
            if total_bits <= 8:
                # Pack into a single byte
                packed_value = 0
                bit_position = 7  # Start from MSB
                for slice_obj in current_word_slices:
                    slice_bits = slice_obj.get_raw_bits()
                    for i in range(slice_obj.bit_size - 1, -1, -1):
                        if (slice_bits >> i) & 1:
                            packed_value |= (1 << bit_position)
                        bit_position -= 1
                words.append(Word(packed_value, 8, 8, self.endian))
            else:
                # Use Value for larger combinations
                new_value = Value.from_word_slices(
                    current_word_slices,
                    self.word_size,
                    self.segment_size,
                    self.endian,
                    self.endian
                )
                words.extend(new_value.words)

        return words
