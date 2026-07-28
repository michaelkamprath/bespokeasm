import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.symbol import SYMBOL_PATTERN
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import ExpressionUseContext
from bespokeasm.expression import parse_expression
from bespokeasm.expression import TokenType
from bespokeasm.utilities import is_valid_label

_FLOW_OPERATOR_PATTERN = re.compile(
    r'\b(?:COUNTER|OFFSET)\s*\(',
    flags=re.IGNORECASE,
)
# A flow operator call may not be assembled from separate expansion fragments
# (the name from a macro value, the parenthesis from the referencing context):
# that split form defeats positional argument protection. The hazard exists
# only in *call position* — a flow keyword used as a plain value is an
# ordinary identifier, which non-flow ISAs legitimately allow. Detection
# therefore couples a trailing operator name in one fragment with an opening
# parenthesis in the adjoining fragment.
_TRAILING_FLOW_OPERATOR_PATTERN = re.compile(
    r'\b(?:COUNTER|OFFSET|COORDINATE)\s*$',
    flags=re.IGNORECASE,
)
_TRAILING_SYMBOL_PATTERN = re.compile(rf'\b({SYMBOL_PATTERN})\s*$')
_OPEN_CALL_PATTERN = re.compile(r'\s*\(')
# Only the name immediately after the opening parenthesis is protected: for
# COORDINATE(counter, offset) the offset is a value expression and remains
# macro-resolvable.
_FLOW_ARGUMENT_PATTERN = re.compile(
    r'(\b(?:COUNTER|OFFSET|COORDINATE)\s*\(\s*)((?:[A-Za-z][A-Za-z0-9_]*|'
    r'_(?!_)[A-Za-z0-9_]+|\.[A-Za-z0-9_]+))',
    flags=re.IGNORECASE,
)


def macro_expansion_introduces_flow_operator(
    preprocessor: Preprocessor,
    text: str,
) -> bool:
    """Return whether any macro reachable from ``text`` carries a flow operator.

    This is a dependency *scan*, not an expansion: it walks symbol values
    breadth-first with a visited set, so it tolerates definition cycles and
    never grows any text. It exists for classification — deciding whether a
    general-looking construct is actually flow-dependent — without evaluating
    operands that an ignored (``--no-static-analysis``) construct must never
    evaluate.
    """
    seen: set[str] = set()
    pending = [text]
    while pending:
        current = pending.pop()
        if _FLOW_OPERATOR_PATTERN.search(current):
            return True
        for match in re.finditer(rf'\b({SYMBOL_PATTERN})\b', current):
            name = match.group(1)
            symbol = preprocessor.get_symbol(name)
            if symbol is None:
                continue
            # A symbol referenced in call position whose expansion ends with
            # a bare operator name would assemble a split flow call; the
            # resolver rejects that form, and for classification it counts as
            # flow dependence.
            if _OPEN_CALL_PATTERN.match(current[match.end():]) and (
                _expands_to_trailing_flow_operator(preprocessor, name, frozenset())
            ):
                return True
            if name not in seen:
                seen.add(name)
                pending.append(str(symbol.value))
    return False


def _expands_to_trailing_flow_operator(
    preprocessor: Preprocessor,
    name: str,
    expanding: frozenset[str],
) -> bool:
    """Return whether a symbol's transitive expansion ends with a flow keyword.

    Cycle-tolerant and expansion-free: only the trailing token of each value
    is followed. A trailing token that is itself a defined symbol is chased
    instead of being matched as an operator, so an ISA that legitimately
    defines one of these words (possible when the ISA does not enable flow
    counters) resolves to that definition rather than the flow meaning.
    """
    if name in expanding:
        return False
    symbol = preprocessor.get_symbol(name)
    if symbol is None:
        return False
    value = str(symbol.value)
    trailing = _TRAILING_SYMBOL_PATTERN.search(value)
    if trailing is not None and preprocessor.get_symbol(trailing.group(1)) is not None:
        return _expands_to_trailing_flow_operator(
            preprocessor,
            trailing.group(1),
            expanding | {name},
        )
    return bool(_TRAILING_FLOW_OPERATOR_PATTERN.search(value))


def resolve_symbols_protecting_flow_names(
    preprocessor: Preprocessor,
    line_id: LineIdentifier,
    text: str,
) -> str:
    """Resolve ``#define`` macros in expression text, keeping flow names literal.

    Value expressions accept every compile-time constant kind, including
    preprocessor macros — but the counter/coordinate names passed to
    ``COUNTER()``, ``OFFSET()``, and ``COORDINATE()`` identify flow entities
    and must never be macro-substituted, in any context.

    The algorithm mirrors ``Preprocessor.resolve_symbols``: each symbol's
    value is resolved recursively with the active expansion chain tracked, so
    a definition cycle errors on its first self-reference (before a
    self-amplifying value like ``A → A+A`` can grow the text), and a
    legitimate chain of any depth resolves fully. Flow-operator argument
    names are re-protected at every expansion level — an expansion may itself
    introduce a flow expression (e.g. a command-line predefined symbol whose
    value is ``COUNTER(stack)``). The placeholder is NUL-delimited so it can
    never lex as a preprocessor symbol (a user could legally ``#define`` any
    identifier-shaped placeholder) and restores unambiguously.
    """
    return _resolve_protecting_flow_names(preprocessor, line_id, text, frozenset())


