import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.counter_coordinate_line import CounterCoordinateLine
from bespokeasm.assembler.line_object.directive_line.factory import DirectiveLine
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
        r'\b(?:COORDINATE|COUNTER|OFFSET)\s*\(',
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
                        sys.exit(
                            f'ERROR: {line_id} - only one label or coordinate declaration '
                            'is allowed per line'
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
                    default_numeric_base=model.default_numeric_base,
                )
                if line_obj is not None:
                    if label_seen:
                        sys.exit(f'ERROR: {line_id} - only one label or constant assignment is allowed per line')
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

                # if we are here, that means nothing was matched. Shouldn't happen, so let's error out
                sys.exit(f'ERROR: {line_id} - unknown instruction "{instruction_str.strip()}"')

        if len(line_obj_list) == 0:
            if instruction_str != '':
                sys.exit(f'ERROR: {line_id} - unknown instruction "{instruction_str.strip()}"')
            # if we got here, the line is only a comment
            line_obj = LineObject(line_id, instruction_str, comment_str, current_memzone)
            return [line_obj]
        return line_obj_list
