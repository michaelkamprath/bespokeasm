# Data Word
# A data word is an abstraction of the bytecode entity rerpesentating the native data size of the target architecture.
# A data word can be an arbitrary number of bits, but is typically 4, 8, 16, 32, or 64 bits. The data word is an the data
# that an address points to in memory.
#
# An instance of this object represents one data word. The following functionality is provided:
# - it can be created from a number, a string, or a byte array. If anyh of these are too large for the data word size,
#   an OverflowError is raised.
# - it can be converted to a byte array of the appropriate size.
# - bit logic operations can be performed on it, such as AND, OR, XOR, NOT, and shifting with other data words objects.
# - it can be compared to other data words or numbers.
from __future__ import annotations
import math


class DataWord:
    def __init__(self, value: int | str | bytearray, size: int = 8):
        if size <= 0 or size > 64 != 0:
            raise ValueError(f'Data word size must be a positive integer between 1 and 64, got {size}')
        self._size = size
        if isinstance(value, str):
            self._value = int(value, 0)
        elif isinstance(value, bytearray):
            if len(value) > math.ceil(size / 8):
                raise OverflowError(f'Byte array {value} is too large for data word size {size}')
            self._value = int.from_bytes(value, 'big')
        else:
            self._value = value

        if not (0 <= self._value < 2 ** size):
            raise OverflowError(f'Value {self.value} is too large for data word size {size}')

    def to_bytes(self, endian: str = 'big') -> bytearray:
        return self._value.to_bytes(math.ceil(self._size / 8), endian)

    def __and__(self, other: DataWord | int) -> DataWord:
        if isinstance(other, DataWord):
            return DataWord(self._value & other._value, self._size)
        elif isinstance(other, int):
            return DataWord(self._value & other, self._size)
        else:
            raise TypeError(f'Unsupported type for AND operation: {type(other)}')

    def __or__(self, other: DataWord | int) -> DataWord:
        if isinstance(other, DataWord):
            return DataWord(self._value | other._value, self._size)
        elif isinstance(other, int):
            return DataWord(self._value | other, self._size)
        else:
            raise TypeError(f'Unsupported type for OR operation: {type(other)}')

    def __xor__(self, other: DataWord | int) -> DataWord:
        if isinstance(other, DataWord):
            return DataWord(self._value ^ other._value, self._size)
        elif isinstance(other, int):
            return DataWord(self._value ^ other, self._size)
        else:
            raise TypeError(f'Unsupported type for XOR operation: {type(other)}')

    def __invert__(self) -> DataWord:
        return DataWord(~self._value & (2 ** self._size - 1), self._size)

    def __lshift__(self, other: int) -> DataWord:
        if not isinstance(other, int):
            raise TypeError(f'Unsupported type for left shift operation: {type(other)}')
        return DataWord((self._value << other) & (2 ** self._size - 1), self._size)

    def __rshift__(self, other: int) -> DataWord:
        if not isinstance(other, int):
            raise TypeError(f'Unsupported type for right shift operation: {type(other)}')
        return DataWord(self._value >> other, self._size)

    def __eq__(self, other: DataWord | int) -> bool:
        if isinstance(other, DataWord):
            return self._value == other._value
        elif isinstance(other, int):
            return self._value == other
        else:
            raise TypeError(f'Unsupported type for equality check: {type(other)}')

    def __ne__(self, other: DataWord | int) -> bool:
        if isinstance(other, DataWord):
            return self._value != other._value
        elif isinstance(other, int):
            return self._value != other
        else:
            raise TypeError(f'Unsupported type for inequality check: {type(other)}')

    def __lt__(self, other: DataWord | int) -> bool:
        if isinstance(other, DataWord):
            return self._value < other._value
        elif isinstance(other, int):
            return self._value < other
        else:
            raise TypeError(f'Unsupported type for less than check: {type(other)}')

    def __le__(self, other: DataWord | int) -> bool:
        if isinstance(other, DataWord):
            return self._value <= other._value
        elif isinstance(other, int):
            return self._value <= other
        else:
            raise TypeError(f'Unsupported type for less than or equal check: {type(other)}')

    def __gt__(self, other: DataWord | int) -> bool:
        if isinstance(other, DataWord):
            return self._value > other._value
        elif isinstance(other, int):
            return self._value > other
        else:
            raise TypeError(f'Unsupported type for greater than check: {type(other)}')

    def __ge__(self, other: DataWord | int) -> bool:
        if isinstance(other, DataWord):
            return self._value >= other._value
        elif isinstance(other, int):
            return self._value >= other
        else:
            raise TypeError(f'Unsupported type for greater than or equal check: {type(other)}')

    def __repr__(self) -> str:
        return f'DataWord(value={self._value}, size={self._size})'

    def __str__(self) -> str:
        return f'DataWord(value={self._value}, size={self._size})'

    @property
    def value(self) -> int:
        return self._value

    @property
    def size(self) -> int:
        return self._size

    def __len__(self) -> int:
        """Returns the size of the data word in bytes."""
        if self._size <= 0:
            raise ValueError('Data word size must be positive')
        return math.ceil(self._size / 8)

    def __hash__(self) -> int:
        """Returns a hash of the data word based on its value and size."""
        return hash((self._value, self._size))

    def __bool__(self) -> bool:
        """Returns True if the data word is non-zero, False otherwise."""
        return self._value != 0

    def __int__(self) -> int:
        """Returns the integer value of the data word."""
        return self._value

    def __float__(self) -> float:
        """Returns the float value of the data word."""
        return float(self._value)

    def __index__(self) -> int:
        """Returns the integer value of the data word for use in slicing and other operations."""
        return self._value
