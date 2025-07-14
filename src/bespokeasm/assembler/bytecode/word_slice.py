class WordSlice:
    """
    Represents a slice of bits that can be grouped with other WordSlices to form a Word.

    WordSlices are raw bit components with no endianness concept - they are always
    concatenated in order to form the final Word. The endianness is applied at the
    Word level when the Word is converted to bytes.

    Examples:

    * Instruction word slices:
      - WordSlice(opcode_bits, 3)      # 3-bit opcode
      - WordSlice(operand_type, 5)     # 5-bit operand type
      - These would be concatenated to form an 8-bit instruction Word

    * Address word slices:
      - WordSlice(page_bits, 4)        # 4-bit page number
      - WordSlice(offset_bits, 12)     # 12-bit offset
      - These would be concatenated to form a 16-bit address Word
    """

    def __init__(self, value: int, bit_size: int):
        """
        Initialize a WordSlice with a value and bit size.

        :param value: The integer value of the slice. Must fit within bit_size.
        :param bit_size: The number of bits in this slice. Must be greater than 0.
        :raises ValueError: If bit_size is less than or equal to 0, or if value is out of range.
        """
        if bit_size < 0:
            raise ValueError('bit_size must be greater than or equal to 0')

        # Special case: 0-bit slices can only have value 0
        if bit_size == 0:
            if value != 0:
                raise ValueError(f'0-bit WordSlice can only have value 0, got {value}')
            self._value = 0
            self._bit_size = 0
            return

        # Calculate the valid range for the given bit size
        # Allow both signed (negative) and unsigned (positive) values
        min_value = -(1 << (bit_size - 1))  # -2^(bit_size-1) for signed
        max_value = (1 << bit_size) - 1  # 2^bit_size - 1 for unsigned

        if value < min_value or value > max_value:
            raise ValueError(f'value {value} is out of range for bit_size {bit_size} (range: {min_value} to {max_value})')

        self._value = value
        self._bit_size = bit_size

    @property
    def value(self) -> int:
        """Returns the value of the WordSlice."""
        return self._value

    @property
    def bit_size(self) -> int:
        """Returns the bit size of the WordSlice."""
        return self._bit_size

    def __repr__(self) -> str:
        return f'WordSlice<value=0x{self._value:x}, bit_size={self._bit_size}>'

    def __str__(self) -> str:
        return f'WordSlice<{self._value} ({self._bit_size} bits)>'

    def __eq__(self, other) -> bool:
        if isinstance(other, WordSlice):
            return self._value == other._value and self._bit_size == other._bit_size
        return False

    def __hash__(self) -> int:
        return hash((self._value, self._bit_size))

    def get_raw_bits(self) -> int:
        """
        Returns the raw unsigned bits that represent this value.

        For negative values, returns the two's complement representation as an unsigned integer.
        For non-negative values, returns the value masked to the bit size.
        For 0-bit slices, returns 0.

        :return: The unsigned integer representing the raw bits.
        """
        if self._bit_size == 0:
            return 0

        # Handle negative values by converting to two's complement
        if self._value < 0:
            # Convert to two's complement: invert bits and add 1
            # First, get the positive value as if it were unsigned
            return (1 << self._bit_size) + self._value
        else:
            # For non-negative values, mask to bit size
            return self._value & ((1 << self._bit_size) - 1)
