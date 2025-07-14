from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.expression import parse_expression, ExpressionNode
from bespokeasm.assembler.memory_zone import MemoryZone


class FillDataLine(LineWithWords):
    _count_expr: ExpressionNode
    _value_expr: ExpressionNode

    def __init__(
            self,
            line_id: LineIdentifier,
            instruction: str,
            comment: str,
            fill_count_expression: str,
            fill_value_expression: str,
            current_memzone: MemoryZone,
    ) -> None:
        super().__init__(line_id, instruction, comment, current_memzone)
        self._count_expr = parse_expression(line_id, fill_count_expression)
        self._value_expr = parse_expression(line_id, fill_value_expression)
        self._count = None
        self._value = None

    @property
    def byte_size(self) -> int:
        if self._count is None:
            self._count = self._count_expr.get_value(self.label_scope, self.line_id)
        return self._count

    def generate_words(self):
        if self._count is None:
            self._count = self._count_expr.get_value(self.label_scope, self.line_id)
        if self._value is None:
            self._value = self._value_expr.get_value(self.label_scope, self.line_id)
        self._bytes.extend([(self._value) & 0xFF]*self._count)


class FillUntilDataLine(LineWithWords):
    _fill_until_addr_expr: ExpressionNode
    _fill_value_expr: ExpressionNode
    _fill_until_addr: int
    _fill_value: int

    def __init__(
            self,
            line_id: LineIdentifier,
            instruction: str,
            comment: str,
            fill_until_address_expresion: str,
            fill_value_expression: str,
            current_memzone: MemoryZone,
    ) -> None:
        super().__init__(line_id, instruction, comment, current_memzone)
        self._fill_until_addr_expr = parse_expression(line_id, fill_until_address_expresion)
        self._fill_value_expr = parse_expression(line_id, fill_value_expression)
        self._fill_until_addr = None
        self._fill_value = None

    @property
    def byte_size(self) -> int:
        if self._fill_until_addr is None:
            self._fill_until_addr = self._fill_until_addr_expr.get_value(self.label_scope, self.line_id)
        if self._fill_until_addr >= self.address:
            return self._fill_until_addr - self.address + 1
        else:
            return 0

    def generate_words(self):
        """Finalize the bytes for this fill until line.
        """
        if self._fill_until_addr is None:
            self._fill_until_addr = self._fill_until_addr_expr.get_value(self.label_scope, self.line_id)
        if self._fill_value is None:
            self._fill_value = self._fill_value_expr.get_value(self.label_scope, self.line_id)
        if self.byte_size > 0 and len(self._bytes) == 0:
            self._bytes.extend([self._fill_value & 0xFF]*self.byte_size)
