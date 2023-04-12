from bespokeasm.utilities import is_string_numeric


class PreprocessorSymbol:
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"PrerocessorSymbol({self.name} = {self.value})"

    def __eq__(self, other) -> bool:
        return self.name == other.name and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.name, self.value))

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> str:
        return self._value

    @property
    def is_value_numeric(self) -> bool:
        if self.value is None:
            return False
        return is_string_numeric(self.value)
