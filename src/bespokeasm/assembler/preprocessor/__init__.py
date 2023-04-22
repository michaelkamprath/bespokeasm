import re
import sys

from bespokeasm.assembler.preprocessor.symbol import PreprocessorSymbol
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.preprocessor.symbol import SYMBOL_PATTERN


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

    def add_cli_symbols(self, cli_symbols: list[str]) -> None:
        for symbol_str in cli_symbols:
            if '=' in symbol_str:
                name, value = symbol_str.split('=')
                self.create_symbol(name.strip(), value.strip())
            else:
                self.create_symbol(symbol_str.strip(), None)

    def create_symbol(self, name: str, value: str, line_id: LineIdentifier = None) -> PreprocessorSymbol:
        if name not in self._symbols:
            symbol = PreprocessorSymbol(name, value, line_id)
            self._symbols[name] = symbol
            return symbol
        else:
            raise ValueError(f"Symbol {name} already exists")

    def get_symbol(self, name: str) -> PreprocessorSymbol:
        return self._symbols.get(name, None)

    def resolve_symbols(
                self,
                line_id: LineIdentifier,
                line_str: str,
                resolved_symbols: set[str] = set()
            ) -> str:
        # Resursively resolve symbols in the line string, stopping when there are no more symbols to resolve.
        # Errors if there are recursion loops caused byt symbols that indirectly refer to themselves.

        # to make this fast, all symbol candidates should be identified first, then the symbols should be resolved
        found_symbols: list[str] = re.findall(f'\\b({SYMBOL_PATTERN})\\b', line_str)
        symbols_replaced: set[str] = set()

        for s in found_symbols:
            symbol = self.get_symbol(s)
            if symbol is not None:
                if s in resolved_symbols:
                    sys.exit(
                        f'ERROR - {line_id}: Preprocessor macro symbol {s} is indirectly referring to itself'
                    )
                # first, recurse through this symbol's replacement string to resolve any symbols it may contain
                local_resolved_symbols = resolved_symbols.copy()
                local_resolved_symbols.update([s])
                replacement_str = self.resolve_symbols(line_id, symbol.value, local_resolved_symbols)
                # now replace the symbol with its replacement string
                line_str = line_str.replace(s, replacement_str)
                symbols_replaced.add(s)

        if len(symbols_replaced) > 0:
            updated_resolved_symbols = resolved_symbols.copy()
            updated_resolved_symbols.update(symbols_replaced)
            return self.resolve_symbols(line_id, line_str, updated_resolved_symbols)
        else:
            return line_str
