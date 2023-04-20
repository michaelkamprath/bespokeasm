from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.line_object.preprocessor_line.required_language import RequiredLanguageLine
from bespokeasm.assembler.line_object.preprocessor_line.create_memzone import CreateMemzoneLine
from bespokeasm.assembler.line_object.preprocessor_line.define_symbol import DefineSymbolLine


class PreprocessorLineFactory:
    @classmethod
    def parse_line(
        cls,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        isa_model: AssemblerModel,
        label_scope: LabelScope,
        current_memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        preprocessor: Preprocessor,
        log_verbosity: int,
    ) -> list[LineObject]:
        '''Parse a preprocessor line.'''
        if instruction.startswith('#require '):
            return [RequiredLanguageLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        isa_model,
                        log_verbosity
                    )]

        if instruction.startswith('#create_memzone '):
            return [CreateMemzoneLine(
                        line_id,
                        instruction,
                        comment,
                        current_memzone,
                        memzone_manager,
                        isa_model,
                        log_verbosity,
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
                        log_verbosity,
                    )]
        return []
