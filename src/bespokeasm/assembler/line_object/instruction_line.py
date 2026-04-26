import re
import sys

from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.emdedded_string import EMBEDDED_STRING_PATTERN
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.decorators import build_mnemonic_alternation
from bespokeasm.assembler.model.decorators import MNEMONIC_TOKEN_PATTERN
from bespokeasm.assembler.model.decorators import split_decorated_mnemonic
from bespokeasm.assembler.model.instruction_parser import InstructioParser
from bespokeasm.assembler.parsing import split_line_comment


class InstructionLine(LineWithWords):
    _INSTRUCTUION_EXTRACTION_PATTERN = None
    _INSTRUCTION_PATTERN_KEY = None

    @classmethod
    def reset_instruction_pattern_cache(cls):
        """Reset the instruction extraction pattern cache for test isolation."""
        cls._INSTRUCTUION_EXTRACTION_PATTERN = None
        cls._INSTRUCTION_PATTERN_KEY = None

    @classmethod
    def _ensure_instruction_pattern(cls, isa_model: AssemblerModel) -> None:
        pattern_key = tuple(isa_model.operation_mnemonics)
        if cls._INSTRUCTUION_EXTRACTION_PATTERN is not None and cls._INSTRUCTION_PATTERN_KEY == pattern_key:
            return

        instructions_regex = build_mnemonic_alternation(isa_model.operation_mnemonics)
        cls._INSTRUCTUION_EXTRACTION_PATTERN = re.compile(
            fr'(?:\s+(?:{instructions_regex})(?=\s|$))|\s*$|\s*{EMBEDDED_STRING_PATTERN}',
            flags=re.IGNORECASE | re.MULTILINE,
        )
        cls._INSTRUCTION_PATTERN_KEY = pattern_key

    @classmethod
    def _raise_decorator_error(
        cls,
        line_id: LineIdentifier,
        command_str: str,
        isa_model: AssemblerModel,
    ) -> None:
        decorated_token = split_decorated_mnemonic(command_str)
        if decorated_token is None:
            return

        mnemonic_stem, decorator_symbol, is_prefix = decorated_token
        if not isa_model.instructions.is_instruction_stem(mnemonic_stem):
            return

        configured_mnemonics = isa_model.instructions.configured_mnemonics_for_stem(mnemonic_stem)
        decorator_position = 'prefix' if is_prefix else 'postfix'
        configured_forms = ', '.join(f'"{mnemonic}"' for mnemonic in configured_mnemonics)
        sys.exit(
            f'ERROR: {line_id} - Mnemonic "{command_str}" uses undeclared {decorator_position} '
            f'decorator "{decorator_symbol}" for instruction root "{mnemonic_stem}". '
            f'Configured forms: {configured_forms}'
        )

    @classmethod
    def factory(
            cls,
            line_id: LineIdentifier,
            line_str: str,
            comment: str,
            isa_model: AssemblerModel,
            current_memzone: MemoryZone,
            memzone_manager: MemoryZoneManager,
    ) -> LineWithWords | None:
        """Tries to contruct a instruction line object from the passed instruction line"""
        instruction_content, _ = split_line_comment(line_str)
        instruction_content = instruction_content.strip()
        command_match = re.search(MNEMONIC_TOKEN_PATTERN, instruction_content)
        if command_match is None or len(command_match.groups()) != 1:
            return None

        command_str = command_match.group(1).strip().lower()
        if isa_model.instructions.get(command_str) is None:
            cls._raise_decorator_error(line_id, command_str, isa_model)
            return None

        cls._ensure_instruction_pattern(isa_model)
        command_end = command_match.end(1)
        instruction_tail = instruction_content[command_end:]
        candidate_end_positions = {len(instruction_content)}
        for instruction_end_match in re.finditer(cls._INSTRUCTUION_EXTRACTION_PATTERN, instruction_tail):
            candidate_end_positions.add(command_end + instruction_end_match.start())

        last_error: SystemExit | None = None
        for candidate_end in sorted(candidate_end_positions, reverse=True):
            instruction_str = instruction_content[:candidate_end].rstrip()
            argument_str = instruction_str.strip()[len(command_str):]
            try:
                return InstructionLine(
                    line_id,
                    command_str,
                    argument_str,
                    isa_model,
                    memzone_manager,
                    instruction_str,
                    comment,
                    current_memzone,
                )
            except SystemExit as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
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

    @property
    def has_operand_labels(self) -> bool:
        return self._assembled_instruction.has_operand_labels

    def get_operand_label_addresses(self) -> list[tuple[str, int]]:
        return self._assembled_instruction.get_operand_label_addresses(self.address)

    def register_operand_labels(self, named_scope_manager: NamedScopeManager) -> None:
        for label, value in self.get_operand_label_addresses():
            if not named_scope_manager.set_label_value(
                label,
                value,
                self.line_id,
                self.active_named_scopes,
            ):
                self.label_scope.set_label_value(label, value, self.line_id)

    def generate_words(self) -> bytearray:
        """Finalize the bytes for this line with the label assignemnts"""
        self._words.extend(
            self._assembled_instruction.get_words(
                self.label_scope,
                self.active_named_scopes,
                self.address,
                self.word_count,
            )
        )
