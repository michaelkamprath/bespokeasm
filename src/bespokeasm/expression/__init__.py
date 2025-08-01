#
# This expression parser was heavily inspired by:
#       https://github.com/gnebehay/parser
#
# To use this class, import the following:
#
#    from bespokeasm.expression import parse_expression, ExpressionNode
#
import enum
import operator
import re
import sys

from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.utilities import is_string_numeric
from bespokeasm.utilities import is_valid_label
from bespokeasm.utilities import parse_numeric_string
from bespokeasm.utilities import PATTERN_HEX

EXPRESSION_PARTS_PATTERN = \
    r'(?:(?:\%|b)[01]+|{}|\d+|[\+\-\*\/\&\|\^\(\)]|>>|<<|%|LSB\(|BYTE\d\(|(?:\.|_)?\w+|\'.\'|[><])'.format(
        PATTERN_HEX
    )


class TokenType(enum.Enum):
    T_NUM = 0
    T_LABEL = 1
    T_NEGATION = 2
    T_RIGHT_SHIFT = 3
    T_LEFT_SHIFT = 4
    T_PLUS = 5
    T_MINUS = 6
    T_MULT = 7
    T_DIV = 8
    T_MOD = 9
    T_AND = 10
    T_OR = 11
    T_XOR = 12
    T_LSB = 13
    T_BYTE = 14
    T_LPAR = 15
    T_RPAR = 16
    T_END = 17


