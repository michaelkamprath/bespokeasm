from __future__ import annotations

import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import INSTRUCTION_EXPRESSION_PATTERN
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.symbol import SYMBOL_PATTERN
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import parse_expression

# NOTE: the order of the RHS expressions is important, as it determines the order of evaluation. Need to parse the
#       quoted strings first, then the expressions.
PREPROCESSOR_CONDITION_IF_PATTERN = re.compile(
    f'^(?:#if)\\s+({INSTRUCTION_EXPRESSION_PATTERN})\\s+(==|!=|>|>=|<|<=)\\s+'
    f"(?:(?:\\\')(.+)(?:\\\')|(?:\\\")(.+)(?:\\\")|({INSTRUCTION_EXPRESSION_PATTERN}))"
)

PREPROCESSOR_CONDITION_IMPLIED_IF_PATTERN = re.compile(
    fr'^(?:#if)\s+({INSTRUCTION_EXPRESSION_PATTERN})'
)

PREPROCESSOR_CONDITION_ELIF_PATTERN = re.compile(
    f'^(?:#elif)\\s+({INSTRUCTION_EXPRESSION_PATTERN})\\s+(==|!=|>|>=|<|<=)\\s+'
    f"(?:(?:\\\')(.+)(?:\\\')|(?:\\\")(.+)(?:\\\")|({INSTRUCTION_EXPRESSION_PATTERN}))"
)

PREPROCESSOR_CONDITION_IMPLIED_ELIF_PATTERN = re.compile(
    fr'^(?:#elif)\s+({INSTRUCTION_EXPRESSION_PATTERN})'
)

PREPROCESSOR_CONDITION_IFDEF_PATTERN = re.compile(
    fr'^(#ifdef|#ifndef)\s+({SYMBOL_PATTERN})\b'
)


class PreprocessorCondition:
    def __init__(self, line_str: str, line: LineIdentifier):
        self._line_str = line_str
        self._line = line
        self._parent = None

    def __repr__(self) -> str:
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.__repr__()

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        """Evaluates whether this condition is true or false."""
        raise NotImplementedError()

    def is_lineage_true(self, preprocessor: Preprocessor) -> bool:
        if self.parent is None:
            return self.evaluate(preprocessor)
        return self.parent.is_lineage_true(preprocessor) or self.evaluate(preprocessor)

    @property
    def parent(self) -> PreprocessorCondition:
        return self._parent

    def _check_and_set_parent(self, parent: PreprocessorCondition):
        self._parent = parent

    @parent.setter
    def parent(self, parent: PreprocessorCondition):
        self._check_and_set_parent(parent)

    @property
    def is_dependent(self) -> bool:
        return False


class IfPreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        super().__init__(line_str, line)
        self._handle_matching(
            line_str, line,
            PREPROCESSOR_CONDITION_IF_PATTERN,
            PREPROCESSOR_CONDITION_IMPLIED_IF_PATTERN,
        )

    def _handle_matching(
                self,
                line_str: str,
                line: LineIdentifier,
                compare_pattern: re.Pattern[str],
                implied_pattern: re.Pattern[str],
            ) -> None:
        match = compare_pattern.match(line_str.strip())
        if match is None:
            match2 = implied_pattern.match(line_str.strip())
            if match2 is None:
                raise ValueError(f'Invalid preprocessor condition at line: {line_str}')
            self._lhs_expression = match2.group(1)
            self._operator = '!='
            self._rhs_expression = '0'
        else:
            self._lhs_expression = match.group(1)
            self._operator = match.group(2)
            self._rhs_expression = match.group(3) or match.group(4) or match.group(5)

    def __repr__(self) -> str:
        return f'IfPreprocessorCondition<#if {self._lhs_expression} {self._operator} {self._rhs_expression}>'

    def _check_and_set_parent(self, parent: PreprocessorCondition):
        raise ValueError('Cannot set parent of an IfPreprocessorCondition')

    def _evaluate_condition(self, preprocessor: Preprocessor) -> bool:
        lhs_resolved = preprocessor.resolve_symbols(self._line, self._lhs_expression)
        rhs_resolved = preprocessor.resolve_symbols(self._line, self._rhs_expression)

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

        if self._operator == '==':
            return lhs_value == rhs_value
        elif self._operator == '!=':
            return lhs_value != rhs_value
        elif self._operator == '>':
            return lhs_value > rhs_value
        elif self._operator == '>=':
            return lhs_value >= rhs_value
        elif self._operator == '<':
            return lhs_value < rhs_value
        elif self._operator == '<=':
            return lhs_value <= rhs_value
        else:
            raise ValueError(f'Unknown operator {self._operator}')

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        return self._evaluate_condition(preprocessor)


