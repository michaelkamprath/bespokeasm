import sys

from bespokeasm.assembler.byte_code.generator.instruction import InstructionBytecodeGenerator
from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.assembled import AssembledInstruction
from bespokeasm.assembler.model.operand_parser import MatchedOperandSet
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart
from bespokeasm.assembler.model.instruction import Instruction, InstructionVariant
from bespokeasm.assembler.model import AssemblerModel

class BytecodeGenerator:

    @classmethod
    def generate_bytecode_parts(
        cls,
        instruction: InstructionBase,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
    ) -> AssembledInstruction:
        if isinstance(instruction, Instruction):
            return InstructionBytecodeGenerator.generate_bytecode_parts(instruction, line_id, mnemonic, operands, isa_model)
        sys.exit(f'ERROR: INTERNAL - BytecodeGenerator got an unknown instruction type - {instruction}')
