import sys

from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.assembled import AssembledInstruction
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class InstructioParserBase:
    '''Template for InstructionParser. Exists to prevent circular imports.'''
    @classmethod
    def parse_instruction(
        cls,
        isa_model: AssemblerModel,
        line_id: LineIdentifier,
        instruction: str,
        memzone_manager: MemoryZoneManager,
    ) -> AssembledInstruction:
        sys.exit('ERROR: INTERNAL - called InstructioParserBase.parse_instruction')
