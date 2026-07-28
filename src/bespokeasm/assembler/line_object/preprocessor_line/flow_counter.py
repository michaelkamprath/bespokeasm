import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import ExpressionUseContext
from bespokeasm.expression import parse_expression
from bespokeasm.expression import TokenType
from bespokeasm.utilities import is_valid_label


class FlowCounterDirectiveLine(PreprocessorLine):
    """Base class for analysis-only flow-counter directives."""

    _PARAMETER_PATTERN = re.compile(
        r'(?:(?<=\s)|^)([A-Za-z_]\w*)\s*=',
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        self._isa_model = isa_model

    def _error(self, message: str) -> None:
        """Report a source-local diagnostic in the flow category."""
        self._isa_model.diagnostic_reporter.error(
            self.line_id,
            message,
            category='flow',
        )

    def _parse_parameters(
        self,
        text: str,
        allowed: set[str],
    ) -> dict[str, ExpressionNode]:
        """Parse whitespace-separated ``name=expression`` directive parameters.

        With static analysis disabled, flow directives are analysis-only syntax
        that must be ignored as if stripped from the source. Syntactic
        validation still runs, while well-formed parameters belonging to a
        future milestone are ignored until their analysis is available.
        """
        enforce = self._isa_model.static_analysis_enabled
        if not text.strip():
            return {}
        matches = list(self._PARAMETER_PATTERN.finditer(text))
        if not matches or text[:matches[0].start()].strip():
            self._error(f'invalid flow directive parameters: {text.strip()}')
            return {}
        parsed_parameters = {}
        seen_names = set()
        for index, match in enumerate(matches):
            name = match.group(1).lower()
            value_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            value_text = text[match.end():value_end].strip()
            if not value_text:
                self._error(f'flow directive parameter "{name}" requires a value')
                continue
            if name in seen_names:
                self._error(f'duplicate flow directive parameter "{name}"')
                continue
            seen_names.add(name)
            try:
                value_expression = parse_expression(
                    self.line_id,
                    value_text,
                    self._isa_model.default_numeric_base,
                )
            except (SyntaxError, SystemExit) as error:
                self._error(str(error))
                continue
            parsed_parameters[name] = value_expression

        parameters = {}
        for name, value_expression in parsed_parameters.items():
            if name not in allowed:
                if enforce:
                    self._error(
                        f'flow directive parameter "{name}" is not supported'
                    )
                continue
            parameters[name] = value_expression
        return parameters

    def evaluate_parameter(self, name: str) -> int | None:
        """Resolve a parsed parameter in the directive's assigned symbol scopes."""
        expression = self._parameters.get(name)
        if expression is None:
            return None
        return expression.get_value(
            self.symbol_scope,
            self.active_named_scopes,
            self.line_id,
        )

    def identifier_parameter(self, name: str) -> str | None:
        """Return a parameter that must be one unqualified identifier."""
        expression = self._parameters.get(name)
        if expression is None:
            return None
        if (
            expression.token_type not in {TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM}
            or expression.left_child is not None
            or expression.right_child is not None
            or not is_valid_label(str(expression.value))
        ):
            self._error(
                f'flow directive parameter "{name}" requires one identifier'
            )
            return None
        return str(expression.value)

    def _parse_flow_expression(self, text: str) -> ExpressionNode | None:
        """Parse an expression evaluated only by the flow-analysis pass."""
        try:
            return parse_expression(
                self.line_id,
                text,
                self._isa_model.default_numeric_base,
                context=ExpressionUseContext.FLOW_DIRECTIVE,
            )
        except (SyntaxError, SystemExit) as error:
            self._error(str(error))
            return None

    def _validate_counter_name(self, counter_name: str, context: str) -> None:
        """Require a global or file-scoped flow-counter instance name."""
        if not is_valid_label(counter_name) or counter_name.startswith('.'):
            self._error(f'invalid flow counter {context} "{counter_name}"')

    def _validate_feature_enabled(self) -> None:
        """Reject active flow syntax when the selected ISA lacks the feature."""
        if (
            self._isa_model.static_analysis_enabled
            and not self._isa_model.flow_counters_enabled
        ):
            self._error('this instruction set does not enable flow counters')


class FlowTrackLine(FlowCounterDirectiveLine):
    """Analysis-only ``#track`` directive."""

    _PATTERN = re.compile(
        r'^#track\s+(\S+)(?:\s+(.*))?$',
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model)
        match = self._PATTERN.fullmatch(instruction.strip())
        if match is None:
            self._error(f'invalid #track directive syntax: {instruction}')
            self._counter_class = None
            self._parameters = {}
            return
        self._counter_class = match.group(1)
        if not is_valid_label(self._counter_class):
            self._error(f'invalid flow counter class name "{self._counter_class}"')
        self._parameters = self._parse_parameters(
            match.group(2) or '',
            {'as', 'mode', 'init', 'exit'},
        )
        instance_name = self.identifier_parameter('as')
        if instance_name is not None:
            self._validate_counter_name(instance_name, 'instance name')
        self._validate_feature_enabled()

    @property
    def counter_class(self) -> str:
        """Return the configured counter class requested by ``#track``."""
        return self._counter_class

    @property
    def counter_name(self) -> str:
        """Return the effective instance name created by ``#track``."""
        return self.identifier_parameter('as') or self._counter_class


class FlowEndTrackLine(FlowCounterDirectiveLine):
    """Analysis-only ``#endtrack`` directive."""

    _PATTERN = re.compile(
        r'^#endtrack\s+(\S+)(?:\s+(.*))?$',
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model)
        match = self._PATTERN.fullmatch(instruction.strip())
        if match is None:
            self._error(f'invalid #endtrack directive syntax: {instruction}')
            self._counter_name = None
            self._parameters = {}
            return
        self._counter_name = match.group(1)
        self._validate_counter_name(self._counter_name, 'name')
        self._parameters = self._parse_parameters(match.group(2) or '', {'exit'})
        self._validate_feature_enabled()

    @property
    def counter_name(self) -> str:
        """Return the active counter name requested by ``#endtrack``."""
        return self._counter_name


class FlowNamedCounterDirectiveLine(FlowCounterDirectiveLine):
    """Base for directives whose first operand names a counter instance."""

    _DIRECTIVE = ''
    _PATTERN = None

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model)
        match = self._PATTERN.fullmatch(instruction.strip())
        if match is None:
            self._error(
                f'invalid #{self._DIRECTIVE} directive syntax: {instruction}'
            )
            self._counter_name = None
            return
        self._counter_name = match.group(1)
        self._validate_counter_name(self._counter_name, 'name')
        self._validate_feature_enabled()

    @property
    def counter_name(self) -> str:
        """Return the counter instance targeted by this directive."""
        return self._counter_name


