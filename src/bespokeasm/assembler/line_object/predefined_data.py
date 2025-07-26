"""
This module defines the PredefinedDataLine class, which represents a line object that generates a sequence of repeated words
for bytecode output. Each word is of a specified size and value, and the line is used to efficiently represent large blocks
of repeated data in the assembled output.
"""
from typing import Literal
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.memory_zone import MemoryZone


class PredefinedDataLine(LineWithWords):
    """
    Represents a line object that generates a sequence of repeated words for bytecode output.

    This is used to efficiently represent a block of memory initialized to a repeated value, such as for zero-filling or
    pattern-filling memory regions. The number of words, the value to repeat, and word formatting are all configurable.
    """
    def __init__(
            self,
            line_id: LineIdentifier,
            word_count: int,
            value: int,
            name: str,
            current_memzone: MemoryZone,
            word_size: int,
            word_segment_size: int,
            intra_word_endianness: Literal['little', 'big'],
            multi_word_endianness: Literal['little', 'big'],
    ) -> None:
        """
        Initialize a PredefinedDataLine.

        Args:
            line_id (LineIdentifier): Unique identifier for this line in the source.
            word_count (int): Number of words to generate.
            value (int): The value to repeat in each word.
            name (str): Name or label for this line.
            current_memzone (MemoryZone): The memory zone this line belongs to.
            word_size (int): Size of each word in bits.
            word_segment_size (int): Size of each word segment in bits.
            intra_word_endianness (Literal['little', 'big']): Endianness within each word.
            multi_word_endianness (Literal['little', 'big']): Endianness across multiple words.
        """
        super().__init__(
            line_id,
            f'.predefined_data [{value}]*{word_count}',
            name,
            current_memzone,
            word_size,
            word_segment_size,
            intra_word_endianness,
            multi_word_endianness,
        )
        self._word_count = word_count
        self._value = value

    def __str__(self):
        """
        Return a string representation of the PredefinedDataLine for debugging.
        """
        return f'PredefinedDataLine<{self.comment}>'

    @property
    def word_count(self) -> int:
        """
        Returns the number of words this data line will generate.
        """
        return self._word_count

    def generate_words(self):
        """
        Generate the repeated words for this line and append them to the internal word list.
        Each word will have the specified value, masked to the word size.
        """
        word_mask = (1 << self._word_size) - 1
        words = [
            Word(self._value & word_mask, self._word_size, self._word_segment_size, self._intra_word_endianness)
            for _ in range(self._word_count)
        ]
        self._words.extend(words)