def _resolve_protecting_flow_names(
    preprocessor: Preprocessor,
    line_id: LineIdentifier,
    text: str,
    expanding: frozenset[str],
) -> str:
    protected_names: list[str] = []

    def protect(match: re.Match[str]) -> str:
        protected_names.append(match.group(2))
        return f'{match.group(1)}\x00{len(protected_names) - 1}\x00'

    current = _FLOW_ARGUMENT_PATTERN.sub(protect, text)
    while True:
        defined_names = [
            name
            for name in dict.fromkeys(
                re.findall(rf'\b({SYMBOL_PATTERN})\b', current)
            )
            if preprocessor.get_symbol(name) is not None
        ]
        if not defined_names:
            break
        for name in defined_names:
            if name in expanding:
                sys.exit(
                    f'ERROR - {line_id}: Preprocessor macro symbol {name} is '
                    'indirectly referring to itself'
                )
            replacement = _resolve_protecting_flow_names(
                preprocessor,
                line_id,
                preprocessor.get_symbol(name).value,
                expanding | {name},
            )
            replacement = _FLOW_ARGUMENT_PATTERN.sub(protect, replacement)

            def splice(
                match: re.Match[str],
                _replacement: str = replacement,
                _name: str = name,
            ) -> str:
                # Reject a flow operator call assembled from separate
                # fragments: the expansion supplying the name while the
                # context supplies the parenthesis (or vice versa). A bare
                # keyword spliced as a plain value is left alone — non-flow
                # ISAs use these words ordinarily.
                forms_split_call = (
                    _TRAILING_FLOW_OPERATOR_PATTERN.search(_replacement)
                    and _OPEN_CALL_PATTERN.match(match.string[match.end():])
                ) or (
                    _TRAILING_FLOW_OPERATOR_PATTERN.search(match.string[:match.start()])
                    and _OPEN_CALL_PATTERN.match(_replacement)
                )
                if forms_split_call:
                    sys.exit(
                        f'ERROR - {line_id}: macro "{_name}" expansion forms a '
                        'flow operator call from separate fragments; flow '
                        'operators must be written as complete calls such as '
                        'COUNTER(name)'
                    )
                return _replacement

            current = re.sub(rf'\b{re.escape(name)}\b', splice, current)
        expanding = expanding | set(defined_names)
    for index, name in enumerate(protected_names):
        current = current.replace(f'\x00{index}\x00', name)
    return current


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
        preprocessor: Preprocessor | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        self._isa_model = isa_model
        self._preprocessor = preprocessor

    def _resolve_value_text(self, text: str) -> str:
        """Resolve preprocessor macros in one directive value expression.

        With static analysis disabled these directives are ignored as if
        stripped from the source, so their values must not be macro-resolved
        (resolution could itself fail, e.g. on a macro cycle only they
        reference); source-level syntax validation still runs on the raw text.
        """
        if (
            self._preprocessor is None
            or not self._isa_model.static_analysis_enabled
        ):
            return text
        return resolve_symbols_protecting_flow_names(
            self._preprocessor,
            self.line_id,
            text,
        )

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
        identifier_names: frozenset[str] = frozenset(),
    ) -> dict[str, ExpressionNode]:
        """Parse whitespace-separated ``name=expression`` directive parameters.

        With static analysis disabled, flow directives are analysis-only syntax
        that must be ignored as if stripped from the source. Syntactic
        validation still runs, while well-formed parameters belonging to a
        future milestone are ignored until their analysis is available.

        Values are ordinary compile-time expressions and receive preprocessor
        macro resolution — except the ``identifier_names`` parameters (such as
        ``as=`` and ``mode=``), whose values name flow entities and must stay
        literal.
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
            if name not in identifier_names:
                value_text = self._resolve_value_text(value_text)
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
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        preprocessor: Preprocessor | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model, preprocessor)
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
            identifier_names=frozenset({'as', 'mode'}),
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
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        preprocessor: Preprocessor | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model, preprocessor)
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
        preprocessor: Preprocessor | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model, preprocessor)
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
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        preprocessor: Preprocessor | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model, preprocessor)
        match = self._PATTERN.fullmatch(instruction.strip())
        self._value_expression = (
            self._parse_flow_expression(self._resolve_value_text(match.group(2)))
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
    )


class FlowResumeLine(FlowNamedCounterDirectiveLine):
    """Analysis-only ``#resume counter = expression`` directive."""

    _DIRECTIVE = 'resume'
    _PATTERN = re.compile(
        r'^#resume\s+(\S+)\s*=\s*(.+)$',
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        preprocessor: Preprocessor | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone, isa_model, preprocessor)
        match = self._PATTERN.fullmatch(instruction.strip())
        self._value_expression = (
            self._parse_flow_expression(self._resolve_value_text(match.group(2)))
            if match is not None
            else None
        )

    @property
    def value_expression(self) -> ExpressionNode | None:
        """Return the expression used to restore a known scalar value."""
        return self._value_expression
