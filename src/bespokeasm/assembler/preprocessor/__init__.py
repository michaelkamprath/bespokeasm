import re

from bespokeasm.assembler.preprocessor.symbol import PreprocessorSymbol


class Preprocessor:
    def __init__(self):
        self._symbols: dict[str, PreprocessorSymbol] = {}

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
        print(
            f"Resolving symbols in line: {line_str} (symbols: {self._symbols.keys()})",
        )
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
