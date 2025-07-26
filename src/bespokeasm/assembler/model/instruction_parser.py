import sys

from bespokeasm.assembler.bytecode.assembled import AssembledInstruction
from bespokeasm.assembler.bytecode.generator import BytecodeGenerator
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.model.instruction_parser_base import InstructioParserBase


class InstructioParser(InstructioParserBase):
    @classmethod
    def parse_instruction(
        cls,
        isa_model: AssemblerModel,
        line_id: LineIdentifier,
        instruction: str,
        memzone_manager: MemoryZoneManager,
    ) -> AssembledInstruction:
        instr_parts = instruction.strip().split(' ', 1)
        mnemonic = instr_parts[0].lower()
        if len(instr_parts) > 1:
            operands = instr_parts[1]
        else:
            operands = ''

        instr_obj: InstructionBase = isa_model.instructions.get(mnemonic)
        if instr_obj is None:
            sys.exit(f'ERROR: {line_id} - Unrecognized mnemonic "{mnemonic}"')

        return BytecodeGenerator.generate_bytecode_parts(
            instr_obj,
            line_id,
            mnemonic,
            operands,
            isa_model,
            memzone_manager,
            InstructioParser
        )
