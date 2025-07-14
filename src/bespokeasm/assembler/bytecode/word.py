from typing import Literal
from .word_slice import WordSlice


class Word:
    """
    Represents a word in the bytecode. A word is the smallest unit a memory address points to.

    A Word has:
    - A bit size (total number of bits)
    - A segment size (size of segments within the word, must divide bit size evenly)
    - A value (integer value of the word)
    - Intra-word endianness ('big' or 'little') indicating segment order when emitting bytes

    Words can be constructed from:
    - A list of WordSlice objects (packed in order from MSB to LSB)
    - An integer value (if it fits within the bit size)
    """

    def __init__(
        self,
        value: int,
        bit_size: int,
        segment_size: int = 8,
        intra_word_endianness: Literal['little', 'big'] = 'big'
    ):
        """
        Initialize a Word with a value and bit size.

        :param value: The integer value of the word
        :param bit_size: The total number of bits in the word (must be > 0)
        :param segment_size: The size of segments within the word (must be > 0 and divide bit_size evenly)
        :param intra_word_endianness: The endianness of segments when converting to bytes
        :raises ValueError: If parameters are invalid or value doesn't fit in bit_size
        """
        if bit_size <= 0:
            raise ValueError('bit_size must be greater than 0')

        if segment_size <= 0:
            raise ValueError('segment_size must be greater than 0')

        if bit_size % segment_size != 0:
            raise ValueError(f'bit_size {bit_size} must be divisible by segment_size {segment_size}')

        if segment_size > bit_size:
            raise ValueError(f'segment_size {segment_size} cannot be greater than bit_size {bit_size}')

        # Calculate valid range for the given bit size
        min_value = -(1 << (bit_size - 1))  # -2^(bit_size-1) for signed
        max_value = (1 << bit_size) - 1  # 2^bit_size - 1 for unsigned

        if value < min_value or value > max_value:
            raise ValueError(f'value {value} is out of range for bit_size {bit_size} (range: {min_value} to {max_value})')

        if intra_word_endianness not in ['little', 'big']:
            raise ValueError('intra_word_endianness must be "little" or "big"')

        self._value = value
        self._bit_size = bit_size
        self._segment_size = segment_size
        self._intra_word_endianness = intra_word_endianness

    @classmethod
    def from_word_slices(
        cls,
        word_slices: list[WordSlice],
        bit_size: int,
        segment_size: int = 8,
        intra_word_endianness: Literal['little', 'big'] = 'big'
    ) -> 'Word':
        """
        Create a Word from a list of WordSlice objects.

        The WordSlices are packed in order from most significant bit to least significant bit.
        If the total bits from WordSlices is less than bit_size, the remaining bits are filled with 0.

        :param word_slices: List of WordSlice objects to pack into the word
        :param bit_size: The total number of bits in the word
        :param segment_size: The size of segments within the word
        :param intra_word_endianness: The endianness of segments when converting to bytes
        :return: A new Word object
        :raises ValueError: If parameters are invalid or total bits exceed bit_size
        """
        if bit_size <= 0:
            raise ValueError('bit_size must be greater than 0')

        if segment_size <= 0:
            raise ValueError('segment_size must be greater than 0')

        if bit_size % segment_size != 0:
            raise ValueError(f'bit_size {bit_size} must be divisible by segment_size {segment_size}')

        if segment_size > bit_size:
            raise ValueError(f'segment_size {segment_size} cannot be greater than bit_size {bit_size}')

        # Calculate total bits from WordSlices
        total_slice_bits = sum(slice_obj.bit_size for slice_obj in word_slices)

        if total_slice_bits > bit_size:
            raise ValueError(f'Total bits from WordSlices ({total_slice_bits}) exceeds word bit_size ({bit_size})')

        # Pack WordSlices into the word value
        value = 0
        current_bit_position = bit_size - 1  # Start from MSB

        for slice_obj in word_slices:
            # Get the raw bits from the WordSlice
            slice_bits = slice_obj.get_raw_bits()

            # Place the bits at the current position
            value |= slice_bits << (current_bit_position - slice_obj.bit_size + 1)
            current_bit_position -= slice_obj.bit_size

        return cls(value, bit_size, segment_size, intra_word_endianness)

    @classmethod
    def from_bytes(
        cls,
        bytes: bytes,
        word_bit_size: int,
        word_segment_size: int,
        intra_word_endianness: Literal['little', 'big'],
    ) -> list['Word']:
        '''
        Convert a list of bytes into a list of words with each word having the indicated bit size and segment size.

        :param bytes: The bytes to convert
        :param word_bit_size: The total number of bits in the word
        :param word_segment_size: The size of segments within the word
        :param intra_word_endianness: The endianness of segments when converting to bytes
        :return: A list of Word objects
        '''
        if word_bit_size <= 0:
            raise ValueError('word_bit_size must be greater than 0')
        if word_segment_size <= 0:
            raise ValueError('word_segment_size must be greater than 0')
        if word_bit_size % word_segment_size != 0:
            raise ValueError(f'word_bit_size {word_bit_size} must be divisible by word_segment_size {word_segment_size}')
        if word_segment_size > word_bit_size:
            raise ValueError(f'word_segment_size {word_segment_size} cannot be greater than word_bit_size {word_bit_size}')

        total_bits = len(bytes) * 8
        word_count = total_bits // word_bit_size
        if total_bits % word_bit_size != 0:
            raise ValueError('Input bytes do not align to an integer number of words')

        words = []
        # Convert bytes to a single integer (big-endian)
        big_int = int.from_bytes(bytes, byteorder='big')
        for i in range(word_count):
            # Extract the bits for this word
            shift = (word_count - 1 - i) * word_bit_size
            word_value = (big_int >> shift) & ((1 << word_bit_size) - 1)

            # For little-endian intra-word, reverse the segments
            if intra_word_endianness == 'little' and word_segment_size != word_bit_size:
                segment_count = word_bit_size // word_segment_size
                segments = []
                for s in range(segment_count):
                    seg_shift = (segment_count - 1 - s) * word_segment_size
                    seg_val = (word_value >> seg_shift) & ((1 << word_segment_size) - 1)
                    segments.append(seg_val)
                segments = list(reversed(segments))
                # Recombine segments into a value
                word_value = 0
                for idx, seg in enumerate(segments):
                    word_value |= seg << ((segment_count - 1 - idx) * word_segment_size)
            words.append(cls(word_value, word_bit_size, word_segment_size, intra_word_endianness))
        return words

    @property
    def value(self) -> int:
        """Returns the integer value of the word."""
        return self._value

    @property
    def bit_size(self) -> int:
        """Returns the total number of bits in the word."""
        return self._bit_size

    @property
    def segment_size(self) -> int:
        """Returns the size of segments within the word."""
        return self._segment_size

    @property
    def intra_word_endianness(self) -> Literal['little', 'big']:
        """Returns the endianness of segments when converting to bytes."""
        return self._intra_word_endianness

    @property
    def segment_count(self) -> int:
        """Returns the number of segments in the word."""
        return self._bit_size // self._segment_size

    def to_bytes(self) -> bytes:
        """
        Convert the word to bytes according to the intra-word endianness.

        The word is divided into segments based on segment_size, and the segments
        are ordered according to intra_word_endianness when converting to bytes.

        :return: Bytes representation of the word
        """
        # Calculate number of bytes needed
        byte_count = (self._bit_size + 7) // 8

        # Handle negative values by converting to two's complement
        if self._value < 0:
            # Convert to two's complement: invert bits and add 1
            positive_value = (1 << self._bit_size) + self._value
        else:
            positive_value = self._value

        # Extract segments from the positive value
        segments = self._extract_segments_from_value(positive_value)

        # Apply intra-word endianness
        if self._intra_word_endianness == 'little':
            segments = list(reversed(segments))

        # Combine segments back into a value
        combined_value = self._combine_segments(segments)

        # Left-align the value within the byte array (MSB first)
        total_bits = byte_count * 8
        shift = total_bits - self._bit_size
        aligned_value = combined_value << shift

        # Convert to bytes using big-endian (since we've already handled endianness)
        return aligned_value.to_bytes(byte_count, byteorder='big', signed=False)

    def _extract_segments(self) -> list[int]:
        """
        Extract segments from the word value based on segment_size.

        :return: List of segment values, ordered from most significant to least significant
        """
        return self._extract_segments_from_value(self._value)

    def _extract_segments_from_value(self, value: int) -> list[int]:
        """
        Extract segments from a given value based on segment_size.

        :param value: The value to extract segments from
        :return: List of segment values, ordered from most significant to least significant
        """
        segments = []
        segment_mask = (1 << self._segment_size) - 1

        for i in range(self.segment_count):
            # Extract segment starting from MSB
            segment_value = (value >> (self._bit_size - (i + 1) * self._segment_size)) & segment_mask
            segments.append(segment_value)

        return segments

    def _combine_segments(self, segments: list[int]) -> int:
        """
        Combine segments back into a word value.

        :param segments: List of segment values, ordered from most significant to least significant
        :return: The combined word value
        """
        if len(segments) != self.segment_count:
            raise ValueError(f'Expected {self.segment_count} segments, got {len(segments)}')

        value = 0
        for i, segment in enumerate(segments):
            value |= segment << (self._bit_size - (i + 1) * self._segment_size)

        return value

    def __repr__(self) -> str:
        return f'Word<value=0x{self._value:x}, bit_size={self._bit_size}, ' \
               f'segment_size={self._segment_size}, intra_word_endianness={self._intra_word_endianness}>'

    def __str__(self) -> str:
        return f'Word<{self._value} ({self._bit_size} bits, {self._segment_size}-bit segments, {self._intra_word_endianness})>'

    def __eq__(self, other) -> bool:
        if isinstance(other, Word):
            return (
                    self._value == other._value and
                    self._bit_size == other._bit_size and
                    self._segment_size == other._segment_size and
                    self._intra_word_endianness == other._intra_word_endianness
                )
        return False

    def __hash__(self) -> int:
        return hash((self._value, self._bit_size, self._segment_size, self._intra_word_endianness))

    def __int__(self) -> int:
        return self._value

    @classmethod
    def words_to_bytes(
        cls,
        words: list,
        compact_bytes: bool = False,
        multi_word_endianness: Literal['little', 'big'] = 'big'
    ) -> bytearray:
        """
        Generate a byte array from a list of Word or WordSlice objects.
        If compact_bytes is True, pack bits tightly in the order given, ignoring per-Word endianness.
        """
        if not words:
            return bytearray()

        if compact_bytes:
            # For compact packing, we need to handle each word's endianness properly
            # and pack them in sequence
            byte_array = bytearray()
            current_byte = 0
            current_bit_position = 7  # Start from MSB of current byte

            for word in words:
                if hasattr(word, 'bit_size') and hasattr(word, 'value'):
                    value = word.value
                    bit_size = word.bit_size
                else:
                    continue

                # Handle negative values by converting to two's complement
                if value < 0:
                    positive_value = (1 << bit_size) + value
                else:
                    positive_value = value

                # Pack bits from MSB to LSB
                for bit_index in range(bit_size - 1, -1, -1):
                    bit_value = (positive_value >> bit_index) & 1

                    if bit_value:
                        current_byte |= (1 << current_bit_position)

                    current_bit_position -= 1

                    # If we've filled a byte, add it to the array and start a new one
                    if current_bit_position < 0:
                        byte_array.append(current_byte)
                        current_byte = 0
                        current_bit_position = 7

            # Add the last byte if it has any bits set
            if current_bit_position < 7:
                byte_array.append(current_byte)

            return byte_array
        else:
            # Convert each word to bytes and concatenate
            byte_array = bytearray()
            for word in words:
                word_bytes = word.to_bytes()
                byte_array.extend(word_bytes)
            return byte_array
