import re
import sys

from bespokeasm.assembler.line_object import LineWithBytes
from bespokeasm.assembler.model import AssemblerModel


class InstructionLine(LineWithBytes):
    COMMAND_EXTRACT_PATTERN = re.compile(r'^\s*(\w+)', flags=re.IGNORECASE|re.MULTILINE)

    def factory(line_num: int, line_str: str, comment: str, isa_model: AssemblerModel):
        """Tries to contruct a instruction line object from the passed instruction line"""
        #extract the instruction command
        command_match = re.search(InstructionLine.COMMAND_EXTRACT_PATTERN, line_str)
        if command_match is None or len(command_match.groups()) != 1:
            sys.exit(f'ERROR: line {line_num} - Wrongly formatted instruction: {line_str}')
        command_str = command_match.group(1).strip()
        if command_str not in isa_model.instruction_mnemonics:
            sys.exit(f'ERROR: line {line_num} - Unreconized instruction: {line_str}')
        argument_str = line_str.strip()[len(command_str):]
        return InstructionLine(line_num, command_str, argument_str, isa_model, line_str, comment)

    def __init__(
            self,
            line_num: int,
            command_str: str,
            argument_str: str,
            isa_model: AssemblerModel,
            instruction: str,
            comment: str
        ):
        super().__init__(line_num, instruction, comment)
        self._command = command_str
        self._argument_str = argument_str
        self._isa_model = isa_model
        self._assembled_instruction = self._isa_model.parse_instruction(line_num, instruction)
    def __str__(self):
        return f'InstructionLine<{self.instruction.strip()} -> {self._assembled_instruction}>'

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this instruction will generate"""
        return self._assembled_instruction.byte_size

    def generate_bytes(self, label_dict: dict[str, int]) -> bytearray:
        """Finalize the bytes for this line with the label assignemnts"""
        self._bytes.extend(self._assembled_instruction.get_bytes(label_dict))