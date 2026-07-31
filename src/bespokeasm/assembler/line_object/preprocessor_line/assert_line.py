import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import (
    macro_expansion_introduces_flow_operator,
)
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import (
    resolve_symbols_protecting_flow_names,
)
from bespokeasm.assembler.line_object.preprocessor_line.message import (
    parse_trailing_message_candidates,
)
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition import IfPreprocessorCondition
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import ExpressionUseContext
from bespokeasm.expression import parse_expression
from bespokeasm.utilities import is_valid_label


class AssertLine(PreprocessorLine):
    """A general compile-time assertion, optionally backed by flow analysis."""

    _FLOW_OPERATOR_PATTERN = re.compile(
        r'\b(?:COUNTER|OFFSET)\s*\(',
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        preprocessor: Preprocessor,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        self._isa_model = isa_model
        self._message = None
        self._color = None

        source = instruction.strip()
        condition_text = source[len('#assert'):].strip()
        if not condition_text:
            self._syntax_error(instruction)

        condition = None
        for parsed_message in parse_trailing_message_candidates(condition_text):
            condition = self._try_condition(parsed_message.leading_text)
            if condition is not None:
                condition_text = parsed_message.leading_text
                self._color = parsed_message.color
                self._message = parsed_message.text
                break

        if condition is None:
            condition = self._try_condition(condition_text)
        if condition is None:
            self._syntax_error(instruction)

        self._condition_text = condition_text
        self._comparison = condition.operator
        self._lhs_text = condition.lhs_expression.strip()
        self._rhs_text = condition.rhs_expression.strip()
        self._uses_explicit_flow = bool(
            self._FLOW_OPERATOR_PATTERN.search(self._lhs_text)
            or self._FLOW_OPERATOR_PATTERN.search(self._rhs_text)
        )

        is_unknown_bare_name = (
            is_valid_label(self._lhs_text)
            and not self._lhs_text.startswith('.')
            and preprocessor.get_symbol(self._lhs_text) is None
        )
        self._counter_name = (
            self._lhs_text
            if isa_model.flow_counters_enabled
            and is_unknown_bare_name
            else None
        )
        self._is_flow_dependent = (
            self._uses_explicit_flow or self._counter_name is not None
        )

        # Expansion can introduce a flow expression (e.g. a command-line
        # predefined symbol whose value is COUNTER(stack)), so flow dependence
        # is also determined from the operands' macro dependencies. This is a
        # cycle-tolerant scan, not a resolution: a flow-dependent assertion
        # may be ignored under --no-flow-checks, in which case its
        # operands — including a sibling operand carrying a macro cycle —
        # must never be evaluated during classification.
        if not self._is_flow_dependent and (
            macro_expansion_introduces_flow_operator(preprocessor, self._lhs_text)
            or macro_expansion_introduces_flow_operator(preprocessor, self._rhs_text)
        ):
            self._uses_explicit_flow = True
            self._is_flow_dependent = True

        if (
            self._uses_explicit_flow
            and not isa_model.flow_counters_enabled
        ):
            self._error(
                'this instruction set does not enable flow counters',
                category='flow',
            )

        # General evaluation belongs to general asserts only: a flow-dependent
        # assert (explicit operator, bare-name shorthand, or macro-introduced
        # flow expression) is evaluated by the flow-analysis pass and must not
        # compute a throwaway general result here.
        self._general_result = (
            None
            if self._is_flow_dependent
            else condition.evaluate(preprocessor)
        )
        self._flow_lhs_text = self._resolve_flow_expression(
            self._lhs_text,
            preprocessor,
        )
        self._flow_rhs_text = self._resolve_flow_expression(
            self._rhs_text,
            preprocessor,
        )
        self._flow_lhs_expression = None
        self._flow_rhs_expression = None
        self.enforce_general()

    def _try_condition(
        self,
        condition_text: str,
    ) -> IfPreprocessorCondition | None:
        """Parse one assertion condition using the canonical ``#if`` grammar."""
        try:
            condition = IfPreprocessorCondition(
                f'#if {condition_text}',
                self.line_id,
            )
            return condition if condition.is_complete else None
        except ValueError:
            return None

    def _syntax_error(self, instruction: str) -> None:
        self._error(f'invalid #assert directive syntax: {instruction}')

    def _error(
        self,
        message: str,
        *,
        category: str = 'user',
        color: str | None = None,
    ) -> None:
        """Report an assertion diagnostic through the assembler reporter."""
        self._isa_model.diagnostic_reporter.error(
            self.line_id,
            message,
            category=category,
            color=color,
        )

    def _resolve_flow_expression(
        self,
        expression: str,
        preprocessor: Preprocessor,
    ) -> str:
        """Resolve macros while preserving names passed to flow operators.

        The resolved text feeds only flow-dependent evaluation, which is
        skipped entirely under ``--no-flow-checks`` — so resolution is
        skipped too, keeping ignored flow assertions strip-equivalent even
        when resolution itself would fail (e.g. a macro cycle).
        """
        if not self._isa_model.flow_checks_enabled:
            return expression
        return resolve_symbols_protecting_flow_names(
            preprocessor,
            self.line_id,
            expression,
        )

    def _parse_flow_expression(self, expression: str) -> ExpressionNode:
        """Parse an assertion operand for deferred flow-aware evaluation."""
        try:
            return parse_expression(
                self.line_id,
                expression,
                self._isa_model.default_numeric_base,
                context=ExpressionUseContext.FLOW_DIRECTIVE,
            )
        except (SyntaxError, SystemExit) as error:
            self._error(str(error), category='flow')

    @property
    def condition_text(self) -> str:
        """Return the condition as written, excluding its optional message."""
        return self._condition_text

    @property
    def comparison(self) -> str:
        """Return the assertion's comparison operator."""
        return self._comparison

    @property
    def counter_name(self) -> str | None:
        """Return the counter named by legacy bare-name flow shorthand."""
        return self._counter_name

    @property
    def is_flow_dependent(self) -> bool:
        """Return whether evaluation requires the flow-analysis pass."""
        return self._is_flow_dependent

    @property
    def flow_lhs_expression(self) -> ExpressionNode:
        """Return the lazily parsed left operand for explicit flow assertions."""
        if self._flow_lhs_expression is None:
            self._flow_lhs_expression = self._parse_flow_expression(
                self._flow_lhs_text
            )
        return self._flow_lhs_expression

    @property
    def flow_rhs_expression(self) -> ExpressionNode:
        """Return the lazily parsed right operand for flow assertions."""
        if self._flow_rhs_expression is None:
            self._flow_rhs_expression = self._parse_flow_expression(
                self._flow_rhs_text
            )
        return self._flow_rhs_expression

    def enforce_general(self) -> None:
        """Fail assembly if a previously evaluated non-flow condition is false."""
        if self._is_flow_dependent or self._general_result is None:
            return
        if not self._general_result:
            message = self._message or (
                f'assertion failed: {self._condition_text}'
            )
            self._error(message, color=self._color)

    def report_flow_failure(
        self,
        default_message: str,
    ) -> None:
        """Report a failed flow assertion with its optional user message."""
        self._error(
            self._message or default_message,
            category='flow',
            color=self._color,
        )
