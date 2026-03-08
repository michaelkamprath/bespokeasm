import math
from dataclasses import dataclass
from typing import Literal

from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.line_identifier import LineIdentifier


class AssembledInstruction:
    @dataclass(frozen=True)
    class OperandLabelBinding:
        label: str
        bytecode_part: ByteCodePart

    def __init__(
        self,
        line_id: LineIdentifier,
        parts: list[ByteCodePart],
        word_size: int,
        segment_size: int,
        multi_word_endian: Literal['little', 'big'],
        intra_word_endian: Literal['little', 'big'],
        operand_label_bindings: list[tuple[str, ByteCodePart]] | None = None,
    ):
        self._parts = parts
        self._line_id = line_id
        self._word_size = word_size
        self._segment_size = segment_size
        self._multi_word_endian = multi_word_endian
        self._intra_word_endian = intra_word_endian
        self._operand_label_bindings = [
            AssembledInstruction.OperandLabelBinding(label, part)
            for label, part in (operand_label_bindings or [])
        ]
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

    @property
    def has_operand_labels(self) -> bool:
        return len(self._operand_label_bindings) > 0

    def _get_part_start_bit_offset(self, target_part: ByteCodePart) -> int:
        bit_offset = 0
        for part in self._parts:
            if part.word_align and bit_offset % self._word_size != 0:
                bit_offset += self._word_size - (bit_offset % self._word_size)
            if part is target_part:
                return bit_offset
            bit_offset += part.value_size
        raise ValueError(
            'INTERNAL - Unable to locate operand-label target in emitted instruction parts.'
        )

    def get_operand_label_addresses(self, instruction_address: int) -> list[tuple[str, int]]:
        if instruction_address is None:
            raise ValueError(
                'INTERNAL - Instruction address is required to resolve operand labels.'
            )
        label_addresses: list[tuple[str, int]] = []
        for binding in self._operand_label_bindings:
            start_bit_offset = self._get_part_start_bit_offset(binding.bytecode_part)
            if start_bit_offset % self._word_size != 0:
                raise ValueError(
                    f'Operand label "{binding.label}" is invalid because '
                    f'its operand argument starts at non-word-aligned bit offset {start_bit_offset}.'
                )
            if binding.bytecode_part.value_size == 0:
                raise ValueError(
                    f'Operand label "{binding.label}" is invalid because '
                    'the annotated operand argument emits zero bits.'
                )
            if binding.bytecode_part.value_size % self._word_size != 0:
                raise ValueError(
                    f'Operand label "{binding.label}" is invalid because '
                    f'the annotated operand argument is not word-full '
                    f'({binding.bytecode_part.value_size} bits for word size {self._word_size}).'
                )
            label_addresses.append((binding.label, instruction_address + (start_bit_offset // self._word_size)))
        return label_addresses

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
