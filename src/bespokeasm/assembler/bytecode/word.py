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
    def fromInt(
                value: int,
                bit_size: int = 8,
                align_bytes: bool = False,
                byteorder: Literal['little', 'big'] = 'big'
            ) -> 'Word':
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
        if bit_size < 0:
            raise ValueError('bit_size must be greater or equal to 0')
        if bit_size == 0 and value != 0:
            raise ValueError('bit_size is 0, but value is not 0')
        if value < (-2**(bit_size-1)) or value >= (2**bit_size):
            raise ValueError(f'value {value} is out of range for bit size {bit_size}')
        return Word(value, bit_size, align_bytes, byteorder)

    @staticmethod
    def generateByteArray(words: list['Word'], compact_bytes=False, byteorder: Literal['little', 'big'] = None) -> bytes:
        """
        Generates a byte array representation of a list of Word objects. Word objects
        are not required to have the same bit size. If compact_bytes is True, bits are packed tightly into bytes,
        respecting the align_bytes property of individual Word objects. This means that the bits will be packed
        to the left, and if a Word has align_bytes set to True, it will be aligned to the next byte boundary.
        Otherwise, each Word will start a new byte in the array.

        :param words: List of Word objects to convert to a byte array.
        :param compact_bytes: If True, pack the bits tightly into bytes, respecting the align_bytes property if
                              indivdual Word objects. If False, each Word will start a new byte in the array.
        :param byteorder: The byte order to use when converting the Word values to bytes. Does not impact
                          the compact_bytes option, which only affects how bits are packed. None means to use the
                          byte order specified during initialization of the Word objects for that Word.
        :return: A byte array representation of the Word objects.
        :raises ValueError: If the bit size of any Word is less than or equal to 0, or if there is not enough space
                            in the byte array for the Word values
        """
        if not words:
            return b''

        if compact_bytes:
            # the total bits calculation needs to account for any byte alignment that causeds
            # the bits to be padded to the next byte boundary
            total_bits = 0
            for word in words:
                if word.align_bytes and total_bits % 8 != 0:
                    total_bits += 8 - (total_bits % 8)
                total_bits += word.bit_size
            byte_array = bytearray((total_bits + 7) // 8)
            current_bit = 0
            for word in words:
                if word.bit_size < 0:
                    raise ValueError('Word bit size must be greater than 0')
                if word.bit_size == 0 and word.value != 0:
                    raise ValueError('Word bit size is 0, but value is not 0')
                if current_bit + word.bit_size > len(byte_array) * 8:
                    raise ValueError('Not enough space in byte array for the word')
                # If align_bytes is set, align to next byte boundary before writing
                if word.align_bytes and current_bit % 8 != 0:
                    current_bit += 8 - (current_bit % 8)
                # If the word is byte-aligned and we're at a byte boundary, copy bytes directly
                if word.bit_size % 8 == 0 and current_bit % 8 == 0:
                    word_bytes = word.to_bytes(compact_bytes=True, byteorder=byteorder)
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
                word_bytes = word.to_bytes(compact_bytes=False, byteorder=byteorder)
                byte_array[current_index:current_index + word.byte_size] = word_bytes
                current_index += word.byte_size
            if current_index != len(byte_array):
                raise ValueError('Mismatch in byte array size')

            return bytes(byte_array)

    def __init__(
                self,
                value: int,
                bit_size: int = 8,
                align_bytes: bool = False,
                byteorder: Literal['little', 'big'] = 'big',
            ) -> None:
        """
        Initializes a Word object with a value and bit size.

        :param value: The integer value of the word.
        :param bit_size: The bit size of the word. Must be greater than 0.
        :param align_bytes: If True, the word will be aligned to byte boundaries when packed by
                            the Word.generateByteArray method.
        :param byteorder: The byte order to use when converting the Word value to bytes.
        :raises ValueError: If bit_size is less than or equal to 0, or if the value is out of range for the specified bit size.
        """
        if bit_size < 0:
            raise ValueError('bit_size must be greater than 0')
        if bit_size == 0 and value != 0:
            raise ValueError('bit_size is 0, but value is not 0')
        if value < (-2**(bit_size-1)) or value >= (1 << bit_size):
            raise ValueError(f'value {value} is out of range for bit size {bit_size}')
        self._value = value
        self._bit_size = bit_size
        self._align_bytes = align_bytes
        self._byteorder = byteorder

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

    @property
    def byteorder(self) -> Literal['little', 'big']:
        """
        Returns the byte order used when converting the Word value to bytes.
        This is either 'little' or 'big'.
        """
        return self._byteorder

    def __bytes__(self):
        """
        Returns the word value as a byte array in big-endian order. If you need little-endian order, use
        the to_bytes method with byteorder='little'. The byte array will be of length 1 if bit_size is
        <=8, or larger for other bit sizes.
        """
        return self.to_bytes()

    def to_bytes(self, compact_bytes: bool = False, byteorder: Literal['little', 'big'] = None) -> bytes:
        """
        Returns the word value as a byte array. The value will be "left packed" into the byte array,
        meaning that the highest bits of the value will be in the highest bits of the first byte.
        The byte array will be of length 1 if bit_size is <=8, or larger for other bit sizes.

        For bit sizes greater than 8, the byte array will be left-packked with zeros to fill the byte size.
        if the compact_bytes parameter is True. For example, a 12-bite value of 0x123 will be represented
        as bytes([0x12, 0x30]), which is 2 bytes long, with the first byte containing the high bits and the second
        byte containing the low bits. Furthermore, for a 4-bit value of 0b1010, the byte array will be
        bytes([0b10100000]), which is 1 byte long, with the high nibble containing the value and the low nibble
        filled with zeros. This behavior is intended to work with the Word.generateByteArray method,
        which expects the bits to be packed tightly into bytes when compact_bytes is True.

        :param compact_bytes: If True, the bits will be packed tightly to the left into bytes.
        :param byteorder: The byte order to use when converting the Word value to bytes. If None, uses the
                          byte order specified during initialization of the Word object.
        :return: A byte array representation of the Word value.
        """
        if byteorder is None:
            byteorder = self._byteorder
        byte_len = (self.bit_size + 7) // 8
        value = self.value

        if compact_bytes:
            # Left-pack the bits: shift value so the highest bits are in the highest bits of the first byte
            total_bits = byte_len * 8
            shift = total_bits - self.bit_size
            value = value << shift

        return value.to_bytes(byte_len, byteorder=byteorder, signed=(self.value < 0))

    @property
    def byte_size(self) -> int:
        """
        Returns the byte size of the word.
        This is the number of bytes needed to represent the word value.
        """
        return (self.bit_size + 7) // 8
