import sys

from bespokeasm.assembler.bytecode.assembled import AssembledInstruction
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction import InstructionVariant
from bespokeasm.assembler.model.operand_parser import MatchedOperandSet


class InstructionBytecodeGenerator:

    @classmethod
    def generate_bytecode_parts(
        cls,
        instruction: Instruction,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        memzone_manager: MemoryZoneManager,
    ) -> AssembledInstruction:
        if mnemonic != instruction.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {instruction} to parse mnemonic "{mnemonic}"')

        for variant in instruction.variants:
            assembled_instruction = InstructionBytecodeGenerator.generate_variant_bytecode_parts(
                variant,
                line_id,
                mnemonic,
                operands,
                isa_model,
                memzone_manager,
            )
            if assembled_instruction is not None:
                return assembled_instruction

        sys.exit(f'ERROR: {line_id} - Instruction "{mnemonic}" has no valid operands configured.')

    @classmethod
    def generate_variant_bytecode_parts(
        cls,
        variant: InstructionVariant,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        memzone_manager: MemoryZoneManager,
    ) -> AssembledInstruction:
        if mnemonic != variant.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {variant} to parse mnemonic "{mnemonic}"')
        if operands is not None and operands != '':
            operand_list = operands.strip().split(',')
        else:
            operand_list = []

        # generate the machine code parts
        multi_word_endian = variant._variant_config['bytecode'].get('multi_word_endian', isa_model.multi_word_endianness)
        intra_word_endian = variant._variant_config['bytecode'].get('intra_word_endian', isa_model.intra_word_endianness)
        base_bytecode = NumericByteCodePart(
            variant.base_bytecode_value,
            variant.base_bytecode_size,
            False,
            multi_word_endian,
            intra_word_endian,
            line_id,
            isa_model.word_size,
            isa_model.word_segment_size,
        )
        base_bytecode_suffix = None
        if variant.has_bytecode_suffix:
            base_bytecode_suffix = NumericByteCodePart(
                variant.suffix_bytecode_value,
                variant.suffix_bytecode_size,
                False,
                multi_word_endian,
                intra_word_endian,
                line_id,
                isa_model.word_size,
                isa_model.word_segment_size,
            )

        if variant._operand_parser is not None:
            matched_operands: MatchedOperandSet
            matched_operands = variant._operand_parser.find_matching_operands(
                line_id, operand_list, isa_model.registers, memzone_manager,
            )
            if matched_operands is None:
                return None
            machine_code = matched_operands.generate_bytecode(base_bytecode, base_bytecode_suffix)
        elif len(operand_list) > 0:
            # This variant was expecting no operands but some were found. No match.
            return None
        else:
            machine_code = [base_bytecode]

        return AssembledInstruction(
            line_id,
            machine_code,
            isa_model.word_size,
            isa_model.word_segment_size,
            multi_word_endian,
            intra_word_endian,
        )
