import re

from bespokeasm.assembler.analysis import SourceIdentity
from bespokeasm.assembler.bytecode.assembled import AssembledInstruction
from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePart
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
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
from bespokeasm.assembler.model.operand.value_selection import selecting_values
from bespokeasm.assembler.model.operand.value_selection import ValueSelection
from bespokeasm.assembler.parsing import split_line_comment
from bespokeasm.assembler.symbol_scope.named_scope_manager import NamedScopeManager


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
        raise AssemblerError(
            line_id,
            f'Mnemonic "{command_str}" uses undeclared {decorator_position} '
            f'decorator "{decorator_symbol}" for instruction root "{mnemonic_stem}". '
            f'Configured forms: {configured_forms}',
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
            source_ordinal: int = 0,
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

        last_error: AssemblerError | SystemExit | None = None
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
                    source_ordinal,
                )
            except (AssemblerError, SystemExit) as exc:
                # Candidates are tried longest first. The whole-line attempt knows about
                # every operand the user wrote, so its explanation is the most useful one.
                if last_error is None:
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
            source_ordinal: int = 0,
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
        self._memzone_manager = memzone_manager
        self._parse_identity = None
        if isa_model.analysis_records_enabled:
            self._parse_identity = SourceIdentity.from_line_id(line_id, source_ordinal)
            self._source_identity = self._parse_identity
        # Values aren't known yet, so `select_by_value` operands don't match and the line takes
        # another form; `relax` reconsiders it once pass 1 has set symbol values. A line with no
        # other form takes the value-selected one, and pass 2 checks its value.
        deferring = ValueSelection.deferring()
        try:
            self._assembled_instruction = self._match(deferring)
        except (AssemblerError, SystemExit):
            if not deferring.deferred:
                raise
            self._assembled_instruction = self._match(ValueSelection.assuming())
            deferring.deferred = False
        self._relaxable = deferring.deferred

    def _match(self, selection: ValueSelection) -> AssembledInstruction:
        with selecting_values(selection):
            return InstructioParser.parse_instruction(
                self._isa_model,
                self.line_id,
                self.instruction,
                self._memzone_manager,
                source_identity=self._parse_identity,
            )

    @property
    def relaxable(self) -> bool:
        """Whether a `select_by_value` form could still replace this line's form."""
        return self._relaxable

    def relax(self) -> bool:
        """Re-match the line against the symbol values pass 1 has set. A `select_by_value` form
        whose value is now in its zone replaces the line's form for good. Returns whether the
        line's size changed."""
        if not self._relaxable:
            return False
        # The line matched a form before, and known values only add forms, so this matches too.
        evaluating = ValueSelection.evaluating(self._known_value)
        assembled = self._match(evaluating)
        if not evaluating.selected_any(assembled.parts):
            return False
        if assembled.word_count > self.word_count:
            raise AssemblerError(
                self.line_id,
                f'the form that select_by_value selects for "{self.instruction.strip()}" is '
                f'{assembled.word_count} words, longer than the {self.word_count}-word form it would replace; '
                'a value-selected form must be no longer than the forms listed after it',
            )
        size_changed = assembled.word_count != self.word_count
        self._assembled_instruction = assembled
        self._relaxable = False
        return size_changed

    def _known_value(self, part: ExpressionByteCodePart) -> int | None:
        """The value of an operand's expression with the symbols set so far, or None."""
        try:
            value = part.parsed_expression.get_value(
                self.symbol_scope, self.active_named_scopes, self.line_id, self.address,
            )
        except (AssemblerError, ValueError, ArithmeticError):
            return None
        return value if isinstance(value, int) else None

    def __str__(self):
        return f'InstructionLine<{self.instruction.strip()} -> {self._assembled_instruction}>'

    @property
    def word_count(self) -> int:
        """Returns the number of words this instruction will generate"""
        return self._assembled_instruction.word_count

    @property
    def has_operand_labels(self) -> bool:
        return self._assembled_instruction.has_operand_labels

    @property
    def source_identity(self) -> SourceIdentity | None:
        return getattr(self, '_source_identity', None)

    @property
    def analysis_records(self):
        return self._assembled_instruction.analysis_records

    @property
    def analysis_units(self):
        """Expose semantic records and flow nodes for each real instruction."""
        return self._assembled_instruction.analysis_units

    @property
    def flow_expression_nodes(self):
        """Expose deferred flow expressions retained by instruction operands."""
        return self._assembled_instruction.flow_expression_nodes

    @property
    def flow_candidate_nodes(self):
        """Expose operand label leaves that may name counter coordinates."""
        return self._assembled_instruction.flow_candidate_nodes

    def get_operand_label_addresses(self) -> list[tuple[str, int]]:
        return self._assembled_instruction.get_operand_label_addresses(self.address)

    def register_operand_labels(self, named_scope_manager: NamedScopeManager, relocating: bool = False) -> None:
        for label, value in self.get_operand_label_addresses():
            if not named_scope_manager.set_label_value(
                label,
                value,
                self.line_id,
                self.active_named_scopes,
                relocating=relocating,
            ):
                self.symbol_scope.set_label_value(label, value, self.line_id, relocating=relocating)

    def generate_words(self) -> bytearray:
        """Finalize the bytes for this line with the label assignemnts"""
        self._words.extend(
            self._assembled_instruction.get_words(
                self.symbol_scope,
                self.active_named_scopes,
                self.address,
                self.word_count,
            )
        )
