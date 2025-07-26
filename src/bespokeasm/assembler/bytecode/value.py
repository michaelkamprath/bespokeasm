from typing import Literal
from .word import Word
from .word_slice import WordSlice


class Value:
    """
    Represents a value that spans multiple words. A Value is composed of multiple Word objects
    that collectively represent a single logical value.

    The Value class handles:
    - Construction from a single integer value
    - Multi-word endianness for byte emission
    - Left-packing of bits when word bit size isn't a multiple of 8
    - Consistent word properties across all words in the value

    All Word objects in a Value have the same bit_size, segment_size, and intra_word_endianness,
    but may have different values.
    """

    def __init__(
        self,
        value: int,
        word_bit_size: int,
        segment_size: int = 8,
        intra_word_endianness: Literal['little', 'big'] = 'big',
        multi_word_endianness: Literal['little', 'big'] = 'big'
    ):
        """
        Initialize a Value with a value and word configuration.

        :param value: The integer value to represent
        :param word_bit_size: The bit size of each word in the value
        :param segment_size: The size of segments within each word
        :param intra_word_endianness: The endianness of segments within each word
        :param multi_word_endianness: The endianness of words when emitting bytes
        :raises ValueError: If parameters are invalid
        """
        if word_bit_size <= 0:
            raise ValueError('word_bit_size must be greater than 0')

        if segment_size <= 0:
            raise ValueError('segment_size must be greater than 0')

        if segment_size > word_bit_size:
            raise ValueError(f'segment_size {segment_size} cannot be greater than word_bit_size {word_bit_size}')

        # If segment_size doesn't divide word_bit_size evenly, adjust segment_size to word_bit_size
        if word_bit_size % segment_size != 0:
            segment_size = word_bit_size

        if multi_word_endianness not in ['little', 'big']:
            raise ValueError('multi_word_endianness must be "little" or "big"')

        if intra_word_endianness not in ['little', 'big']:
            raise ValueError('intra_word_endianness must be "little" or "big"')

        self._value = value
        self._word_bit_size = word_bit_size
        self._segment_size = segment_size
        self._intra_word_endianness = intra_word_endianness
        self._multi_word_endianness = multi_word_endianness

        # Calculate the number of words needed
        self._word_count = self._calculate_word_count()

        # Generate the list of words
        self._words = self._generate_words()

    @classmethod
    def from_words(
        cls,
        words: list[Word],
        multi_word_endianness: Literal['little', 'big'] = 'big'
    ) -> 'Value':
        """
        Create a Value from a list of Word objects.

        All Word objects must have the same bit_size, segment_size, and intra_word_endianness.
        The words are assumed to be in big-endian order (MSB to LSB).

        :param words: List of Word objects to combine into a Value
        :param multi_word_endianness: The multi-word endianness for the Value
        :return: A new Value object
        :raises ValueError: If the list is empty or Word objects have inconsistent properties
        """
        if not words:
            raise ValueError('words list cannot be empty')

        if len(words) == 0:
            raise ValueError('words list cannot be empty')

        # Check that all words have consistent properties
        first_word = words[0]
        word_bit_size = first_word.bit_size
        segment_size = first_word.segment_size
        intra_word_endianness = first_word.intra_word_endianness

        for i, word in enumerate(words):
            if word.bit_size != word_bit_size:
                raise ValueError(f'Word {i} has bit_size {word.bit_size}, expected {word_bit_size}')
            if word.segment_size != segment_size:
                raise ValueError(f'Word {i} has segment_size {word.segment_size}, expected {segment_size}')
            if word.intra_word_endianness != intra_word_endianness:
                raise ValueError(
                        f'Word {i} has intra_word_endianness {word.intra_word_endianness}, '
                        f'expected {intra_word_endianness}'
                    )

        # Calculate the total value by combining all words
        total_value = 0
        for i, word in enumerate(words):
            # Each word contributes to the total value, shifted by its position
            # For negative values, we need to treat them as unsigned in the context of the larger value
            if word.value < 0:
                # Convert to two's complement for the word's bit size
                word_value = (1 << word_bit_size) + word.value
            else:
                word_value = word.value

            shift = (len(words) - 1 - i) * word_bit_size
            total_value |= word_value << shift

        # Create the Value object
        value_obj = cls.__new__(cls)
        value_obj._value = total_value
        value_obj._word_bit_size = word_bit_size
        value_obj._segment_size = segment_size
        value_obj._intra_word_endianness = intra_word_endianness
        value_obj._multi_word_endianness = multi_word_endianness
        value_obj._word_count = len(words)
        value_obj._words = words.copy()  # Store a copy of the words

        return value_obj

    @classmethod
    def from_word_slices(
        cls,
        word_slices: list['WordSlice'],
        word_bit_size: int,
        segment_size: int = 8,
        multi_word_endianness: Literal['little', 'big'] = 'big',
        intra_word_endianness: Literal['little', 'big'] = 'big',
    ) -> 'Value':
        """
        Create a Value from a list of WordSlice objects.

        The WordSlices are packed into words of the specified bit_size, and then
        the words are combined into a Value. The WordSlices are processed in order
        from most significant to least significant.

        :param word_slices: List of WordSlice objects to pack into words
        :param word_bit_size: The bit size of each word in the Value
        :param segment_size: The size of segments within each word
        :param intra_word_endianness: The endianness of segments within each word
        :param multi_word_endianness: The endianness of words when emitting bytes
        :return: A new Value object
        :raises ValueError: If parameters are invalid
        """
        if word_bit_size <= 0:
            raise ValueError('word_bit_size must be greater than 0')

        if segment_size <= 0:
            raise ValueError('segment_size must be greater than 0')

        if segment_size > word_bit_size:
            raise ValueError(f'segment_size {segment_size} cannot be greater than word_bit_size {word_bit_size}')

        # If segment_size doesn't divide word_bit_size evenly, adjust segment_size to word_bit_size
        if word_bit_size % segment_size != 0:
            segment_size = word_bit_size

        if multi_word_endianness not in ['little', 'big']:
            raise ValueError('multi_word_endianness must be "little" or "big"')

        if intra_word_endianness not in ['little', 'big']:
            raise ValueError('intra_word_endianness must be "little" or "big"')

        if not word_slices:
            # Create a Value with zero value
            return cls(0, word_bit_size, segment_size, intra_word_endianness, multi_word_endianness)

        # Calculate total bits from WordSlices
        total_slice_bits = sum(slice_obj.bit_size for slice_obj in word_slices)

        # Calculate how many words we need
        word_count = (total_slice_bits + word_bit_size - 1) // word_bit_size

        # First, calculate the total value by packing all WordSlices
        total_value = 0
        current_bit_position = total_slice_bits - 1  # Start from MSB

        for slice_obj in word_slices:
            slice_bits = slice_obj.get_raw_bits()
            # Position the slice at the current bit position
            total_value |= slice_bits << (current_bit_position - slice_obj.bit_size + 1)
            current_bit_position -= slice_obj.bit_size

        # Now create the Value object with the total value
        value_obj = cls.__new__(cls)
        value_obj._value = total_value
        value_obj._word_bit_size = word_bit_size
        value_obj._segment_size = segment_size
        value_obj._intra_word_endianness = intra_word_endianness
        value_obj._multi_word_endianness = multi_word_endianness
        value_obj._word_count = word_count
        value_obj._words = value_obj._generate_words()  # Generate words from the total value

        return value_obj

    def _calculate_word_count(self) -> int:
        """
        Calculate the number of words needed to represent the value.

        :return: Number of words needed
        """
        # Calculate the total number of bits needed
        if self._value == 0:
            return 1  # At least one word, even for zero

        # Calculate bits needed for the absolute value
        abs_value = abs(self._value)
        bits_needed = abs_value.bit_length()

        # If the value is negative, we need one more bit for the sign
        if self._value < 0:
            bits_needed += 1

        # Calculate number of words needed
        word_count = (bits_needed + self._word_bit_size - 1) // self._word_bit_size

        return max(1, word_count)  # At least one word

    def _generate_words(self) -> list[Word]:
        """
        Generate the list of Word objects that represent this value.

        :return: List of Word objects
        """
        words = []
        remaining_value = self._value

        for i in range(self._word_count):
            # Calculate the bit position for this word
            bit_position = (self._word_count - 1 - i) * self._word_bit_size

            # Extract the bits for this word
            if bit_position >= remaining_value.bit_length():
                # This word will be zero
                word_value = 0
            else:
                # Extract the bits for this word
                word_value = (remaining_value >> bit_position) & ((1 << self._word_bit_size) - 1)

            # Create the word
            word = Word(
                value=word_value,
                bit_size=self._word_bit_size,
                segment_size=self._segment_size,
                intra_word_endianness=self._intra_word_endianness
            )
            words.append(word)

        return words

    @property
    def value(self) -> int:
        """Returns the integer value represented by this Value."""
        return self._value

    @property
    def word_bit_size(self) -> int:
        """Returns the bit size of each word in this Value."""
        return self._word_bit_size

    @property
    def segment_size(self) -> int:
        """Returns the segment size of each word in this Value."""
        return self._segment_size

    @property
    def intra_word_endianness(self) -> Literal['little', 'big']:
        """Returns the intra-word endianness of each word in this Value."""
        return self._intra_word_endianness

    @property
    def multi_word_endianness(self) -> Literal['little', 'big']:
        """Returns the multi-word endianness of this Value."""
        return self._multi_word_endianness

    @property
    def word_count(self) -> int:
        """Returns the number of words in this Value."""
        return self._word_count

    @property
    def words(self) -> list[Word]:
        """
        Returns the list of Word objects in this Value. Note that the Words are always in big-endian order.
        If you want to get the words in this Value's native endianness, use get_words_ordered().
        """
        return self._words.copy()  # Return a copy to prevent modification

    def get_words_ordered(self, multi_word_endianness: Literal['little', 'big'] = None) -> list[Word]:
        """
        Returns the list of Word objects ordered according to the specified multi-word endianness.

        :param multi_word_endianness: The multi-word endianness to use for ordering.
                                     If None, uses the Value object's multi_word_endianness.
        :return: List of Word objects ordered according to the specified endianness
        :raises ValueError: If multi_word_endianness is not 'little', 'big', or None
        """
        if multi_word_endianness is not None and multi_word_endianness not in ['little', 'big']:
            raise ValueError('multi_word_endianness must be "little", "big", or None')

        # Use the Value object's endianness if none specified
        endianness = multi_word_endianness if multi_word_endianness is not None else self._multi_word_endianness

        if endianness == 'little':
            # For little-endian, return words in reverse order (LSB first)
            return list(reversed(self._words))
        else:
            # For big-endian, return words in original order (MSB first)
            return self._words.copy()

    def to_bytes(self) -> bytes:
        """
        Convert the Value to bytes according to the multi-word endianness.

        The words are ordered according to multi_word_endianness when converting to bytes.
        If word_bit_size is not a multiple of 8, the bits are left-packed.

        :return: Bytes representation of the Value
        """
        if not self._words:
            return b''

        # Determine the order of words based on multi-word endianness
        if self._multi_word_endianness == 'little':
            # For little-endian multi-word, process words in reverse order
            words_to_process = list(reversed(self._words))
        else:
            # For big-endian multi-word, process words in original order
            words_to_process = self._words

        # Check if we need to left-pack bits
        if self._word_bit_size % 8 != 0:
            return self._to_bytes_left_packed(words_to_process)
        else:
            return self._to_bytes_aligned(words_to_process)

    def _to_bytes_left_packed(self, words: list[Word]) -> bytes:
        """
        Convert words to bytes with left-packing when word bit size isn't a multiple of 8.

        :param words: List of words to convert
        :return: Bytes representation with left-packing
        """
        # Calculate total bits
        total_bits = len(words) * self._word_bit_size
        byte_count = (total_bits + 7) // 8

        # Create byte array
        byte_array = bytearray(byte_count)
        current_bit = 0

        for word in words:
            # Get the raw bits from the word (handle negative values)
            if word.value < 0:
                # Convert to two's complement
                word_bits = (1 << self._word_bit_size) + word.value
            else:
                word_bits = word.value

            # Pack the bits into the byte array, MSB first
            for bit_index in range(self._word_bit_size - 1, -1, -1):
                if (word_bits >> bit_index) & 1:
                    byte_array[current_bit // 8] |= (1 << (7 - (current_bit % 8)))
                current_bit += 1

        return bytes(byte_array)

    def _to_bytes_aligned(self, words: list[Word]) -> bytes:
        """
        Convert words to bytes when word bit size is a multiple of 8.

        :param words: List of words to convert
        :return: Bytes representation
        """
        byte_array = bytearray()

        for word in words:
            word_bytes = word.to_bytes()
            byte_array.extend(word_bytes)

        return bytes(byte_array)

    def __repr__(self) -> str:
        return f'Value<value=0x{self._value:x}, words={self._word_count}x{self._word_bit_size}bit, ' \
               f'multi_endian={self._multi_word_endianness}>'

    def __str__(self) -> str:
        return f'Value<{self._value} ({self._word_count} words of {self._word_bit_size} bits each, ' \
               f'{self._multi_word_endianness} multi-word)>'

    def __eq__(self, other) -> bool:
        if isinstance(other, Value):
            return (
                    self._value == other._value and
                    self._word_bit_size == other._word_bit_size and
                    self._segment_size == other._segment_size and
                    self._intra_word_endianness == other._intra_word_endianness and
                    self._multi_word_endianness == other._multi_word_endianness
                )
        return False

    def __hash__(self) -> int:
        return hash((self._value, self._word_bit_size, self._segment_size,
                    self._intra_word_endianness, self._multi_word_endianness))

    def __int__(self) -> int:
        return self._value
