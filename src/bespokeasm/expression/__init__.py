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

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope.flow_symbols import FlowSymbolError
from bespokeasm.assembler.symbol_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.utilities import is_explicit_numeric_string
from bespokeasm.utilities import is_unprefixed_numeric_string
from bespokeasm.utilities import is_valid_label
from bespokeasm.utilities import normalize_default_numeric_base
from bespokeasm.utilities import parse_numeric_string
from bespokeasm.utilities import PATTERN_CHARACTER_ORDINAL
from bespokeasm.utilities import PATTERN_HEX

EXPRESSION_PARTS_PATTERN = \
    r'(?:(?:\%|b)[01]+|{}|[\+\-\*\/\&\|\^\(\)]|>>|<<|%|COUNTER\(|OFFSET\(|LSB\(|BYTE\d\(|(?:\.|_)?\w+|{}|[><])'.format(
        PATTERN_HEX,
        PATTERN_CHARACTER_ORDINAL,
    )


class ExpressionUseContext(enum.Enum):
    """The assembly context in which an expression is consumed."""

    OPERAND_VALUE = 'operand_value'
    DATA_VALUE = 'data_value'
    FLOW_DIRECTIVE = 'flow_directive'
    LAYOUT = 'layout'
    PREPROCESSOR_CONDITION = 'preprocessor_condition'
    INSTRUCTION_SELECTION = 'instruction_selection'


class TokenType(enum.Enum):
    T_NUM = 0
    T_LABEL = 1
    T_LABEL_OR_NUM = 2
    T_NEGATION = 3
    T_RIGHT_SHIFT = 4
    T_LEFT_SHIFT = 5
    T_PLUS = 6
    T_MINUS = 7
    T_MULT = 8
    T_DIV = 9
    T_MOD = 10
    T_AND = 11
    T_OR = 12
    T_XOR = 13
    T_LSB = 14
    T_BYTE = 15
    T_LPAR = 16
    T_RPAR = 17
    T_END = 18
    T_COUNTER = 19
    T_OFFSET = 20


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

    def __init__(self, token_type: TokenType, value=None, default_numeric_base: str = 'decimal'):
        self.token_type = token_type
        self.value = value
        self.default_numeric_base = normalize_default_numeric_base(default_numeric_base)
        self.left_child: ExpressionNode = None
        self.right_child: ExpressionNode = None
        self._is_unary = token_type in [
            TokenType.T_BYTE,
            TokenType.T_LSB,
            TokenType.T_COUNTER,
            TokenType.T_OFFSET,
        ]

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'<ExpressionNode: type={self.token_type}, value="{self.value}">'

    @property
    def is_unary(self) -> bool:
        return self.token_type in [
            TokenType.T_BYTE,
            TokenType.T_LSB,
            TokenType.T_COUNTER,
            TokenType.T_OFFSET,
            TokenType.T_NEGATION,
        ]

    @property
    def expression_context(self) -> ExpressionUseContext | None:
        """Return the use context attached by deferred analysis parsing."""
        return getattr(self, '_expression_context', None)

    def deferred_flow_nodes(self) -> tuple:
        """Return deferred flow-expression nodes in source-tree order."""
        nodes = []
        if self.token_type in [TokenType.T_COUNTER, TokenType.T_OFFSET]:
            nodes.append(self)
        if self.left_child is not None:
            nodes.extend(self.left_child.deferred_flow_nodes())
        if not self.is_unary and self.right_child is not None:
            nodes.extend(self.right_child.deferred_flow_nodes())
        return tuple(nodes)

    def resolve_flow_value(self, value: int) -> None:
        """Attach the value computed by the static-analysis pass."""
        if self.token_type not in [TokenType.T_COUNTER, TokenType.T_OFFSET]:
            raise TypeError('only flow-expression nodes can receive a flow value')
        self._resolved_flow_value = value

    def _numeric_value(
        self,
        symbol_scope: SymbolScope | None,
        active_named_scopes: ActiveNamedScopeList,
        line_id: LineIdentifier,
    ) -> int:
        if self.token_type == TokenType.T_NUM:
            return self.value
        elif self.token_type in [TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM]:
            if symbol_scope is None:
                if self.token_type == TokenType.T_LABEL_OR_NUM:
                    return parse_numeric_string(self.value, self.default_numeric_base)
                sys.exit(f'ERROR - INTERNAL: {line_id} - Label {self.value} has no symbol scope = {self}')
            # in ths case value is a label
            if active_named_scopes is not None:
                val = active_named_scopes.named_scope_manager.get_label_value(
                    self.value, symbol_scope, active_named_scopes, line_id
                )
            else:
                val = symbol_scope.get_label_value(self.value, line_id)
            if val is None:
                # The numeric fallback must win before any coordinate lookup:
                # a token that is a valid numeral in the default base resolved
                # numerically before flow counters existed, and strip
                # equivalence requires it to keep doing so. Coordinate
                # diagnostics apply only to otherwise-unresolvable references.
                if self.token_type == TokenType.T_LABEL_OR_NUM:
                    return parse_numeric_string(self.value, self.default_numeric_base)
                coordinate = (
                    active_named_scopes.named_scope_manager.get_counter_coordinate(
                        self.value,
                        symbol_scope,
                        active_named_scopes,
                    )
                    if active_named_scopes is not None
                    else symbol_scope.get_counter_coordinate(self.value)
                )
                if coordinate is not None:
                    raise FlowSymbolError(
                        f'counter coordinate "{self.value}" may only be used through OFFSET()'
                    )
                if symbol_scope.ignored_counter_coordinate_site(self.value) is not None:
                    raise FlowSymbolError(
                        f'static analysis is disabled; cannot resolve {self.value}'
                    )
                sys.exit(f'ERROR: {line_id} - Label {self.value} resolves to NONE = {self}')
            return val
        else:
            # this wasn't a numeric value
            sys.exit(f'ERROR: {line_id} - Label {self.value} is not numeric = {self}')

    def _compute(
        self,
        symbol_scope: SymbolScope,
        active_named_scopes: ActiveNamedScopeList,
        line_id: LineIdentifier
    ) -> int:
        if self.token_type in [TokenType.T_NUM, TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM]:
            return self._numeric_value(symbol_scope, active_named_scopes, line_id)
        if self.token_type in [TokenType.T_COUNTER, TokenType.T_OFFSET]:
            if hasattr(self, '_resolved_flow_value'):
                return self._resolved_flow_value
            raise RuntimeError(
                'deferred flow expression reached numeric evaluation before '
                'the static-analysis pass resolved it'
            )
        if self.token_type in [TokenType.T_LSB, TokenType.T_BYTE]:
            byte_idx = 0
            if self.token_type == TokenType.T_BYTE:
                byte_idx = int(self.value[4])
            arg_value = int(self.left_child._compute(symbol_scope, active_named_scopes, line_id))
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
            arg_value = self.left_child._compute(symbol_scope, active_named_scopes, line_id)
            operation = ExpressionNode._operations[self.token_type]
            return operation(arg_value)
        else:
            left_result = self.left_child._compute(symbol_scope, active_named_scopes, line_id)
            right_result = self.right_child._compute(symbol_scope, active_named_scopes, line_id)
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

    def get_value(
        self,
        symbol_scope: SymbolScope,
        active_named_scopes: ActiveNamedScopeList,
        line_id: LineIdentifier
    ) -> int:
        calculated_value = self._compute(symbol_scope, active_named_scopes, line_id)
        return int(calculated_value)

    def contains_register_labels(self, register_labels: set[str]) -> bool:
        if self.token_type in [TokenType.T_COUNTER, TokenType.T_OFFSET]:
            return False
        if self.token_type in [TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM]:
            return self.value in register_labels
        if self.token_type == TokenType.T_NUM:
            return False
        if self.left_child is not None and self.left_child.contains_register_labels(register_labels):
            return True
        if not self.is_unary and self.right_child is not None:
            return self.right_child.contains_register_labels(register_labels)
        return False

    def contained_labels(self) -> set[str]:
        if self.token_type in [TokenType.T_COUNTER, TokenType.T_OFFSET]:
            return set()
        if self.token_type == TokenType.T_LABEL:
            return {self.value}
        elif self.token_type in [TokenType.T_NUM, TokenType.T_LABEL_OR_NUM]:
            return set()
        left_result: set[str] = self.left_child.contained_labels()
        right_result: set[str] = set()
        if not self.is_unary:
            right_result = self.right_child.contained_labels()
        return left_result.union(right_result)


