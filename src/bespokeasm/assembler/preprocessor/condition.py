import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.expression import parse_expression, ExpressionNode
from bespokeasm.assembler.line_object import INSTRUCTION_EXPRESSION_PATTERN


# NOTE: the order of the RHS expressions is important, as it determines the order of evaluation. Need to parse the
#       quoted strings first, then the expressions.
PREPROCESSOR_CONDITION_IF_PATTERN = re.compile(
    f"^(?:#if)\\s+([\\w\\d_]+)\\s+(==|!=|>|>=|<|<=)\\s+"
    f"(?:(?:\\\')(.+)(?:\\\')|(?:\\\")(.+)(?:\\\")|({INSTRUCTION_EXPRESSION_PATTERN}))"
)


class PreprocessorCondition:
    def __init__(self, line_str: str, line: LineIdentifier):
        self._line_str = line_str
        self._line = line

        match = PREPROCESSOR_CONDITION_IF_PATTERN.match(line_str.strip())
        if match is None:
            raise ValueError(f"Invalid preprocessor condition at line: {line_str}")

        self._lhs_expression = match.group(1)
        self._operator = match.group(2)
        self._rhs_expression = match.group(3) or match.group(4) or match.group(5)

    def __repr__(self) -> str:
        return f"PreprocessorCondition<#if {self._lhs_symbol} {self._operator} {self._rhs_expression}>"

    def __str__(self) -> str:
        return self.__repr__()

    def evaluate(self, preprocess: Preprocessor) -> bool:
        lhs_resolved = preprocess.resolve_symbols(self._lhs_expression)
        rhs_resolved = preprocess.resolve_symbols(self._rhs_expression)

        lhs_expression: ExpressionNode = parse_expression(self._line, lhs_resolved)
        rhs_expression: ExpressionNode = parse_expression(self._line, rhs_resolved)

        if len(lhs_expression.contained_labels()) > 0 or len(rhs_expression.contained_labels()) > 0:
            # must do a string comparison
            lhs_value = lhs_resolved
            rhs_value = rhs_resolved
        else:
            # can do a numeric comparison
            lhs_value = lhs_expression.get_value(None, self._line)
            rhs_value = rhs_expression.get_value(None, self._line)

        print(f"Comparing {lhs_value} {self._operator} {rhs_value}")

        if self._operator == "==":
            return lhs_value == rhs_value
        elif self._operator == "!=":
            return lhs_value != rhs_value
        elif self._operator == ">":
            return lhs_value > rhs_value
        elif self._operator == ">=":
            return lhs_value >= rhs_value
        elif self._operator == "<":
            return lhs_value < rhs_value
        elif self._operator == "<=":
            return lhs_value <= rhs_value
        else:
            raise ValueError(f"Unknown operator {self._operator}")