class ExpressionNode:
    _operations = {
        TokenType.T_PLUS: operator.add,
        TokenType.T_MINUS: operator.sub,
        TokenType.T_MULT: operator.mul,
        TokenType.T_DIV: operator.truediv,
        TokenType.T_MOD: operator.mod,
        TokenType.T_AND: operator.and_,
        TokenType.T_OR: operator.or_,
        TokenType.T_XOR: operator.xor,
        TokenType.T_RIGHT_SHIFT: operator.rshift,
        TokenType.T_LEFT_SHIFT: operator.lshift,
        TokenType.T_NEGATION: operator.neg,
    }

    def __init__(self, token_type: TokenType, value=None):
        self.token_type = token_type
        self.value = value
        self.left_child: ExpressionNode = None
        self.right_child: ExpressionNode = None
        self._is_unary = token_type in [TokenType.T_BYTE, TokenType.T_LSB]

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'<ExpressionNode: type={self.token_type}, value="{self.value}">'

    @property
    def is_unary(self) -> bool:
        return self.token_type in [
            TokenType.T_BYTE,
            TokenType.T_LSB,
            TokenType.T_NEGATION,
        ]

    def _numeric_value(self, label_scope: LabelScope, line_id: LineIdentifier) -> int:
        if self.token_type == TokenType.T_NUM:
            return self.value
        elif self.token_type == TokenType.T_LABEL:
            if label_scope is None:
                sys.exit(f'ERROR - INTERNAL: {line_id} - Label {self.value} has no label scope = {self}')
            # in ths case value is a label
            val = label_scope.get_label_value(self.value, line_id)
            if val is None:
                sys.exit(f'ERROR: {line_id} - Label {self.value} resolves to NONE = {self}')
            return val
        else:
            # this wasn't a numeric value
            sys.exit(f'ERROR: {line_id} - Label {self.value} is not numeric = {self}')

    def _compute(self, label_scope: LabelScope, line_id: LineIdentifier) -> int:
        if self.token_type in [TokenType.T_NUM, TokenType.T_LABEL]:
            return self._numeric_value(label_scope, line_id)
        if self.token_type in [TokenType.T_LSB, TokenType.T_BYTE]:
            byte_idx = 0
            if self.token_type == TokenType.T_BYTE:
                byte_idx = int(self.value[4])
            arg_value = int(self.left_child._compute(label_scope, line_id))
            byte_count = max(((abs(arg_value).bit_length() + 7) // 8), byte_idx+1)
            masked_arg = arg_value & (2**(8 * byte_count) - 1)
            try:
                arg_value_bytes = masked_arg.to_bytes(byte_count, byteorder='little', signed=False)
            except OverflowError as oe:
                sys.exit(
                    f'ERROR - {line_id}: Cound not conver value "{arg_value}" to bytes. masked value = {masked_arg}, {oe}'
                )
            return arg_value_bytes[byte_idx]
        elif self.token_type == TokenType.T_NEGATION:
            arg_value = self.left_child._compute(label_scope, line_id)
            operation = ExpressionNode._operations[self.token_type]
            return operation(arg_value)
        else:
            left_result = self.left_child._compute(label_scope, line_id)
            right_result = self.right_child._compute(label_scope, line_id)
            operation = ExpressionNode._operations[self.token_type]
            if self.token_type in [
                        TokenType.T_AND,
                        TokenType.T_OR,
                        TokenType.T_XOR,
                        TokenType.T_LEFT_SHIFT,
                        TokenType.T_RIGHT_SHIFT
                    ]:
                left_result = int(left_result)
                right_result = int(right_result)
            elif self.token_type in [TokenType.T_DIV, TokenType.T_MOD]:
                left_result = float(left_result)
                right_result = float(right_result)
            return operation(left_result, right_result)

    def get_value(self, label_scope: LabelScope, line_id: LineIdentifier) -> int:
        calculated_value = self._compute(label_scope, line_id)
        return int(calculated_value)

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        contained_registers = self.contained_labels().intersection(register_labels)
        return len(contained_registers) > 0

    def contained_labels(self) -> set[str]:
        if self.token_type == TokenType.T_LABEL:
            return {self.value}
        elif self.token_type in [TokenType.T_NUM]:
            return set()
        left_result: set[str] = self.left_child.contained_labels()
        right_result: set[str] = set()
        if not self.is_unary:
            right_result = self.right_child.contained_labels()
        return left_result.union(right_result)


def parse_expression(line_id: LineIdentifier, expression: str) -> ExpressionNode:
    tokens = _lexical_analysis(line_id, expression)
    ast = _parse_e(line_id, tokens)
    _match(line_id, tokens, TokenType.T_END)
    return ast


TOKEN_MAPPINGS = {
    '<<': TokenType.T_LEFT_SHIFT,
    '>>': TokenType.T_RIGHT_SHIFT,
    '+': TokenType.T_PLUS,
    '-': TokenType.T_MINUS,
    '*': TokenType.T_MULT,
    '/': TokenType.T_DIV,
    '%': TokenType.T_MOD,
    '&': TokenType.T_AND,
    '|': TokenType.T_OR,
    '^': TokenType.T_XOR,
    '(': TokenType.T_LPAR,
    ')': TokenType.T_RPAR,
    'LSB(': TokenType.T_LSB,
}


def _lexical_analysis(line_id: LineIdentifier, s: str) -> list[ExpressionNode]:
    tokens = []
    expression_parts = re.findall(EXPRESSION_PARTS_PATTERN, s)
    for part in expression_parts:
        if part in TOKEN_MAPPINGS:
            token_type = TOKEN_MAPPINGS[part]
            token = ExpressionNode(token_type, value=part)
        elif re.match(r'^BYTE\d\(', part):
            token = ExpressionNode(TokenType.T_BYTE, value=part)
        elif is_string_numeric(part):
            token = ExpressionNode(TokenType.T_NUM, value=parse_numeric_string(part))
        elif is_valid_label(part):
            token = ExpressionNode(TokenType.T_LABEL, value=part)
        else:
            sys.exit(f'ERROR: {line_id} - invalid token: {part}')
        tokens.append(token)
    tokens.append(ExpressionNode(TokenType.T_END))
    return tokens


def _parse_e(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e1(line_id, tokens)
    while tokens[0].token_type in [TokenType.T_AND, TokenType.T_OR, TokenType.T_XOR]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e1(line_id, tokens)
        left_node = node
    return left_node


def _parse_e1(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e2(line_id, tokens)
    while tokens[0].token_type in [TokenType.T_LEFT_SHIFT, TokenType.T_RIGHT_SHIFT]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e2(line_id, tokens)
        left_node = node
    return left_node


def _parse_e2(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e3(line_id, tokens)
    while tokens[0].token_type in [TokenType.T_PLUS, TokenType.T_MINUS]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e3(line_id, tokens)
        left_node = node
    return left_node


def _parse_e3(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e4(line_id, tokens)
    while tokens[0].token_type in [TokenType.T_MULT, TokenType.T_DIV, TokenType.T_MOD]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e4(line_id, tokens)
        left_node = node
    return left_node


def _parse_e4(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    if tokens[0].token_type in [TokenType.T_NUM, TokenType.T_LABEL]:
        return tokens.pop(0)

    if tokens[0].token_type in [TokenType.T_LSB, TokenType.T_BYTE]:
        node = tokens.pop(0)
        node.left_child = _parse_e(line_id, tokens)
        _match(line_id, tokens, TokenType.T_RPAR)
        return node
    elif tokens[0].token_type == TokenType.T_MINUS:
        # if we are here, this should be a negation
        node = ExpressionNode(TokenType.T_NEGATION, value=tokens[0].value)
        tokens.pop(0)
        node.left_child = _parse_e(line_id, tokens)
        return node
    else:
        _match(line_id, tokens, TokenType.T_LPAR)
        expression = _parse_e(line_id, tokens)
        _match(line_id, tokens, TokenType.T_RPAR)
        return expression


def _match(line_id: LineIdentifier, tokens: list[ExpressionNode], token: TokenType) -> ExpressionNode:
    if tokens[0].token_type == token:
        return tokens.pop(0)
    else:
        raise SyntaxError(f'ERROR: {line_id} - Invalid syntax on token: {tokens}. Expected {token}')