def parse_expression(
    line_id: LineIdentifier,
    expression: str,
    default_numeric_base: str = 'decimal',
    *,
    context: ExpressionUseContext | None = None,
) -> ExpressionNode:
    """Parse a source numeric expression with deferred flow-value support."""
    ast = _parse_expression_ast(line_id, expression, default_numeric_base)
    flow_nodes = ast.deferred_flow_nodes()
    if flow_nodes and context is None:
        raise SyntaxError(
            f'ERROR: {line_id} - flow expression has no tagged use context'
        )
    if flow_nodes and context not in {
        ExpressionUseContext.OPERAND_VALUE,
        ExpressionUseContext.DATA_VALUE,
        ExpressionUseContext.FLOW_DIRECTIVE,
    }:
        raise SyntaxError(
            f'ERROR: {line_id} - flow expressions are not allowed in '
            f'{context.value.replace("_", " ")} expressions'
        )
    for node in flow_nodes:
        node._expression_context = context
    return ast


def parse_deferred_flow_expression(
    line_id: LineIdentifier,
    expression: str,
    context: ExpressionUseContext,
    default_numeric_base: str = 'decimal',
) -> ExpressionNode:
    """Parse and context-tag flow operators without evaluating or exposing them.

    This analysis-only M0 entry point gives later milestones a stable parsed
    representation. Normal source parsing continues through ``parse_expression``
    and rejects these operators until their semantics ship.
    """
    if not isinstance(context, ExpressionUseContext):
        raise TypeError('context must be an ExpressionUseContext')
    ast = _parse_expression_ast(line_id, expression, default_numeric_base)
    for node in ast.deferred_flow_nodes():
        node._expression_context = context
    return ast


