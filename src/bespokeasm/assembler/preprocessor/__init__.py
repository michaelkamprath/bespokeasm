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
