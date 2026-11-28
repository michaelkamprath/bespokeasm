import difflib
import re

from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import preprocessor_directives_for_isa
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.counter_coordinate_line import CounterCoordinateLine
from bespokeasm.assembler.line_object.directive_line.factory import DirectiveLine
from bespokeasm.assembler.line_object.directive_line.factory import resolve_directive_alias
from bespokeasm.assembler.line_object.emdedded_string import EmbeddedString
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line.factory import PreprocessorLineFactory
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import (
    resolve_symbols_protecting_flow_names,
)
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.parsing import split_line_comment
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.utilities import PATTERN_SYMBOL


class LineOjectFactory:
    _FLOW_EXPRESSION_PATTERN = re.compile(
        r'\b(?:COORDINATE|COUNTER)\s*\(',
        flags=re.IGNORECASE,
    )
    _COORDINATE_EXPRESSION_PATTERN = re.compile(
        r'\bCOORDINATE\s*\(',
        flags=re.IGNORECASE,
    )
    # \b keeps a label that merely starts with a directive name (".orglabel:")
    # from being mistaken for the directive itself.
    _LAYOUT_DIRECTIVE_PATTERN = re.compile(
        r'\.(?:org|align|zerountil|zero)\b',
        flags=re.IGNORECASE,
    )
    _FILL_DIRECTIVE_PATTERN = re.compile(
        r'\.fill\b',
        flags=re.IGNORECASE,
    )
    _FLOW_DIRECTIVE_PATTERN = re.compile(
        r'^#(?:assert|set|resume)\b',
    )

    @classmethod
    def _flow_expression_error(
        cls,
        line_id: LineIdentifier,
        model: AssemblerModel,
        context: str,
    ) -> None:
        """Report the capability-appropriate diagnostic for a forbidden use."""
        if not model.flow_counters_enabled:
            message = 'this instruction set does not enable flow counters'
        else:
            message = f'flow expressions are not allowed in {context}'
        model.diagnostic_reporter.error(line_id, message, category='flow')

    @classmethod
    def _validate_flow_expression_context(
        cls,
        line_id: LineIdentifier,
        instruction: str,
        model: AssemblerModel,
    ) -> None:
        """Reject flow operators before they can affect layout or selection."""
        if cls._FLOW_EXPRESSION_PATTERN.search(instruction) is None:
            return
        # An alias such as `.res` for `.fill` follows the rules of the directive it stands for.
        instruction, _ = resolve_directive_alias(instruction, model.directive_aliases)
        if (
            cls._COORDINATE_EXPRESSION_PATTERN.search(instruction)
            and ':=' not in instruction
        ):
            cls._flow_expression_error(
                line_id,
                model,
                'anything except a := counter-coordinate declaration',
            )
        if (
            instruction.startswith('#')
            and cls._FLOW_DIRECTIVE_PATTERN.match(instruction) is None
        ):
            if instruction.startswith(('#if ', '#elif ', '#ifdef ', '#ifndef ')):
                context = 'conditional-compilation directives'
            elif instruction.startswith('#require '):
                context = 'version requirements'
            else:
                context = 'preprocessor directives'
            cls._flow_expression_error(line_id, model, context)
        if cls._LAYOUT_DIRECTIVE_PATTERN.match(instruction):
            cls._flow_expression_error(line_id, model, 'layout expressions')
        if cls._FILL_DIRECTIVE_PATTERN.match(instruction):
            arguments = instruction.split(None, 1)
            count_expression = arguments[1].split(',', 1)[0] if len(arguments) > 1 else ''
            if cls._FLOW_EXPRESSION_PATTERN.search(count_expression):
                cls._flow_expression_error(line_id, model, 'fill-count expressions')
        if re.match(
            fr'^\s*{PATTERN_SYMBOL}\s*(?:=|\bEQU\b)',
            instruction,
            flags=re.IGNORECASE,
        ):
            cls._flow_expression_error(line_id, model, 'ordinary constant assignments')

    _DIRECTIVE_ARGUMENT_HINTS = {
        '.org': 'requires an address, for example ".org 0x100"',
        '.phase': 'requires the address to assemble for, for example ".phase 0xfc00"',
        '.dephase': 'takes no arguments',
        '.memzone': 'requires the name of a memory zone, for example ".memzone GLOBAL"',
        '.fill': 'requires a count and an optional fill value, for example ".fill 16" or ".fill 16, $FF"',
        '.zero': 'requires a count, for example ".zero 16"',
        '.zerountil': 'requires an end address, for example ".zerountil 0x0FFF"',
        '.align': 'takes an optional alignment value, for example ".align 256"',
        '.byte': 'requires at least one value or string, for example ".byte 1, 2, 3"',
        '.2byte': 'requires at least one value, for example ".2byte 0x1234"',
        '.4byte': 'requires at least one value, for example ".4byte 0x12345678"',
        '.8byte': 'requires at least one value',
        '.16byte': 'requires at least one value',
        '.cstr': 'requires a quoted string, for example \'.cstr "hello"\'',
        '.asciiz': 'requires a quoted string, for example \'.asciiz "hello"\'',
    }

    @staticmethod
    def _suggestion(word: str, candidates: list[str]) -> str:
        """Return a "; did you mean ..." suffix for the closest known names, or an empty string."""
        lowered = {candidate.lower(): candidate for candidate in candidates}
        matches = difflib.get_close_matches(word.lower(), list(lowered), n=2, cutoff=0.7)
        if not matches:
            return ''
        names = ' or '.join(f'"{lowered[match]}"' for match in matches)
        return f'; did you mean {names}?'

    @classmethod
    def _warn_if_symbol_shadows_mnemonic(cls, line_id: LineIdentifier, label_obj: LabelLine, model: AssemblerModel) -> None:
        name = label_obj.get_label()
        if model.instructions.get(name.lower()) is None:
            return
        kind = 'constant' if label_obj.is_constant else 'label'
        model.diagnostic_reporter.warn(
            line_id,
            f'{kind} "{name}" has the same name as an instruction mnemonic; a line that starts with "{name}" '
            'followed by operands will be assembled as that instruction',
        )

    @classmethod
    def _report_unparsable_text(
        cls,
        line_id: LineIdentifier,
        instruction_str: str,
        model: AssemblerModel,
    ) -> None:
        """Report source text that is not a label, constant, directive, or instruction.

        The generic "unknown instruction" wording hides several distinct mistakes, so the
        text is classified first and each class gets a message that says what to fix.
        """
        text = instruction_str.strip()
        reporter = model.diagnostic_reporter
        first_word = text.split(None, 1)[0]

        if text.startswith('#'):
            known = sorted(f'#{name}' for name in preprocessor_directives_for_isa(model.flow_counters_enabled))
            reporter.error(
                line_id,
                f'unknown preprocessor directive "{first_word}"{cls._suggestion(first_word, known)}',
            )

        if text.startswith('.'):
            name_match = re.match(r'\.\w+', text)
            directive = name_match.group(0).lower() if name_match else first_word
            aliases = model.directive_aliases
            target = f'.{aliases[directive[1:]]}' if directive[1:] in aliases else directive
            if target in cls._DIRECTIVE_ARGUMENT_HINTS:
                hint = cls._DIRECTIVE_ARGUMENT_HINTS[target].replace(f'"{target} ', f'"{directive} ')
                reporter.error(line_id, f'{directive} directive {hint}')
            known = sorted(f'.{name}' for name in COMPILER_DIRECTIVES_SET | BYTECODE_DIRECTIVES_SET | set(aliases))
            reporter.error(line_id, f'unknown directive "{directive}"{cls._suggestion(directive, known)}')

        constant_match = re.fullmatch(fr'({PATTERN_SYMBOL})\s*(?:=|EQU)', text, flags=re.IGNORECASE)
        if constant_match is not None:
            reporter.error(line_id, f'constant "{constant_match.group(1)}" is missing a value after "="')

        if re.fullmatch(PATTERN_SYMBOL, text) is not None:
            suggestion = cls._suggestion(text, model.operation_mnemonics)
            if suggestion:
                suggestion = suggestion.replace('; did you mean', '; if it is an instruction, did you mean', 1)
            reporter.error(
                line_id,
                f'unknown instruction "{text}"; if this is meant to be a label, write it with a colon '
                f'as "{text}:"{suggestion}',
            )

        if re.fullmatch(fr'{PATTERN_SYMBOL}(?:\s+{PATTERN_SYMBOL})+:', text) is not None:
            reporter.error(line_id, f'label "{text[:-1]}" is not valid; label names cannot contain spaces')

        quoted = f'"{first_word}" in "{text}"' if first_word != text else f'"{text}"'
        reporter.error(
            line_id,
            f'unknown instruction {quoted}{cls._suggestion(first_word, model.operation_mnemonics)}',
        )

    @classmethod
    def parse_line(
                cls,
                line_id: LineIdentifier,
                line_str: str,
                model: AssemblerModel,
                symbol_scope: SymbolScope,
                active_named_scopes: ActiveNamedScopeList,
                current_memzone: MemoryZone,
                memzone_manager: MemoryZoneManager,
                preprocessor: Preprocessor,
                condition_stack: ConditionStack,
                log_verbosity: int,
                filename: str = None,
            ) -> list[LineObject]:
        instruction_portion, comment_portion = split_line_comment(line_str)
        comment_str = comment_portion.strip()
        instruction_str = instruction_portion.strip()
        cls._validate_flow_expression_context(line_id, instruction_str, model)

        line_obj_list: list[LineObject] = []
        label_seen = False
        # check to see if this is preprocessor directive
        if instruction_str.startswith('#'):
            # this is a preprocessor directive
            line_obj_list.extend(PreprocessorLineFactory.parse_line(
                    line_id,
                    instruction_str,
                    comment_str,
                    model,
                    symbol_scope,
                    active_named_scopes,
                    current_memzone,
                    memzone_manager,
                    preprocessor,
                    condition_stack,
                    log_verbosity,
                    filename,
                ))
        else:
            # resolve preprocessor symbols; the names passed to flow operators
            # identify flow entities and stay literal in every context
            instruction_str = resolve_symbols_protecting_flow_names(
                preprocessor,
                line_id,
                instruction_str,
            )
            cls._validate_flow_expression_context(line_id, instruction_str, model)
            # parse instruction
            first_fragment = True
            while len(instruction_str) > 0:
                # Re-validate every fragment after the first: a leading label can
                # hide a layout directive from the whole-line check above
                # ("start: .org COUNTER(...)"), and flow expressions must be
                # rejected before any layout parsing sees them.
                if not first_fragment:
                    cls._validate_flow_expression_context(line_id, instruction_str, model)
                first_fragment = False
                # Counter coordinates must precede colon-style label parsing:
                # otherwise ``.slot := ...`` looks like label ``.slot:``.
                line_obj = CounterCoordinateLine.factory(
                    line_id,
                    instruction_str,
                    comment_str,
                    current_memzone,
                    model,
                )
                if line_obj is not None:
                    if label_seen:
                        model.diagnostic_reporter.error(
                            line_id,
                            'only one label or coordinate declaration is allowed per line',
                        )
                    line_obj_list.append(line_obj)
                    label_seen = True
                    instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                    continue

                # try label
                line_obj: LineObject = LabelLine.factory(
                    line_id,
                    instruction_str,
                    comment_str,
                    model.registers,
                    symbol_scope,
                    active_named_scopes,
                    current_memzone,
                    default_numeric_base=model.expression_syntax,
                )
                if line_obj is not None:
                    if label_seen:
                        model.diagnostic_reporter.error(line_id, 'only one label or constant assignment is allowed per line')
                    cls._warn_if_symbol_shadows_mnemonic(line_id, line_obj, model)
                    line_obj_list.append(line_obj)
                    label_seen = True
                    instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                    continue

                # try directives
                line_obj = DirectiveLine.factory(
                    line_id,
                    instruction_str,
                    comment_str,
                    current_memzone,
                    memzone_manager,
                    model,
                )
                if line_obj is not None:
                    line_obj_list.append(line_obj)
                    instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                    continue

                # try embedded string
                if model.allow_embedded_strings:
                    line_obj = EmbeddedString.factory(
                        line_id,
                        instruction_str,
                        comment_str,
                        current_memzone,
                        model.word_size,
                        model.word_segment_size,
                        model.intra_word_endianness,
                        model.multi_word_endianness,
                        model.cstr_terminator,
                    )
                    if line_obj is not None:
                        line_obj_list.append(line_obj)
                        instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                        continue

                # try instruction
                line_obj = InstructionLine.factory(
                    line_id,
                    instruction_str,
                    comment_str,
                    model,
                    current_memzone,
                    memzone_manager,
                    source_ordinal=len(line_obj_list),
                )
                if line_obj is not None:
                    line_obj_list.append(line_obj)
                    instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                    continue

                # if we are here, that means nothing was matched.
                cls._report_unparsable_text(line_id, instruction_str, model)

        if len(line_obj_list) == 0:
            if instruction_str != '':
                cls._report_unparsable_text(line_id, instruction_str, model)
            # if we got here, the line is only a comment
            line_obj = LineObject(line_id, instruction_str, comment_str, current_memzone)
            return [line_obj]
        return line_obj_list
