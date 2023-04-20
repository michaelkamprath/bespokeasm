import re
import sys

from bespokeasm.assembler.preprocessor.symbol import PreprocessorSymbol
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.line_object.preprocessor_line.required_language import RequiredLanguageLine
from bespokeasm.assembler.line_object.preprocessor_line.create_memzone import CreateMemzoneLine


class Preprocessor:
    def __init__(self, predefined_symbols: dict[str, str] = {}) -> None:
        self._symbols: dict[str, PreprocessorSymbol] = {}
        for symbol_def in predefined_symbols:
            if 'name' not in symbol_def:
                sys.exit(
                    'ERROR: Preprocessor symbol definition in instruction set configuration YAML file '
                    'is missing the required "name" field.'
                )
            try:
                self.create_symbol(symbol_def['name'], symbol_def.get('value', ''))
            except ValueError:
                sys.exit(
                    f'ERROR: Preprocessor symbol {symbol_def["name"]} is defined multiple times in '
                    f'instruction set configuration YAML file.'
                )

    def create_symbol(self, name: str, value: str) -> PreprocessorSymbol:
        if name not in self._symbols:
            symbol = PreprocessorSymbol(name, value)
            self._symbols[name] = symbol
            return symbol
        else:
            raise ValueError(f"Symbol {name} already exists")

    def get_symbol(self, name: str) -> PreprocessorSymbol:
        return self._symbols.get(name, None)

    def resolve_symbols(self, line_str: str) -> str:
        # Resursively resolve symbols in the line string, stopping when there are no more symbols to resolve.
        # Errors if there are recursion loops caused byt symbols that indirectly refer to themselves.

        # to make this fast, all symbol candidates should be identified first, then the symbols should be resolved
        found_symbols: list[str] = re.findall(r"\b([\w\d_]+)\b", line_str)
        symbol_replaced: bool = False
        for s in found_symbols:
            symbol = self.get_symbol(s)
            if symbol is not None:
                line_str = line_str.replace(s, symbol.value)
                symbol_replaced = True

        if symbol_replaced:
            return self.resolve_symbols(line_str)
        else:
            return line_str

    def parse_line(
                self,
                line_id: LineIdentifier,
                instruction: str,
                comment: str,
                isa_model: AssemblerModel,
                label_scope: LabelScope,
                current_memzone: MemoryZone,
                memzone_manager: MemoryZoneManager,
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
        return []
