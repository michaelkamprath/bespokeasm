from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.preprocessor_line.condition_line import CONDITIONAL_LINE_PREFIX_LIST
from bespokeasm.assembler.line_object.preprocessor_line.condition_line import ConditionLine
from bespokeasm.assembler.line_object.preprocessor_line.create_memzone import CreateMemzoneLine
from bespokeasm.assembler.line_object.preprocessor_line.create_scope import CreateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.deactivate_scope import DeactivateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.define_symbol import DefineSymbolLine
from bespokeasm.assembler.line_object.preprocessor_line.error_line import ErrorLine
from bespokeasm.assembler.line_object.preprocessor_line.print_line import PrintLine
from bespokeasm.assembler.line_object.preprocessor_line.required_language import RequiredLanguageLine
from bespokeasm.assembler.line_object.preprocessor_line.use_scope import UseScopeLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


class PreprocessorLineFactory:
    @classmethod
    def parse_line(
        cls,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        isa_model: AssemblerModel,
        label_scope: LabelScope,
        active_named_scopes: ActiveNamedScopeList,
        current_memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        preprocessor: Preprocessor,
        condition_stack: ConditionStack,
        log_verbosity: int,
        filename: str,
    ) -> list[LineObject]:
        '''Parse a preprocessor line.'''
        if instruction.startswith('#create-scope '):
            return [CreateScopeLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        isa_model,
                        active_named_scopes.named_scope_manager
                    )]

        if instruction.startswith('#use-scope '):
            return [UseScopeLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        isa_model,
                        active_named_scopes.named_scope_manager,
                        filename
                    )]

        if instruction.startswith('#deactivate-scope '):
            return [DeactivateScopeLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        isa_model,
                        active_named_scopes.named_scope_manager,
                        filename
                    )]

        if instruction.startswith('#require '):
            return [RequiredLanguageLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        isa_model,
                        preprocessor
                    )]

        if instruction == '#error' or instruction.startswith('#error '):
            return [ErrorLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        preprocessor,
                        condition_stack,
                    )]

        if instruction.startswith('#create_memzone '):
            return [CreateMemzoneLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        memzone_manager,
                        isa_model,
                    )]

        if instruction.startswith('#define '):
            return [DefineSymbolLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        memzone_manager,
                        isa_model,
                        preprocessor,
                    )]
        if instruction.startswith('#print '):
            return [PrintLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        preprocessor,
                        condition_stack,
                        log_verbosity,
                    )]
        if instruction.startswith(tuple(CONDITIONAL_LINE_PREFIX_LIST)):
            return [ConditionLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        preprocessor,
                        condition_stack,
                    )]
        return []
