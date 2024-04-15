from functools import cached_property

from bespokeasm.utilities import is_string_numeric, parse_numeric_string
from bespokeasm.assembler.line_identifier import LineIdentifier


SYMBOL_PATTERN = r'[\w_][\w\d_]+'


class PreprocessorSymbol:
    def __init__(self, name: str, value: str, line_id: LineIdentifier = None):
        self._name = name
        self._value = value if value is not None else ''
        self._line_id = line_id

    def __repr__(self) -> str:
        return f'PrerocessorSymbol({self.name} = {self.value})'

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
    def created_line_id(self) -> LineIdentifier:
        return self._line_id

    @cached_property
    def value_numeric(self) -> int:
        '''Returns the numeric value of the symbol, or None if the value is not numeric'''
        if self.value is None or not self.is_value_numeric:
            return None
        return parse_numeric_string(self.value)

    @cached_property
    def is_value_numeric(self) -> bool:
        if self.value is None:
            return False
        return is_string_numeric(self.value)
