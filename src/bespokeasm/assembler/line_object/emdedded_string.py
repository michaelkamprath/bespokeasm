# an embedded string line object is a string that has its bytecode embdedded where the string is
# in the code. Essential, it is a `.cstr` line object but without the `.cstr` prefix. The
# embedded string feature must be enabled in the ISA configuration file, whether there is a
# termination character or not to be included in the bytecode.
from __future__ import annotations

import math
import re
from typing import Literal

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.memory_zone import MemoryZone


EMBEDDED_STRING_PATTERN = r'(?P<quote>[\"])((?:\\(?P=quote)|.|\n)*?)(?P=quote)'


class EmbeddedString(LineWithWords):
    QUOTED_STRING_PATTERN = re.compile(
        rf'^{EMBEDDED_STRING_PATTERN}',
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )

    @classmethod
    def factory(
            cls,
            line_id: LineIdentifier,
            instruction: str,
            comment: str,
            current_memzone: MemoryZone,
            word_size: int,
            word_segment_size: int,
            intra_word_endianness: Literal['little', 'big'],
            multi_word_endianness: Literal['little', 'big'],
            cstr_terminator: int = 0,
    ) -> EmbeddedString:
        # detyermine if string starts with a quoted string
        match = re.search(EmbeddedString.QUOTED_STRING_PATTERN, instruction)
        if match is None or len(match.groups()) != 2:
            return None

        return EmbeddedString(
            line_id,
            match.group(0),
            match.group(2),
            comment,
            current_memzone,
            word_size,
            word_segment_size,
            intra_word_endianness,
            multi_word_endianness,
            cstr_terminator,
        )

    def __init__(
            self,
            line_id: LineIdentifier,
            instruction: str,
            quoted_string: str,
            comment: str,
            current_memzone: MemoryZone,
            word_size: int,
            word_segment_size: int,
            intra_word_endianness: Literal['little', 'big'],
            multi_word_endianness: Literal['little', 'big'],
            cstr_terminator: int = 0,
    ) -> None:
        super().__init__(
            line_id,
            instruction,
            comment,
            current_memzone,
            word_size,
            word_segment_size,
            intra_word_endianness,
            multi_word_endianness,
        )
        self._string_bytes = \
            [ord(x) for x in list(bytes(quoted_string, 'utf-8').decode('unicode_escape'))] \
            + [cstr_terminator]

    def __str__(self):
        return f'EmbeddedString<{self.instruction}, size={self.byte_size}, chars={self._string_bytes}>'

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this data line will generate"""
        return len(self._string_bytes)

    @property
    def word_count(self) -> int:
        # TODO: reconcile this to final rules for data compilation
        return math.ceil(self.byte_size*8 / self._word_size)

    def generate_words(self) -> None:
        # set the bytes
        for c in self._string_bytes:
            self._words.append(Word(c, self._word_size, self._word_segment_size, self._intra_word_endianness))