class ElifPreprocessorCondition(IfPreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        # skipping the super() init here as we need for it to not do the matching
        self._line_str = line_str
        self._line = line

        self._handle_matching(
            line_str, line,
            PREPROCESSOR_CONDITION_ELIF_PATTERN,
            PREPROCESSOR_CONDITION_IMPLIED_ELIF_PATTERN,
        )

    def __repr__(self) -> str:
        return f'ElifPreprocessorCondition<#elif {self._lhs_expression} {self._operator} {self._rhs_expression}>'

    def _check_and_set_parent(self, parent: PreprocessorCondition):
        if isinstance(parent, ElifPreprocessorCondition) or isinstance(parent, IfPreprocessorCondition):
            self._parent = parent
        else:
            raise ValueError('#elif can only have #if or #elif as a parent')

    @property
    def is_dependent(self) -> bool:
        return True

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        # if the parent is true, this should be false regardless
        # if its condition evaluates true. If the parent lineage is false,
        # this should evaluate to true if its condition evaluates true.
        if self.parent is None:
            sys.exit(f'ERROR - Internal: parent condition not set for {self} at line {self._line}')
        if self.parent.is_lineage_true(preprocessor):
            return False
        return self._evaluate_condition(preprocessor)


class IfdefPreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        super().__init__(line_str, line)

        match = PREPROCESSOR_CONDITION_IFDEF_PATTERN.match(line_str.strip())
        if match is None:
            raise ValueError(f'Invalid preprocessor condition at line: {line_str}')
        self._is_ifndef = match.group(1) == '#ifndef'
        self._symbol = match.group(2)

    def __repr__(self) -> str:
        return f'IfdefPreprocessorCondition<{"#ifndef" if self._is_ifndef else "#ifdef"} {self._symbol}>'

    def _check_and_set_parent(self, parent: PreprocessorCondition):
        raise ValueError('Cannot set parent of an IfdefPreprocessorCondition')

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        symbol = preprocessor.get_symbol(self._symbol)
        if symbol is None:
            return self._is_ifndef
        else:
            return not self._is_ifndef


class ElsePreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        super().__init__(line_str, line)

    def __repr__(self) -> str:
        return 'ElsePreprocessorCondition<#else>'

    def _check_and_set_parent(self, parent: PreprocessorCondition):
        if isinstance(parent, ElsePreprocessorCondition) or isinstance(parent, EndifPreprocessorCondition):
            raise ValueError('#else must have a conditional as a parent')
        self._parent = parent

    @property
    def is_dependent(self) -> bool:
        return True

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        if self.parent is None:
            sys.exit(f'ERROR - Internal: parent condition not set for {self} at line {self._line}')
        return not self.parent.is_lineage_true(preprocessor)


class EndifPreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        super().__init__(line_str, line)

    def __repr__(self) -> str:
        return 'EndifPreprocessorCondition<#endif>'

    def _check_and_set_parent(self, parent: PreprocessorCondition):
        if isinstance(parent, EndifPreprocessorCondition):
            raise ValueError('#endif must have a conditional as a parent')
        self._parent = parent

    @property
    def is_dependent(self) -> bool:
        return True

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        return True


class MutePreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        super().__init__(line_str, line)

    def __repr__(self) -> str:
        return f'MutePreprocessorCondition<{self.self._line_str}>'

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        return True


class UnmutePreprocessorCondition(PreprocessorCondition):
    def __init__(self, line_str: str, line: LineIdentifier):
        super().__init__(line_str, line)

    def __repr__(self) -> str:
        return f'UnmutePreprocessorCondition<{self.self._line_str}>'

    def evaluate(self, preprocessor: Preprocessor) -> bool:
        return True
