import math
from typing import Literal

from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.line_identifier import LineIdentifier


class AssembledInstruction:
    def __init__(
        self,
        line_id: LineIdentifier,
        parts: list[ByteCodePart],
        word_size: int,
        segment_size: int,
        multi_word_endian: Literal['little', 'big'],
        intra_word_endian: Literal['little', 'big'],
    ):
        self._parts = parts
        self._line_id = line_id
        self._word_size = word_size
        self._segment_size = segment_size
        self._multi_word_endian = multi_word_endian
        self._intra_word_endian = intra_word_endian
        # calculate word count
        total_bits = 0
        for bcp in self._parts:
            if bcp.word_align:
                if total_bits % self._word_size != 0:
                    total_bits += self._word_size - total_bits % self._word_size
            total_bits += bcp.value_size
        self._word_count = math.ceil(total_bits/self._word_size)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'AssembledInstruction{self._parts}'

    @property
    def word_count(self):
        '''Returns the number of words this instruction will generate'''
        return self._word_count

    @property
    def line_id(self):
        return self._line_id

    @property
    def parts(self):
        return self._parts

    def get_words(
            self,
            label_scope: LabelScope,
            active_named_scopes: ActiveNamedScopeList,
            instruction_address: int,
            instruction_size: int,
    ) -> list[Word]:
        '''
        Returns a list of words that represent the assembled instruction.

        :param label_scope: The label scope to use for resolving label values.
        :param instruction_address: The address of the instruction.
        :param instruction_size: The size of the instruction in words.
        :returns: A list of words that represent the assembled instruction.
        '''
        words: list[Word] = ByteCodePart.compact_parts_to_words(
            self._parts,
            self._word_size,
            self._segment_size,
            self._multi_word_endian,
            label_scope,
            active_named_scopes,
            instruction_address,
            instruction_size,
        )
        return words


class CompositeAssembledInstruction(AssembledInstruction):
    def __init__(
        self,
        line_id: LineIdentifier,
        instructions: list[AssembledInstruction],
        word_size: int,
        segment_size: int,
        multi_word_endian: Literal['little', 'big'],
        intra_word_endian: Literal['little', 'big'],
    ):
        # turn instruction list into byte code parts list
        parts: list[ByteCodePart] = [
            p for instr in instructions for p in instr.parts
        ]
        super().__init__(line_id, parts, word_size, segment_size, multi_word_endian, intra_word_endian)
        self._instructions = instructions

    @property
    def instructions(self):
        return self._instructions
