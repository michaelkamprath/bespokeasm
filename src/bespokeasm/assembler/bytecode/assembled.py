import math
from typing import Literal

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.bytecode.word import Word


class AssembledInstruction:
    def __init__(
        self,
        line_id: LineIdentifier,
        parts: list[ByteCodePart],
        word_size: int,
        segment_size: int,
        endian: Literal['little', 'big'],
    ):
        self._parts = parts
        self._line_id = line_id
        self._word_size = word_size
        self._segment_size = segment_size
        self._endian = endian
        # calculate total bytes
        total_bits = 0
        for bcp in self._parts:
            if bcp.word_align:
                if total_bits % 8 != 0:
                    total_bits += 8 - total_bits % 8
            total_bits += bcp.value_size
        self._byte_size = math.ceil(total_bits/8)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'AssembledInstruction{self._parts}'

    @property
    def byte_size(self):
        return self._byte_size

    @property
    def line_id(self):
        return self._line_id

    @property
    def parts(self):
        return self._parts

    def get_words(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> list[Word]:
        words: list[Word] = ByteCodePart.compact_parts_to_words(
            self._parts,
            self._word_size,
            self._segment_size,
            self._endian,
            label_scope,
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
        endian: Literal['little', 'big'],
    ):
        # turn instruction list into byte code parts list
        parts: list[ByteCodePart] = [
            p for instr in instructions for p in instr.parts
        ]
        super().__init__(line_id, parts, word_size, segment_size, endian)
        self._instructions = instructions

    @property
    def instructions(self):
        return self._instructions
