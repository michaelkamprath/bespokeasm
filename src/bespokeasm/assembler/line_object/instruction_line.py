import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.emdedded_string import EMBEDDED_STRING_PATTERN
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser import InstructioParser


class InstructionLine(LineWithWords):
    COMMAND_EXTRACT_PATTERN = re.compile(r'^\s*(\w[\w\._]*)', flags=re.IGNORECASE | re.MULTILINE)

    _INSTRUCTUION_EXTRACTION_PATTERN = None

    @classmethod
    def factory(
            cls,
            line_id: LineIdentifier,
            line_str: str,
            comment: str,
            isa_model: AssemblerModel,
            current_memzone: MemoryZone,
            memzone_manager: MemoryZoneManager,
    ) -> LineWithWords:
        """Tries to contruct a instruction line object from the passed instruction line"""
        # first, extract evertything up to the next extruction
        if cls._INSTRUCTUION_EXTRACTION_PATTERN is None:
            instructions_regex = '\\b' + '\\b|\\b'.join(isa_model.operation_mnemonics) + '\\b'
            # replace any period characters in instructions with escaped period characters
            instructions_regex = instructions_regex.replace('.', '\\.')
            cls._INSTRUCTUION_EXTRACTION_PATTERN = re.compile(
                fr'(?i)^((?:{instructions_regex}).*?(?=(?:{instructions_regex})'
                fr'|\s*\;|\s*$|\s*{EMBEDDED_STRING_PATTERN}))',
                flags=re.IGNORECASE | re.MULTILINE,
            )
        instruction_match = re.search(cls._INSTRUCTUION_EXTRACTION_PATTERN, line_str.strip())
        if instruction_match is not None:
            instruction_str = instruction_match.group(0)

            # extract the instruction command
            command_match = re.search(cls.COMMAND_EXTRACT_PATTERN, instruction_str)
            if command_match is None or len(command_match.groups()) != 1:
                sys.exit(f'ERROR: {line_id} - Wrongly formatted instruction: {instruction_str}')
            command_str = command_match.group(1).strip().lower()
            if command_str not in isa_model.operation_mnemonics:
                sys.exit(f'ERROR: {line_id} - Unreconized instruction: {instruction_str}')

            argument_str = instruction_str.strip()[len(command_str):]

            return InstructionLine(
                line_id, command_str, argument_str, isa_model,
                memzone_manager, instruction_str, comment, current_memzone,
            )
        else:
            return None

    def __init__(
            self,
            line_id: LineIdentifier,
            command_str: str,
            argument_str: str,
            isa_model: AssemblerModel,
            memzone_manager: MemoryZoneManager,
            instruction: str,
            comment: str,
            current_memzone: MemoryZone,
    ):
        super().__init__(
            line_id, instruction, comment, current_memzone,
            isa_model.word_size,
            isa_model.word_segment_size,
            isa_model.intra_word_endianness,
            isa_model.multi_word_endianness,
        )
        self._command = command_str
        self._argument_str = argument_str
        self._isa_model = isa_model
        self._assembled_instruction = InstructioParser.parse_instruction(
            self._isa_model, line_id, instruction, memzone_manager,
        )

    def __str__(self):
        return f'InstructionLine<{self.instruction.strip()} -> {self._assembled_instruction}>'

    @property
    def word_count(self) -> int:
        """Returns the number of words this instruction will generate"""
        return self._assembled_instruction.word_count

    def generate_words(self) -> bytearray:
        """Finalize the bytes for this line with the label assignemnts"""
        self._words.extend(self._assembled_instruction.get_words(self.label_scope, self.address, self.word_count))
