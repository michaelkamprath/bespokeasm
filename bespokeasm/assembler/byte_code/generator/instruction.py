import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.assembled import AssembledInstruction
from bespokeasm.assembler.model.operand_parser import MatchedOperandSet
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart
from bespokeasm.assembler.model.instruction import Instruction, InstructionVariant
from bespokeasm.assembler.model import AssemblerModel


class InstructionBytecodeGenerator:

    @classmethod
    def generate_bytecode_parts(
        cls,
        instruction: Instruction,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
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
    ) -> AssembledInstruction:
        if mnemonic != variant.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {variant} to parse mnemonic "{mnemonic}"')
        if operands is not None and operands != '':
            operand_list = operands.strip().split(',')
        else:
            operand_list = []

        # generate the machine code parts
        instruction_endian = variant._variant_config['byte_code'].get('endian', isa_model.endian)
        base_bytecode = NumericByteCodePart(
            variant.base_bytecode_value,
            variant.base_bytecode_size,
            False,
            instruction_endian,
            line_id,
        )
        base_bytecode_suffix = None
        if variant.has_bytecode_suffix:
            base_bytecode_suffix = NumericByteCodePart(
                variant.suffix_bytecode_value,
                variant.suffix_bytecode_size,
                False,
                instruction_endian,
                line_id,
            )

        if variant._operand_parser is not None:
            matched_operands: MatchedOperandSet
            matched_operands = variant._operand_parser.find_matching_operands(line_id, operand_list, isa_model.registers)
            if matched_operands is None:
                return None
            machine_code = matched_operands.generate_byte_code(base_bytecode, base_bytecode_suffix)
        elif len(operand_list) > 0:
            # This variant was expecting no operands but some were found. No match.
            return None
        else:
            machine_code = [base_bytecode]

        return AssembledInstruction(line_id, machine_code)
