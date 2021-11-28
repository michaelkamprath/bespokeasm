import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.expression import parse_expression, ExpresionType

class ByteCodePart:
    def __init__(self, value_size: int, byte_align: bool, endian: str, line_id: LineIdentifier):
        self._value_size = value_size
        self._byte_align = byte_align
        self._endian = endian
        self._line_id = line_id

    @property
    def value_size(self) -> int:
        return self._value_size
    @property
    def byte_align(self) -> bool:
        return self._byte_align
    @property
    def endian(self) -> str:
        return self._endian
    @property
    def line_id(self) -> LineIdentifier:
        return self._line_id

    def __repr__(self):
        return str(self)
    def __str__(self):
        return 'You really should override ByteCodePart.__str__'
    def __eq__(self, other):
        return \
            self._value_size == other._value_size \
            and self._byte_align == other._byte_align \
            and self._endian == other._endian
    def get_value(self, label_scope: LabelScope) -> int:
        # this should be overridden
        return None

class NumericByteCodePart(ByteCodePart):
    def __init__(self, value: int, value_size: int, byte_align: bool, endian: str, line_id: LineIdentifier):
        super().__init__(value_size, byte_align, endian, line_id)
        self._value = value
    def __str__(self):
        return f'NumericByteCodePart<value={self._value},size={self.value_size}>'

    def get_value(self, label_scope: LabelScope) -> int:
        return self._value

class ExpressionByteCodePart(ByteCodePart):
    def __init__(self, value_expression: str, value_size: int, byte_align: bool, endian: str, line_id: LineIdentifier):
        super().__init__(value_size, byte_align, endian, line_id)
        self._expression = value_expression
        self._parsed_expression = parse_expression(self.line_id, self._expression)

    def __str__(self):
        return f'ExpressionByteCodePart<expression="{self._expression}",size={self.value_size}>'

    def get_value(self, label_scope: LabelScope) -> int:
        value = self._parsed_expression.get_value(label_scope, self.line_id)
        if  isinstance( value, str):
            print(f'ERROR: {self.line_id} - expression "{self._expression}" did not resolve to an int, got: {value}')
            return 0
        return value

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        return self._parsed_expression.contains_register_labels(register_labels)
