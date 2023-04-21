import re
import sys

from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.symbol import PreprocessorSymbol, SYMBOL_PATTERN


class DefineSymbolLine(PreprocessorLine):
    PATTERN_DEFINE_SYMBOL = re.compile(
            r'^#define\s+({0})(?:\s+((?:[a-zA-Z0-9_]*|\".*\"|\'.*\'|\(.*\)))|\b)$'.format(SYMBOL_PATTERN),
        )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        isa_model: AssemblerModel,
        preprocessor: Preprocessor,
        log_verbosity: int
    ) -> None:
        '''Defines a new preprocessor symbol.'''
        super().__init__(line_id, instruction, comment, memzone)
        define_match = re.search(DefineSymbolLine.PATTERN_DEFINE_SYMBOL, instruction.strip())
        if define_match is not None:
            try:
                if len(define_match.groups()) == 1:
                    self._symbol = preprocessor.create_symbol(define_match.group(1), None, line_id)
                elif len(define_match.groups()) == 2:
                    self._symbol = preprocessor.create_symbol(define_match.group(1), define_match.group(2), line_id)
                else:
                    sys.exit(f'ERROR - {line_id}: Invalid preprocessor symbol definition.')
            except ValueError:
                sys.exit(f'ERROR - {line_id}: Preprocessor symbol {define_match.group(1)} is defined multiple times.')
            if log_verbosity >= 2:
                print(f'INFO - {line_id}: Defined preprocessor symbol {self._symbol.name} = {self._symbol.value}')
        else:
            sys.exit(f'ERROR - {line_id}: Invalid preprocessor symbol definition: {instruction}')

    def __repr__(self) -> str:
        return f"DefineSymbolLine<{self._symbol}>"

    @property
    def symbol(self) -> PreprocessorSymbol:
        return self._symbol
