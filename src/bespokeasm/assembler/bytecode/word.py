from typing import Literal


class Word:
    """
    Represents a word in the bytecode. A word is the data bus width of the CPU, which is typically 8, 16, 32, or 64 bits.
    An address points to a word, and the word is the smallest unit of data that can be read or written.
    """

    @staticmethod
    def fromByteArray(byte_array: bytes, bit_size: int = 8, compact_bytes=False) -> list['Word']:
        """
        Generates a list of Word objects from a byte array.
        Each byte in the array is treated as a separate Word.
        If compact_bytes is True, the byte array is treated as a sequence of bits. Otherwise, each
        byte is treated as a separate word.
        """
        if bit_size <= 0:
            raise ValueError('bit_size must be greater than 0')
        if compact_bytes:
            # Need to treat the byte array like a bit stream and pop off bit_size bits at a time.
            # if bit_size is 4, we will extract 4 bits at a time from the byte array.
            if bit_size == 4:
                # Special case for 4 bits, we can extract 4 bits at a time from the byte array
                word_count = len(byte_array) * 2
                words = []
                for byte in byte_array:
                    words.append(Word((byte >> 4) & 0x0F, bit_size))
                    words.append(Word(byte & 0x0F, bit_size))
            elif bit_size == 8:
                # Special case for 8 bits, each byte is a word
                words = [Word(byte, bit_size) for byte in byte_array]
            elif bit_size % 8 == 0:
                # For bit sizes that are multiples of 8, we can extract the bits directly
                byte_size = bit_size // 8
                word_count = len(byte_array) // byte_size
                words = []
                for i in range(word_count):
                    start_index = i * byte_size
                    end_index = start_index + byte_size
                    words.append(Word(int.from_bytes(byte_array[start_index:end_index], 'big'), bit_size))
            else:
                # For other bit sizes, we need to extract bits one by one
                # This is not implemented yet, as it requires more complex bit manipulation.
                # For now, we will raise an error.
                raise NotImplementedError(
                    'Compact byte extraction for bit sizes other than 4, 8, or multiples of 8 is not implemented yet.'
                )
            return words
        else:
            return [Word(byte, bit_size) for byte in byte_array]

    @staticmethod
    def fromInt(value: int, bit_size: int = 8, align_bytes: bool = False) -> 'Word':
        """
        Generates a Word object from an integer value.

        :param value: The integer value of the word.
        :param bit_size: The bit size of the word. Must be greater than 0.
        :param align_bytes: If True, the word will be aligned to byte boundaries when packed by
                            the Word.generateByteArray method.
        :raises ValueError: If bit_size is less than or equal to 0, or if the value is out of
                            range for the specified bit size.
        :return: A Word object representing the value.
        """
        if bit_size <= 0:
            raise ValueError('bit_size must be greater than 0')
        if value < 0 or value >= (2**bit_size - 1):
            raise ValueError(f'value {value} is out of range for bit size {bit_size}')
        return Word(value, bit_size, align_bytes)

    @staticmethod
    def generateByteArray(words: list['Word'], compact_bytes=False, byteorder: Literal['little', 'big'] = 'big') -> bytes:
        """
        Generates a byte array representation of a list of Word objects. Word objects
        are not required to have the same bit size. If compact_bytes is True, bits are packed tightly into bytes.
        Otherwise, each Word will start a new byte in the array.

        :param words: List of Word objects to convert to a byte array.
        :param compact_bytes: If True, pack the bits tightly into bytes, respecting the aliagn_bytes property if
                              indivdual Word objects. If False, each Word will start a new byte in the array.
        :param byteorder: The byte order to use when converting the Word values to bytes. Does not impact
                          the compact_bytes option, which only affects how bits are packed.
        :return: A byte array representation of the Word objects.
        :raises ValueError: If the bit size of any Word is less than or equal to 0, or if there is not enough space
                            in the byte array for the Word values
        """
        if not words:
            return b''

        if compact_bytes:
            total_bits = sum(word.bit_size for word in words)
            byte_array = bytearray((total_bits + 7) // 8)
            current_bit = 0
            for word in words:
                if word.bit_size <= 0:
                    raise ValueError('Word bit size must be greater than 0')
                if current_bit + word.bit_size > len(byte_array) * 8:
                    raise ValueError('Not enough space in byte array for the word')
                # If align_bytes is set, align to next byte boundary before writing
                if word.align_bytes and current_bit % 8 != 0:
                    current_bit += 8 - (current_bit % 8)
                # If the word is byte-aligned and we're at a byte boundary, copy bytes directly
                if word.bit_size % 8 == 0 and current_bit % 8 == 0:
                    word_bytes = word.to_bytes(byteorder=byteorder)
                    start = current_bit // 8
                    end = start + len(word_bytes)
                    byte_array[start:end] = word_bytes
                    current_bit += word.bit_size
                else:
                    # Otherwise, pack bits one at a time, always MSB first
                    for bit_index in reversed(range(word.bit_size)):
                        if (word.value >> bit_index) & 1:
                            byte_array[current_bit // 8] |= (1 << (7 - (current_bit % 8)))
                        current_bit += 1
            return bytes(byte_array)
        else:
            # Each Word starts a new byte in the array
            total_bytes = sum(word.byte_size for word in words)
            if total_bytes == 0:
                return b''
            if any(word.bit_size <= 0 for word in words):
                raise ValueError('Word bit size must be greater than 0')
            byte_array = bytearray(total_bytes)
            current_index = 0
            for word in words:
                if current_index + word.byte_size > len(byte_array):
                    raise ValueError('Not enough space in byte array for the word')
                # Convert the word value to bytes and store it in the byte array
                word_bytes = word.to_bytes(byteorder=byteorder)
                byte_array[current_index:current_index + word.byte_size] = word_bytes
                current_index += word.byte_size
            if current_index != len(byte_array):
                raise ValueError('Mismatch in byte array size')

            return bytes(byte_array)

    def __init__(self, value: int, bit_size: int = 8, align_bytes: bool = False) -> None:
        """
        Initializes a Word object with a value and bit size.

        :param value: The integer value of the word.
        :param bit_size: The bit size of the word. Must be greater than 0.
        :param align_bytes: If True, the word will be aligned to byte boundaries when packed by
                            the Word.generateByteArray method.
        :raises ValueError: If bit_size is less than or equal to 0, or if the value is out of range for the specified bit size.
        """
        if bit_size <= 0:
            raise ValueError('bit_size must be greater than 0')
        if value < 0 or value >= (1 << bit_size):
            raise ValueError(f'value {value} is out of range for bit size {bit_size}')
        self._value = value
        self._bit_size = bit_size
        self._align_bytes = align_bytes

    def __repr__(self):
        return f'Word<{bytes(self).hex()}, bit_size={self._bit_size}>'

    def __int__(self):
        return self._value

    def __eq__(self, other):
        if isinstance(other, Word):
            return self._value == other._value and self._bit_size == other._bit_size
        return False

    def __hash__(self):
        # this is a hash of both the value and the bit size to ensure that two words with the
        # same value but different bit sizes are not considered equal
        if not isinstance(self, Word):
            return NotImplemented
        if self.bit_size <= 8:
            return hash((self._value, self._bit_size))

    @property
    def value(self) -> int:
        """
        Returns the value of the word
        """
        return self._value

    @property
    def bit_size(self) -> int:
        """
        Returns the bit size of the word
        """
        return self._bit_size

    @property
    def align_bytes(self) -> bool:
        """
        Returns whether the word should be aligned to byte boundaries.
        This is used for packing bits tightly into bytes.
        """
        return self._align_bytes

    def __bytes__(self):
        """
        Returns the word value as a byte array in big-endian order. If you need little-endian order, use
        the to_bytes method with byteorder='little'. The byte array will be of length 1 if bit_size is
        <=8, or larger for other bit sizes.
        """
        return self.to_bytes()

    def to_bytes(self, byteorder: Literal['little', 'big'] = 'big') -> bytes:
        """
        Returns the word value as a byte array.
        The byte array will be of length 1 if bit_size is <=8, or larger for other bit sizes.
        """
        return self.value.to_bytes((self.bit_size + 7) // 8, byteorder=byteorder)

    @property
    def byte_size(self) -> int:
        """
        Returns the byte size of the word.
        This is the number of bytes needed to represent the word value.
        """
        return (self.bit_size + 7) // 8