def _parse_expression_ast(
    line_id: LineIdentifier,
    expression: str,
    default_numeric_base: str,
) -> ExpressionNode:
    tokens = _lexical_analysis(line_id, expression, default_numeric_base)
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
    'COUNTER(': TokenType.T_COUNTER,
    'OFFSET(': TokenType.T_OFFSET,
}


def _lexical_analysis(
    line_id: LineIdentifier,
    s: str,
    default_numeric_base: str = 'decimal',
) -> list[ExpressionNode]:
    expression_without_char_literals = _strip_character_ordinals_for_validation(line_id, s)
    normalized_base = normalize_default_numeric_base(default_numeric_base)
    tokens = []
    if '&&' in expression_without_char_literals or '||' in expression_without_char_literals:
        raise SyntaxError(
            f"ERROR: {line_id} - boolean operators '&&' and '||' are not supported in expressions"
        )
    if '[' in expression_without_char_literals or ']' in expression_without_char_literals:
        raise SyntaxError(
            f'ERROR: {line_id} - brackets are not supported in numeric expressions'
        )
    if expression_without_char_literals.count('"') % 2 != 0:
        raise SyntaxError(
            f'ERROR: {line_id} - unterminated string literal (double quotes are not valid in expressions)'
        )
    if re.search(r'"[^"]*"', expression_without_char_literals):
        raise SyntaxError(
            f'ERROR: {line_id} - double-quoted strings are not valid in expressions '
            "(use single-character ordinals like 'A')"
        )
    last_end = 0
    for match in re.finditer(EXPRESSION_PARTS_PATTERN, s):
        if match.start() > last_end:
            gap = s[last_end:match.start()]
            if gap.strip():
                gap_str = gap.strip()
                raise SyntaxError(f'ERROR: {line_id} - invalid token: {gap_str}')
        part = match.group(0)
        if part in TOKEN_MAPPINGS:
            token_type = TOKEN_MAPPINGS[part]
            token = ExpressionNode(token_type, value=part)
        elif re.match(r'^BYTE\d\(', part):
            token = ExpressionNode(TokenType.T_BYTE, value=part)
        elif is_explicit_numeric_string(part):
            token = ExpressionNode(TokenType.T_NUM, value=parse_numeric_string(part))
        elif is_unprefixed_numeric_string(part, normalized_base):
            if is_valid_label(part):
                token = ExpressionNode(
                    TokenType.T_LABEL_OR_NUM,
                    value=part,
                    default_numeric_base=normalized_base,
                )
            else:
                token = ExpressionNode(
                    TokenType.T_NUM,
                    value=parse_numeric_string(part, normalized_base),
                    default_numeric_base=normalized_base,
                )
        elif is_valid_label(part):
            token = ExpressionNode(TokenType.T_LABEL, value=part)
        elif re.fullmatch(r'[\da-zA-Z]+', part) is not None:
            raise SyntaxError(
                f'ERROR: {line_id} - invalid {normalized_base} numeric literal: {part}'
            )
        else:
            sys.exit(f'ERROR: {line_id} - invalid token: {part}')
        tokens.append(token)
        last_end = match.end()
    if s[last_end:].strip():
        gap_str = s[last_end:].strip()
        raise SyntaxError(f'ERROR: {line_id} - invalid token: {gap_str}')
    tokens.append(ExpressionNode(TokenType.T_END))
    return tokens


def _strip_character_ordinals_for_validation(line_id: LineIdentifier, expression: str) -> str:
    stripped_expression: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] != "'":
            stripped_expression.append(expression[index])
            index += 1
            continue

        index += 1
        if index >= len(expression):
            raise SyntaxError(
                f"ERROR: {line_id} - unterminated character literal (use single quotes like 'A')"
            )
        if expression[index] == "'":
            raise SyntaxError(
                f"ERROR: {line_id} - empty character literal is not valid (use single-character ordinals like 'A')"
            )

        if expression[index] == '\\':
            index += 1
            if index >= len(expression):
                raise SyntaxError(
                    f"ERROR: {line_id} - unterminated character literal (use single quotes like 'A')"
                )
        index += 1

        if index >= len(expression):
            raise SyntaxError(
                f"ERROR: {line_id} - unterminated character literal (use single quotes like 'A')"
            )
        if expression[index] != "'":
            if "'" in expression[index:]:
                raise SyntaxError(
                    f"ERROR: {line_id} - only single-character ordinals are supported (use 'A')"
                )
            raise SyntaxError(
                f"ERROR: {line_id} - unterminated character literal (use single quotes like 'A')"
            )
        index += 1
        stripped_expression.append('0')

    return ''.join(stripped_expression)


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
    if tokens[0].token_type in [TokenType.T_NUM, TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM]:
        return tokens.pop(0)

    if tokens[0].token_type in [
        TokenType.T_LSB,
        TokenType.T_BYTE,
        TokenType.T_COUNTER,
        TokenType.T_OFFSET,
    ]:
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
