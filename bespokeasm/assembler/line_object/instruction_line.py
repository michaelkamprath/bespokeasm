import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser import InstructioParser

class InstructionLine(LineWithBytes):
    COMMAND_EXTRACT_PATTERN = re.compile(r'^\s*(\w+)', flags=re.IGNORECASE|re.MULTILINE)

    def factory(line_id: LineIdentifier, line_str: str, comment: str, isa_model: AssemblerModel):
        """Tries to contruct a instruction line object from the passed instruction line"""
        #extract the instruction command
        command_match = re.search(InstructionLine.COMMAND_EXTRACT_PATTERN, line_str)
        if command_match is None or len(command_match.groups()) != 1:
            sys.exit(f'ERROR: {line_id} - Wrongly formatted instruction: {line_str}')
        command_str = command_match.group(1).strip().lower()
        if command_str not in isa_model.instruction_mnemonics:
            sys.exit(f'ERROR: {line_id} - Unreconized instruction: {line_str}')
        argument_str = line_str.strip()[len(command_str):]
        return InstructionLine(line_id, command_str, argument_str, isa_model, line_str, comment)

    def __init__(
            self,
            line_id: LineIdentifier,
            command_str: str,
            argument_str: str,
            isa_model: AssemblerModel,
            instruction: str,
            comment: str
        ):
        super().__init__(line_id, instruction, comment)
        self._command = command_str
        self._argument_str = argument_str
        self._isa_model = isa_model
        self._assembled_instruction = InstructioParser.parse_instruction(self._isa_model, line_id, instruction)
    def __str__(self):
        return f'InstructionLine<{self.instruction.strip()} -> {self._assembled_instruction}>'

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this instruction will generate"""
        return self._assembled_instruction.byte_size

    def generate_bytes(self) -> bytearray:
        """Finalize the bytes for this line with the label assignemnts"""
        self._bytes.extend(self._assembled_instruction.get_bytes(self.label_scope))