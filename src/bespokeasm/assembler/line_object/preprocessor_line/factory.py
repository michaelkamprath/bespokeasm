from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.preprocessor_line.assert_line import AssertLine
from bespokeasm.assembler.line_object.preprocessor_line.condition_line import ConditionLine
from bespokeasm.assembler.line_object.preprocessor_line.create_memzone import CreateMemzoneLine
from bespokeasm.assembler.line_object.preprocessor_line.create_scope import CreateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.deactivate_scope import DeactivateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.define_symbol import DefineSymbolLine
from bespokeasm.assembler.line_object.preprocessor_line.error_line import ErrorLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowEndTrackLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowEntryLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowResumeLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowSetLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowSuspendLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowTrackLine
from bespokeasm.assembler.line_object.preprocessor_line.print_line import PrintLine
from bespokeasm.assembler.line_object.preprocessor_line.required_language import RequiredLanguageLine
from bespokeasm.assembler.line_object.preprocessor_line.use_scope import UseScopeLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope.named_scope_manager import ActiveNamedScopeList


class PreprocessorLineFactory:
    @classmethod
    def parse_line(
        cls,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        isa_model: AssemblerModel,
        symbol_scope: SymbolScope,
        active_named_scopes: ActiveNamedScopeList,
        current_memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        preprocessor: Preprocessor,
        condition_stack: ConditionStack,
        log_verbosity: int,
        filename: str,
    ) -> list[LineObject]:
        '''Parse a preprocessor line.'''
        directive, separator, _ = instruction.partition(' ')
        has_arguments = bool(separator)

        match directive, has_arguments:
            case ('#track', _):
                line_object = FlowTrackLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#endtrack', _):
                line_object = FlowEndTrackLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#entry', _):
                line_object = FlowEntryLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#assert', _):
                line_object = AssertLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#set', _):
                line_object = FlowSetLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#suspend', _):
                line_object = FlowSuspendLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#resume', _):
                line_object = FlowResumeLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#create-scope', True):
                line_object = CreateScopeLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    active_named_scopes.named_scope_manager,
                )
            case ('#use-scope', True):
                line_object = UseScopeLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    active_named_scopes.named_scope_manager,
                    filename,
                )
            case ('#deactivate-scope', True):
                line_object = DeactivateScopeLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    active_named_scopes.named_scope_manager,
                    filename,
                )
            case ('#require', True):
                line_object = RequiredLanguageLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    isa_model,
                    preprocessor,
                )
            case ('#error', _):
                line_object = ErrorLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    preprocessor,
                    condition_stack,
                )
            case ('#create_memzone', True):
                line_object = CreateMemzoneLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    memzone_manager,
                    isa_model,
                )
            case ('#define', True):
                line_object = DefineSymbolLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    memzone_manager,
                    isa_model,
                    preprocessor,
                )
            case ('#print', True):
                line_object = PrintLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    preprocessor,
                    condition_stack,
                    log_verbosity,
                )
            case (
                '#if' | '#ifdef' | '#ifndef' | '#elif',
                True,
            ) | (
                '#else' | '#endif' | '#mute' | '#emit' | '#unmute',
                _,
            ):
                line_object = ConditionLine(
                    line_id,
                    instruction,
                    comment,
                    current_memzone,
                    preprocessor,
                    condition_stack,
                )
            case _:
                return []

        return [line_object]
