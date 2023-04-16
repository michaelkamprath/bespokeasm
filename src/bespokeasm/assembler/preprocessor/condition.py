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

PREPROCESSOR_CONDITION_IMPLIED_IF_PATTERN = re.compile(
    r"^(?:#if)\s+([\w\d_]+)\b"
)

PREPROCESSOR_CONDITION_IFDEF_PATTERN = re.compile(
    r"^(#ifdef|#ifndef)\s+([\w\d_]+)\b"
)


class PreprocessorCondition:
    def __repr__(self) -> str:
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.__repr__()

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        raise NotImplementedError()


class IfPreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        self._line_str = line_str
        self._line = line

        match = PREPROCESSOR_CONDITION_IF_PATTERN.match(line_str.strip())
        if match is None:
            match2 = PREPROCESSOR_CONDITION_IMPLIED_IF_PATTERN.match(line_str.strip())
            if match2 is None:
                raise ValueError(f"Invalid preprocessor condition at line: {line_str}")
            self._lhs_expression = match2.group(1)
            self._operator = "!="
            self._rhs_expression = "0"
        else:
            self._lhs_expression = match.group(1)
            self._operator = match.group(2)
            self._rhs_expression = match.group(3) or match.group(4) or match.group(5)

    def __repr__(self) -> str:
        return f"PreprocessorCondition<#if {self._lhs_symbol} {self._operator} {self._rhs_expression}>"

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        lhs_resolved = preprocessor.resolve_symbols(self._lhs_expression)
        rhs_resolved = preprocessor.resolve_symbols(self._rhs_expression)

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


class IfdefPreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        self._line_str = line_str
        self._line = line

        match = PREPROCESSOR_CONDITION_IFDEF_PATTERN.match(line_str.strip())
        if match is None:
            raise ValueError(f"Invalid preprocessor condition at line: {line_str}")
        self._is_ifndef = match.group(1) == "#ifndef"
        self._symbol = match.group(2)

    def __repr__(self) -> str:
        return f'IfdefPreprocessorCondition<{"#ifndef" if self._is_ifndef else "#ifdef"} {self._symbol}>'

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        symbol = preprocessor.get_symbol(self._symbol)
        if symbol is None:
            return self._is_ifndef
        else:
            return not self._is_ifndef
