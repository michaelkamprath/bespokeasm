from typing import Literal
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.memory_zone import MemoryZone


class PredefinedDataLine(LineWithWords):
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
        return f'PredefinedDataLine<{self.comment}>'

    @property
    def word_count(self) -> int:
        """Returns the number of words this data line will generate"""
        return self._word_count

    def generate_words(self):
        word_mask = (1 << self._word_size) - 1
        words = [
            Word(self._value & word_mask, self._word_size, self._word_segment_size, self._intra_word_endianness)
            for _ in range(self._word_count)
        ]
        self._words.extend(words)