class FlowSetLine(FlowNamedCounterDirectiveLine):
    """Analysis-only ``#set counter = expression`` directive."""

    _DIRECTIVE = 'set'
    _PATTERN = re.compile(
        r'^#set\s+(\S+)\s*=\s*(.+)$',
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model)
        match = self._PATTERN.fullmatch(instruction.strip())
        self._value_expression = (
            self._parse_flow_expression(match.group(2))
            if match is not None
            else None
        )

    @property
    def value_expression(self) -> ExpressionNode | None:
        """Return the expression used to re-anchor the counter."""
        return self._value_expression


class FlowSuspendLine(FlowNamedCounterDirectiveLine):
    """Analysis-only ``#suspend counter`` directive."""

    _DIRECTIVE = 'suspend'
    _PATTERN = re.compile(
        r'^#suspend\s+(\S+)$',
        flags=re.IGNORECASE,
    )


class FlowResumeLine(FlowNamedCounterDirectiveLine):
    """Analysis-only ``#resume counter = expression`` directive."""

    _DIRECTIVE = 'resume'
    _PATTERN = re.compile(
        r'^#resume\s+(\S+)\s*=\s*(.+)$',
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model)
        match = self._PATTERN.fullmatch(instruction.strip())
        self._value_expression = (
            self._parse_flow_expression(match.group(2))
            if match is not None
            else None
        )

    @property
    def value_expression(self) -> ExpressionNode | None:
        """Return the expression used to restore a known scalar value."""
        return self._value_expression
