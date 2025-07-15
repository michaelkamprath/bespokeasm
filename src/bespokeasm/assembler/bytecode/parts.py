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
        multi_word_endian: Literal['little', 'big'],
        intra_word_endian: Literal['little', 'big'],
        line_id: LineIdentifier,
        word_size: int,
        segment_size: int,
    ) -> None:
        self._value_size = value_size
        self._word_align = word_align
        self._multi_word_endian = multi_word_endian
        self._intra_word_endian = intra_word_endian
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
    def multi_word_endian(self) -> Literal['little', 'big']:
        return self._multi_word_endian

    @property
    def intra_word_endian(self) -> Literal['little', 'big']:
        return self._intra_word_endian

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

    def get_value_representation(
        self,
        label_scope: LabelScope,
        instruction_address: int,
        instruction_size: int,
    ) -> WordSlice | Value:
        return WordSlice(
            self.get_value(label_scope, instruction_address, instruction_size),
            self._value_size,
        )

    def get_words(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> list[Word]:
        value_representation = self.get_value_representation(label_scope, instruction_address, instruction_size)
        if isinstance(value_representation, WordSlice):
            return [
                Word.from_word_slices(
                    [value_representation],
                    self._word_size,
                    self._segment_size,
                    self._intra_word_endian,
                )
            ]
        elif isinstance(value_representation, Value):
            return value_representation.get_words_ordered()
        else:
            sys.exit(
                f'ERROR: INTERNAL - get_words received unexpected value representation type: {type(value_representation)}'
            )

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        return False

    @classmethod
    def compact_parts_to_words(
        cls,
        parts: list[ByteCodePart],
        word_size: int,
        segment_size: int,
        multi_word_endianness: Literal['little', 'big'],
        label_scope: LabelScope,
        instruction_address: int,
        instruction_size: int,
    ) -> list[Word]:
        """
        Compact a list of ByteCodePart objects into a list of Word objects.
        The rules of compaction are:
        - A ByteCodePart is represented by either a WordSlice or a Value and is processed
          in the order they are encountered
        - Consecutive WordSlices are packed into a single value until a ByteCodePart is encountered
          that is either word-aligned or a Value
        - Values are then emitted as a list of Word objects
        - The final list of Word objects is returned
        """
        words = []
        current_word_slices: list[(WordSlice, Literal['little', 'big'])] = []
        # current_bit_position = 0

        def flush_word_slices(
            word_size: int,
            segment_size: int,
            multi_word_endianness: Literal['little', 'big'],
        ) -> list[Word]:
            nonlocal current_word_slices
            result = []
            if current_word_slices:
                total_bits = sum(slice_obj.bit_size for (slice_obj, _) in current_word_slices)
                first_endian = current_word_slices[0][1]
                packed_value = 0
                for slice_obj, _ in current_word_slices:
                    packed_value = (packed_value << slice_obj.bit_size) | slice_obj.get_raw_bits()
                num_words = (total_bits + word_size - 1) // word_size
                for i in range(num_words):
                    bits_left = total_bits - i * word_size
                    if bits_left >= word_size:
                        shift = bits_left - word_size
                        word_bits = (packed_value >> shift) & ((1 << word_size) - 1)
                    else:
                        # Fewer than word_size bits left, left-align them
                        word_bits = (packed_value & ((1 << bits_left) - 1)) << (word_size - bits_left)
                    result.append(Word(word_bits, word_size, segment_size, first_endian))
                current_word_slices = []
            return result

        for part in parts:
            if isinstance(part, CompositeByteCodePart):
                # if the CompositeByteCodePart is word-aligned, then we flush the word slices and
                # add the part's words. Otherwise, we get the WordSlice from the part.
                if part.word_align:
                    if current_word_slices:
                        words.extend(flush_word_slices(word_size, segment_size, multi_word_endianness))
                    words.extend(part.get_words(label_scope, instruction_address, instruction_size))
                else:
                    value_representation = part.get_value_representation(label_scope, instruction_address, instruction_size)
                    if isinstance(value_representation, WordSlice):
                        current_word_slices.append((value_representation, part.intra_word_endian))
                    else:
                        # this should never happen
                        sys.exit(
                            f'ERROR: INTERNAL - CompositeByteCodePart received Value representation: {value_representation}'
                        )
            else:
                value_representation = part.get_value_representation(label_scope, instruction_address, instruction_size)
                if isinstance(value_representation, WordSlice):
                    if part.word_align:
                        # Flush accumulated WordSlices before word-aligned part
                        if current_word_slices:
                            words.extend(flush_word_slices(word_size, segment_size, multi_word_endianness))
                    if value_representation.bit_size % word_size == 0:
                        value = Value.from_word_slices(
                            [value_representation],
                            word_size,
                            segment_size,
                            part.multi_word_endian,
                            part.intra_word_endian,
                        )
                        words.extend(value.get_words_ordered())
                    else:
                        current_word_slices.append((value_representation, part.intra_word_endian))
                elif isinstance(value_representation, Value):
                    # Flush accumulated WordSlices before Values
                    if current_word_slices:
                        words.extend(flush_word_slices(word_size, segment_size, multi_word_endianness))
                    words.extend(value_representation.get_words_ordered())

        # Flush any remaining word slices
        if current_word_slices:
            words.extend(flush_word_slices(word_size, segment_size, multi_word_endianness))

        return words


class NumericByteCodePart(ByteCodePart):
    def __init__(
                self,
                value: int,
                value_size: int,
                word_align: bool,
                multi_word_endian: Literal['little', 'big'],
                intra_word_endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        super().__init__(value_size, word_align, multi_word_endian, intra_word_endian, line_id, word_size, segment_size)
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
        multi_word_endian: Literal['little', 'big'],
        intra_word_endian: Literal['little', 'big'],
        line_id: LineIdentifier,
        word_size: int,
        segment_size: int,
    ) -> None:
        super().__init__(
            value_size,
            word_align,
            multi_word_endian,
            intra_word_endian,
            line_id,
            word_size,
            segment_size,
        )
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
                multi_word_endian: Literal['little', 'big'],
                intra_word_endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        super().__init__(
            value_expression,
            value_size,
            word_align,
            multi_word_endian,
            intra_word_endian,
            line_id,
            word_size,
            segment_size,
        )
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
        multi_word_endian: Literal['little', 'big'],
        intra_word_endian: Literal['little', 'big'],
        line_id: LineIdentifier,
        word_size: int,
        segment_size: int,
    ) -> None:
        super().__init__(
            value_expression,
            value_size,
            word_align,
            multi_word_endian,
            intra_word_endian,
            line_id,
            word_size,
            segment_size,
        )
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
                multi_word_endian: Literal['little', 'big'],
                intra_word_endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        super().__init__(
            value_expression,
            value_size,
            word_align,
            multi_word_endian,
            intra_word_endian,
            line_id,
            word_size,
            segment_size,
        )
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
                multi_word_endian: Literal['little', 'big'],
                intra_word_endian: Literal['little', 'big'],
                line_id: LineIdentifier,
                word_size: int,
                segment_size: int,
            ) -> None:
        total_size = reduce(lambda a, b: a+b.value_size, bytecode_parts, 0)
        super().__init__(total_size, word_align, multi_word_endian, intra_word_endian, line_id, word_size, segment_size)
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
            )
        value = int.from_bytes(bits.get_bytes(), 'big')
        if self.value_size % self.word_size != 0:
            shift_count = self.word_size - (self.value_size % self.word_size)
            value = value >> shift_count
        return value

    def get_value_representation(
        self,
        label_scope: LabelScope,
        instruction_address: int,
        instruction_size: int,
    ) -> WordSlice | Value:
        '''
        For a CompositeByteCodePart, we will return a compacted WordSlice based on the compacted value
        '''
        return WordSlice(
            self.get_value(label_scope, instruction_address, instruction_size),
            self.value_size,
        )

    def get_words(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> list[Word]:
        """
        Returns a list of Word objects representing the composite bytecode part.
        Implements compaction rules for WordSlices and Values.
        """
        return ByteCodePart.compact_parts_to_words(
            self._parts_list,
            self.word_size,
            self.segment_size,
            self.endian,
            label_scope,
            instruction_address,
            instruction_size,
        )
