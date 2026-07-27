import math
from dataclasses import dataclass
from typing import Literal

from bespokeasm.assembler.analysis import InstructionAnalysisRecord
from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.expression import ExpressionNode


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
        analysis_record: InstructionAnalysisRecord | None = None,
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
        if analysis_record is not None:
            self._analysis_record = analysis_record
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
    def analysis_record(self) -> InstructionAnalysisRecord | None:
        return getattr(self, '_analysis_record', None)

    @property
    def analysis_records(self) -> tuple[InstructionAnalysisRecord, ...]:
        analysis_record = self.analysis_record
        if analysis_record is None:
            return ()
        return (analysis_record,)

    @property
    def flow_expression_nodes(self) -> tuple[ExpressionNode, ...]:
        """Return deferred flow nodes retained by emitted expression parts."""
        return tuple(
            node
            for part in self._parts
            if hasattr(part, 'parsed_expression')
            for node in part.parsed_expression.deferred_flow_nodes()
        )

    @property
    def analysis_units(self) -> tuple:
        """Pair this instruction's semantic record with its live expression nodes."""
        analysis_record = self.analysis_record
        if analysis_record is None:
            return ()
        return ((analysis_record, self.flow_expression_nodes),)

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
            symbol_scope: SymbolScope,
            active_named_scopes: ActiveNamedScopeList,
            instruction_address: int,
            instruction_size: int,
    ) -> list[Word]:
        '''
        Returns a list of words that represent the assembled instruction.

        :param symbol_scope: The lexical symbol scope used to resolve label values.
        :param instruction_address: The address of the instruction.
        :param instruction_size: The size of the instruction in words.
        :returns: A list of words that represent the assembled instruction.
        '''
        words: list[Word] = ByteCodePart.compact_parts_to_words(
            parts=self._parts,
            word_size=self._word_size,
            segment_size=self._segment_size,
            multi_word_endianness=self._multi_word_endian,
            symbol_scope=symbol_scope,
            active_named_scopes=active_named_scopes,
            instruction_address=instruction_address,
            instruction_size=instruction_size,
            bytecode_start_address=instruction_address,
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

    @property
    def analysis_records(self) -> tuple[InstructionAnalysisRecord, ...]:
        return tuple(
            record
            for instruction in self._instructions
            for record in instruction.analysis_records
        )

    @property
    def analysis_units(self) -> tuple:
        """Flatten analysis units from each real macro constituent in order."""
        return tuple(
            unit
            for instruction in self._instructions
            for unit in instruction.analysis_units
        )
