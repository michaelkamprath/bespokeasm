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
from bespokeasm.line_object.label_line import is_valid_label

class TokenType(enum.Enum):
    T_NUM = 0
    T_LABEL = 1
    T_PLUS = 2
    T_MINUS = 3
    T_MULT = 4
    T_DIV = 5
    T_LPAR = 6
    T_RPAR = 7
    T_END = 8

class ExpressionNode:
    _operations = {
        TokenType.T_PLUS: operator.add,
        TokenType.T_MINUS: operator.sub,
        TokenType.T_MULT: operator.mul,
        TokenType.T_DIV: operator.truediv
    }

    def __init__(self, token_type: TokenType, value=None):
        self.token_type = token_type
        self.value = value
        self.left_child = None
        self.right_child = None

    def _numeric_value(self, label_map: dict) -> int:
        if self.token_type == TokenType.T_NUM:
            return self.value
        elif self.token_type == TokenType.T_LABEL:
            # in ths case value is a label
            return label_map[self.value]
        else:
            # this wasn't a numeric value
            return None

    def _compute(self, label_map: dict[str,int]) -> float:
        if self.token_type in [TokenType.T_NUM, TokenType.T_LABEL]:
            return float(self._numeric_value(label_map))
        left_result = self.left_child._compute(label_map)
        right_result = self.right_child._compute(label_map)
        operation = ExpressionNode._operations[self.token_type]
        return operation(left_result, right_result)

    def get_value(self, label_map: dict[str,int]) -> int:
        return int(self._compute(label_map))

ExpresionType = ExpressionNode

def parse_expression(line_num: int, expression: str) -> ExpresionType:
    tokens = _lexical_analysis(line_num, expression)
    ast = _parse_e(line_num, tokens)
    _match(line_num, tokens, TokenType.T_END)
    return ast

def _lexical_analysis(line_num: int, s: str) -> list[ExpressionNode]:
    mappings = {
        '+': TokenType.T_PLUS,
        '-': TokenType.T_MINUS,
        '*': TokenType.T_MULT,
        '/': TokenType.T_DIV,
        '(': TokenType.T_LPAR,
        ')': TokenType.T_RPAR,
    }

    tokens = []
    # split the string on white space
    # expression_parts = s.split(None)
    expression_parts = re.findall(r'(?:\%|\$|b|0x)?[\w]+|[\+\-\*\/\(\)]', s)
    for part in expression_parts:
        if len(part) == 1 and part in mappings:
            token_type = mappings[part]
            token = ExpressionNode(token_type, value=part)
        elif is_string_numeric(part):
            token = ExpressionNode(TokenType.T_NUM, value=parse_numeric_string(part))
        elif is_valid_label(part):
            token = ExpressionNode(TokenType.T_LABEL, value=part)
        else:
            sys.exit(f'ERROR: line {line_num} - invalid token: {part}')
        tokens.append(token)
    tokens.append(ExpressionNode(TokenType.T_END))
    return tokens

def _parse_e(line_num: int, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e2(line_num, tokens)
    while tokens[0].token_type in [TokenType.T_PLUS, TokenType.T_MINUS]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e2(line_num, tokens)
        left_node = node
    return left_node

def _parse_e2(line_num: int, tokens: list[ExpressionNode]) -> ExpressionNode:
    left_node = _parse_e3(line_num, tokens)
    while tokens[0].token_type in [TokenType.T_MULT, TokenType.T_DIV]:
        node = tokens.pop(0)
        node.left_child = left_node
        node.right_child = _parse_e3(line_num, tokens)
        left_node = node
    return left_node

def _parse_e3(line_num: int, tokens: list[ExpressionNode]) -> ExpressionNode:
    if tokens[0].token_type in [TokenType.T_NUM, TokenType.T_LABEL]:
        return tokens.pop(0)

    _match(line_num, tokens, TokenType.T_LPAR)
    expression = _parse_e(line_num, tokens)
    _match(line_num, tokens, TokenType.T_RPAR)

    return expression

def _match(line_num: int, tokens: list[ExpressionNode], token: TokenType) -> ExpressionNode:
    if tokens[0].token_type == token:
        return tokens.pop(0)
    else:
        sys.exit(f'ERROR: line {line_num} - Invalid syntax on token: {tokens[0].token_type}')
