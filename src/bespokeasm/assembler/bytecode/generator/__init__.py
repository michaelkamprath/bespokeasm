import sys

from bespokeasm.assembler.bytecode.assembled import AssembledInstruction
from bespokeasm.assembler.bytecode.generator.instruction import InstructionBytecodeGenerator
from bespokeasm.assembler.bytecode.generator.macro import MacroBytecodeGenerator
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.model.instruction_macro import InstructionMacro
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
        memzone_manager: MemoryZoneManager,
        parser_class: type[InstructioParserBase],
    ) -> AssembledInstruction:
        if isinstance(instruction, Instruction):
            return InstructionBytecodeGenerator.generate_bytecode_parts(
                        instruction, line_id, mnemonic, operands, isa_model, memzone_manager
                    )
        elif isinstance(instruction, InstructionMacro):
            return MacroBytecodeGenerator.generate_bytecode_parts(
                        instruction, line_id, mnemonic, operands, isa_model, memzone_manager, parser_class
                    )

        sys.exit(f'ERROR: INTERNAL - BytecodeGenerator got an unknown instruction type - {instruction}')
