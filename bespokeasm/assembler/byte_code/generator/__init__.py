import sys
from typing import Type

from bespokeasm.assembler.byte_code.generator.instruction import InstructionBytecodeGenerator
from bespokeasm.assembler.byte_code.generator.macro import MacroBytecodeGenerator
from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.assembled import AssembledInstruction
from bespokeasm.assembler.model.instruction_macro import InstructionMacro
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser_base import InstructioParserBase


class BytecodeGenerator:

    @classmethod
    def generate_bytecode_parts(
        cls,
        instruction: InstructionBase,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        parser_class: Type[InstructioParserBase],
    ) -> AssembledInstruction:
        if isinstance(instruction, Instruction):
            return InstructionBytecodeGenerator.generate_bytecode_parts(
                        instruction, line_id, mnemonic, operands, isa_model
                    )
        elif isinstance(instruction, InstructionMacro):
            return MacroBytecodeGenerator.generate_bytecode_parts(
                        instruction, line_id, mnemonic, operands, isa_model, parser_class
                    )

        sys.exit(f'ERROR: INTERNAL - BytecodeGenerator got an unknown instruction type - {instruction}')
