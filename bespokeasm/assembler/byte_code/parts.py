import sys

from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.expression import parse_expression

class ByteCodePart:
    def __init__(self, value_size: int, byte_align: bool, endian: str):
        self._value_size = value_size
        self._byte_align = byte_align
        self._endian = endian

    @property
    def value_size(self):
        return self._value_size
    @property
    def byte_align(self):
        return self._byte_align
    @property
    def endian(self):
        return self._endian
    def __repr__(self):
        return str(self)
    def __str__(self):
        return 'You really should override ByteCodePart.__str__'
    def __eq__(self, other):
        return \
            self._value_size == other._value_size \
            and self._byte_align == other._byte_align \
            and self._endian == other._endian
    def get_value(self, line_num: int, label_dict: dict[str, int]) -> int:
        # this should be overridden
        return None

class NumericByteCodePart(ByteCodePart):
    def __init__(self, value: int, value_size: int, byte_align: bool, endian: str):
        super().__init__(value_size, byte_align, endian)
        self._value = value
    def __str__(self):
        return f'NumericByteCodePart<value={self._value},size={self.value_size}>'

    def get_value(self, line_num: int, label_dict: dict[str, int]) -> int:
        return self._value

class ExpressionByteCodePart(ByteCodePart):
    def __init__(self, value_expression: str, value_size: int, byte_align: bool, endian: str):
        super().__init__(value_size, byte_align, endian)
        self._expression = value_expression
    def __str__(self):
        return f'ExpressionByteCodePart<expression="{self._expression}",size={self.value_size}>'

    def get_value(self, line_num: int, label_scope: LabelScope) -> int:
        e = parse_expression(line_num, self._expression)
        value = e.get_value(label_scope, line_num)
        if  isinstance( value, str):
            print(f'ERROR - expression "{self._expression}" did not resolve to an int, got: {value}')
            return 0
        return value