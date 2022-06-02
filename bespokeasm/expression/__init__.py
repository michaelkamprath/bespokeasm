#
# This expression parser was heavily inspired by:
#       https://github.com/gnebehay/parser
#
# To use this class, import the following:
#
#    from bespokeasm.expression import parse_expression, ExpresionType
#

import enum
import operator
import re
import sys

from bespokeasm.utilities import is_string_numeric, parse_numeric_string
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.line_object import is_valid_label


class TokenType(enum.Enum):
    T_NUM = 0
    T_LABEL = 1
    T_PLUS = 2
    T_MINUS = 3
    T_MULT = 4
    T_DIV = 5
    T_AND = 6
    T_OR = 7
    T_XOR = 8
    T_LPAR = 9
    T_RPAR = 10
    T_END = 11


class ExpressionNode:
    _operations = {
        TokenType.T_PLUS: operator.add,
        TokenType.T_MINUS: operator.sub,
        TokenType.T_MULT: operator.mul,
        TokenType.T_DIV: operator.truediv,
        TokenType.T_AND: operator.and_,
        TokenType.T_OR: operator.or_,
        TokenType.T_XOR: operator.xor,
    }

    def __init__(self, token_type: TokenType, value=None):
        self.token_type = token_type
        self.value = value
        self.left_child = None
        self.right_child = None

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'<ExpressionNode: type={self.token_type}, value="{self.value}">'

    def _numeric_value(self, label_scope: LabelScope, line_id: LineIdentifier) -> int:
        if self.token_type == TokenType.T_NUM:
            return self.value
        elif self.token_type == TokenType.T_LABEL:
            # in ths case value is a label
            val = label_scope.get_label_value(self.value, line_id)
            if val is None:
                sys.exit(f'ERROR: {line_id} - Label {self.value} resolves to NONE = {self}')
            return val
        else:
            # this wasn't a numeric value
            sys.exit(f'ERROR: {line_id} - Label {self.value} is not numeric = {self}')

    def _compute(self, label_scope: LabelScope, line_id: LineIdentifier) -> float:
        if self.token_type in [TokenType.T_NUM, TokenType.T_LABEL]:
            return float(self._numeric_value(label_scope, line_id))
        left_result = self.left_child._compute(label_scope, line_id)
        right_result = self.right_child._compute(label_scope, line_id)
        operation = ExpressionNode._operations[self.token_type]
        if self.token_type in [TokenType.T_AND, TokenType.T_OR, TokenType.T_XOR]:
            left_result = int(left_result)
            right_result = int(right_result)
        return operation(left_result, right_result)

    def get_value(self, label_scope: LabelScope, line_id: LineIdentifier) -> int:
        return int(self._compute(label_scope, line_id))

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        if self.token_type == TokenType.T_LABEL:
            return self.value in register_labels
        elif self.token_type in [TokenType.T_NUM]:
            return False
        left_result = self.left_child.contains_register_labels(register_labels)
        right_result = self.right_child.contains_register_labels(register_labels)
        return left_result or right_result


ExpresionType = ExpressionNode


def parse_expression(line_id: LineIdentifier, expression: str) -> ExpresionType:
    tokens = _lexical_analysis(line_id, expression)
    ast = _parse_e(line_id, tokens)
    _match(line_id, tokens, TokenType.T_END)
    return ast


def _lexical_analysis(line_id: LineIdentifier, s: str) -> list[ExpressionNode]:
    mappings = {
        '+': TokenType.T_PLUS,
        '-': TokenType.T_MINUS,
        '*': TokenType.T_MULT,
        '/': TokenType.T_DIV,
        '&': TokenType.T_AND,
        '|': TokenType.T_OR,
        '^': TokenType.T_XOR,
        '(': TokenType.T_LPAR,
        ')': TokenType.T_RPAR,
    }

    tokens = []
    expression_parts = re.findall(r'(?:(?:\%|b)[01]+|(?:\$|0x)[0-9a-fA-F]+|\d+|[\+\-\*\/\&\|\^\(\)]|(?:\.|_)?\w+)', s)
    for part in expression_parts:
        if len(part) == 1 and part in mappings:
            token_type = mappings[part]
            token = ExpressionNode(token_type, value=part)
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
    while tokens[0].token_type in [TokenType.T_PLUS, TokenType.T_MINUS]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e2(line_id, tokens)
        left_node = node
    return left_node


def _parse_e2(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e3(line_id, tokens)
    while tokens[0].token_type in [TokenType.T_MULT, TokenType.T_DIV]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e3(line_id, tokens)
        left_node = node
    return left_node


def _parse_e3(line_id: LineIdentifier, tokens: list[ExpressionNode]) -> ExpressionNode:
    if tokens[0].token_type in [TokenType.T_NUM, TokenType.T_LABEL]:
        return tokens.pop(0)

    _match(line_id, tokens, TokenType.T_LPAR)
    expression = _parse_e(line_id, tokens)
    _match(line_id, tokens, TokenType.T_RPAR)

    return expression


def _match(line_id: LineIdentifier, tokens: list[ExpressionNode], token: TokenType) -> ExpressionNode:
    if tokens[0].token_type == token:
        return tokens.pop(0)
    else:
        sys.exit(f'ERROR: {line_id} - Invalid syntax on token: {tokens[0]}')
