import operator
import re
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field

from bespokeasm.assembler.analysis import OperandSemanticKind
from bespokeasm.assembler.line_object.counter_coordinate_line import CounterCoordinateLine
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.preprocessor_line.assert_line import AssertLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowEndTrackLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowResumeLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowSetLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowSuspendLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowTrackLine
from bespokeasm.assembler.symbol_scope.flow_symbols import CounterCoordinate
from bespokeasm.assembler.symbol_scope.flow_symbols import FlowSymbolError
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import parse_expression
from bespokeasm.expression import TokenType


@dataclass
class _LinearCounterState:
    counter_class: str
    name: str
    instance_id: int
    value: int
    initial_value: int
    expected_exit: int | None
    config: dict
    opened_by: FlowTrackLine
    coordinates: list[CounterCoordinate] = field(default_factory=list)
    path_live: bool = True
    suspended: bool = False


class FlowLinearAnalyzer:
    """Source-order analyzer for scalar, straight-line flow counters."""

    def __init__(self, model, diagnostic_reporter) -> None:
        """Create an analyzer bound to one immutable ISA model and reporter."""
        self._model = model
        self._diagnostic_reporter = diagnostic_reporter
        self._active: dict[str, _LinearCounterState] = {}
        self._next_instance_id = 0

    @staticmethod
    def source_uses_flow(line_objects) -> bool:
        """Return whether compiled source contains any shipped flow construct."""
        return any(
            (
                isinstance(line_object, AssertLine)
                and line_object.is_flow_dependent
            )
            or isinstance(
                line_object,
                (
                    FlowEndTrackLine
                    | FlowResumeLine
                    | FlowSetLine
                    | FlowSuspendLine
                    | FlowTrackLine
                    | CounterCoordinateLine
                ),
            )
            or bool(line_object.flow_expression_nodes)
            for line_object in line_objects
        )

    def _error(self, line_object, message: str) -> None:
        # The reporter is fail-fast today (error() exits), but every call site
        # still guards-and-returns afterward so an accumulate-and-continue
        # reporter cannot turn an error path into a crash on invalid state.
        self._diagnostic_reporter.error(
            line_object.line_id,
            message,
            category='flow',
        )

    def _check_bounds(
        self,
        line_object,
        state: _LinearCounterState,
    ) -> None:
        """Report a bound violation for one counter at this source line."""
        minimum = state.config.get('min_value')
        maximum = state.config.get('max_value')
        if minimum is not None and state.value < minimum:
            self._error(
                line_object,
                f'flow counter "{state.name}" underflow: '
                f'value {state.value} is below minimum {minimum}',
            )
        if maximum is not None and state.value > maximum:
            self._error(
                line_object,
                f'flow counter "{state.name}" overflow: '
                f'value {state.value} exceeds maximum {maximum}',
            )

    def _open(self, line_object: FlowTrackLine) -> None:
        """Validate and initialize the scalar counter named by ``#track``."""
        counter_name = line_object.counter_name
        prior_state = self._active.get(counter_name)
        if prior_state is not None:
            suffix = (
                f'the prior region is still lexically open after its terminal; '
                f'add a lexical #endtrack {prior_state.name} before opening another counter'
                if not prior_state.path_live
                else f'insert #endtrack {prior_state.name} before opening another counter'
            )
            self._error(
                line_object,
                f'flow counter "{prior_state.name}" is still active; {suffix}',
            )
            return
        counter_config = self._model.flow_counters.get(line_object.counter_class)
        if counter_config is None:
            self._error(
                line_object,
                f'flow counter class "{line_object.counter_class}" is not declared by this instruction set',
            )
            return
        if counter_config.get('join', 'require-equal') != 'require-equal':
            self._error(
                line_object,
                f'flow counter class "{line_object.counter_class}" is not scalar; '
                'interval analysis is not available in M4',
            )
            return
        if not self._model.flow_counter_has_effect_metadata(line_object.counter_class):
            self._error(
                line_object,
                f'flow counter class "{line_object.counter_class}" is inert: '
                'no instruction declares an effect or terminal',
            )
            return

        mode_name = line_object.identifier_parameter('mode')
        mode_config = {}
        if mode_name is not None:
            mode_config = counter_config.get('entry_modes', {}).get(mode_name)
            if mode_config is None:
                self._error(
                    line_object,
                    f'flow counter class "{line_object.counter_class}" has no '
                    f'entry mode "{mode_name}"',
                )
                return

        initial = line_object.evaluate_parameter('init')
        if initial is None:
            initial = mode_config.get(
                'init',
                counter_config.get('default_init', 0),
            )
        expected_exit = line_object.evaluate_parameter('exit')
        if expected_exit is None:
            expected_exit = mode_config.get('exit')
        if (
            expected_exit is None
            and counter_config.get('exit_policy', 'balanced') == 'balanced'
        ):
            expected_exit = initial
        state = _LinearCounterState(
            counter_class=line_object.counter_class,
            name=counter_name,
            instance_id=self._next_instance_id,
            value=initial,
            initial_value=initial,
            expected_exit=expected_exit,
            config=counter_config,
            opened_by=line_object,
        )
        self._active[counter_name] = state
        self._next_instance_id += 1
        self._check_bounds(line_object, state)

    def _close(self, line_object: FlowEndTrackLine) -> None:
        """Apply the exit contract and close the active tracking region."""
        state = self._active.get(line_object.counter_name)
        if state is None:
            self._error(
                line_object,
                f'#endtrack {line_object.counter_name} has no active counter',
            )
            return
        if state.suspended:
            if line_object.evaluate_parameter('exit') is not None:
                self._error(
                    line_object,
                    f'#endtrack {state.name} cannot check exit= while the '
                    'counter is suspended',
                )
                return
            del self._active[state.name]
            return
        if not state.path_live:
            del self._active[state.name]
            return
        expected = line_object.evaluate_parameter('exit')
        if expected is None:
            expected = state.expected_exit
        self._check_exit(line_object, state, expected)
        del self._active[state.name]

    def _check_exit(
        self,
        line_object,
        state: _LinearCounterState,
        expected: int | None = None,
    ) -> None:
        """Check one active path against an exact exit contract when present."""
        if expected is None:
            expected = state.expected_exit
        if expected is not None and state.value != expected:
            self._error(
                line_object,
                f'flow counter "{state.name}" exit mismatch: '
                f'expected {expected}, actual {state.value}',
            )

    def _require_live_state(
        self,
        line_object,
        counter_name: str,
        operation: str,
    ) -> _LinearCounterState | None:
        """Return a named live state or report why an operation cannot use it."""
        state = self._active.get(counter_name)
        if state is None:
            self._error(
                line_object,
                f'{operation} references inactive flow counter "{counter_name}"',
            )
            return None
        if not state.path_live:
            self._error(
                line_object,
                f'{operation} is unreachable after flow counter '
                f'"{counter_name}" terminated',
            )
            return None
        return state

    def _counter_name(self, line_object, node: ExpressionNode) -> str | None:
        """Extract and validate the simple counter-name argument to ``COUNTER``."""
        argument = node.left_child
        if (
            node.token_type != TokenType.T_COUNTER
            or argument is None
            or argument.token_type not in {TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM}
            or argument.left_child is not None
            or argument.right_child is not None
        ):
            self._error(line_object, 'COUNTER() requires one counter name')
            return None
        return str(argument.value)

    def _coordinate_name(self, line_object, node: ExpressionNode) -> str | None:
        """Extract the exact coordinate spelling supplied to ``OFFSET()``."""
        argument = node.left_child
        if (
            node.token_type != TokenType.T_OFFSET
            or argument is None
            or argument.token_type not in {TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM}
            or argument.left_child is not None
            or argument.right_child is not None
        ):
            self._error(line_object, 'OFFSET() requires one counter-coordinate symbol')
            return None
        return str(argument.value)

    @staticmethod
    def _lookup_coordinate(line_object, label: str) -> CounterCoordinate | None:
        """Resolve a coordinate using the declaration line's active namespaces."""
        if line_object.active_named_scopes is not None:
            return line_object.active_named_scopes.named_scope_manager.get_counter_coordinate(
                label,
                line_object.symbol_scope,
                line_object.active_named_scopes,
            )
        return line_object.symbol_scope.get_counter_coordinate(label)

    def _resolve_offset(self, line_object, node: ExpressionNode) -> None:
        """Resolve ``OFFSET(coordinate)`` against the active pre-line state."""
        label = self._coordinate_name(line_object, node)
        if label is None:
            return
        coordinate = self._lookup_coordinate(line_object, label)
        if coordinate is None:
            self._error(
                line_object,
                f'OFFSET({label}) requires a symbol declared with :=',
            )
            return
        state = self._active.get(coordinate.counter_name)
        if state is None:
            self._error(
                line_object,
                f'OFFSET({label}) references inactive flow counter "{coordinate.counter_name}"',
            )
            return
        if not state.path_live:
            self._error(
                line_object,
                f'OFFSET({label}) is unreachable after the flow counter path terminated',
            )
            return
        if state.suspended:
            self._error(
                line_object,
                f'OFFSET({label}) cannot be resolved while flow counter '
                f'"{state.name}" is suspended',
            )
            return
        if coordinate.counter_instance_id != state.instance_id:
            self._error(
                line_object,
                f'OFFSET({label}) belongs to an earlier tracking instance of '
                f'counter "{coordinate.counter_name}"',
            )
            return
        if not coordinate.is_valid:
            self._error(
                line_object,
                f'counter coordinate "{label}" is invalid because its saved position '
                'was crossed and is no longer live',
            )
            return
        node.resolve_flow_value(state.value - coordinate.value)

    def _resolve_expressions(self, line_object, nodes: tuple[ExpressionNode, ...]) -> None:
        """Deposit the active pre-instruction value into deferred expressions."""
        for node in nodes:
            if node.token_type == TokenType.T_OFFSET:
                self._resolve_offset(line_object, node)
                continue
            counter_name = self._counter_name(line_object, node)
            if counter_name is None:
                continue
            state = self._require_live_state(
                line_object,
                counter_name,
                f'COUNTER({counter_name})',
            )
            if state is None:
                continue
            if state.suspended:
                self._error(
                    line_object,
                    f'COUNTER({counter_name}) cannot be resolved while flow counter '
                    f'"{counter_name}" is suspended',
                )
                continue
            node.resolve_flow_value(state.value)

    def _declare_coordinate(self, line_object: CounterCoordinateLine) -> None:
        """Validate, resolve, and register one immutable counter coordinate."""
        if (
            line_object.counter_name is None
            or line_object.offset_expression is None
        ):
            self._error(
                line_object,
                'a coordinate declaration must use COORDINATE(counter, offset)',
            )
            return
        counter_name = line_object.counter_name
        state = self._require_live_state(
            line_object,
            counter_name,
            f'COORDINATE({counter_name}, ...)',
        )
        if state is None:
            return
        if state.suspended:
            self._error(
                line_object,
                f'COORDINATE({counter_name}, ...) cannot declare a coordinate '
                'while the counter is suspended',
            )
            return

        for label in self._expression_labels(line_object.offset_expression):
            if self._lookup_coordinate(line_object, label) is not None:
                self._error(
                    line_object,
                    'the offset of a coordinate declaration cannot contain '
                    f'counter coordinate "{label}"',
                )
                return

        try:
            declared_offset = line_object.offset_expression.get_value(
                line_object.symbol_scope,
                line_object.active_named_scopes,
                line_object.line_id,
            )
        except ValueError as error:
            self._error(line_object, str(error))
            return
        offset_policy = state.config.get('coordinate_offsets', 'both')
        if (
            declared_offset == 0
            and not state.config.get('allow_zero_offset', True)
        ):
            self._error(
                line_object,
                f'flow counter "{counter_name}" does not permit zero coordinate offsets',
            )
            return
        if offset_policy == 'positive' and declared_offset < 0:
            self._error(
                line_object,
                f'flow counter "{counter_name}" permits only positive coordinate offsets; '
                f'got {declared_offset}',
            )
            return
        if offset_policy == 'negative' and declared_offset > 0:
            self._error(
                line_object,
                f'flow counter "{counter_name}" permits only negative coordinate offsets; '
                f'got {declared_offset}',
            )
            return

        coordinate = CounterCoordinate(
            label=line_object.label,
            value=state.value - declared_offset,
            counter_name=counter_name,
            counter_instance_id=state.instance_id,
            declared_offset=declared_offset,
            line_id=line_object.line_id,
        )
        try:
            named_scope_manager = line_object.active_named_scopes.named_scope_manager
            if not named_scope_manager.set_counter_coordinate(
                coordinate,
                line_object.active_named_scopes,
            ):
                line_object.symbol_scope.set_counter_coordinate(coordinate)
        except ValueError as error:
            self._error(line_object, str(error))
            return
        state.coordinates.append(coordinate)

    @classmethod
    def _expression_labels(cls, node: ExpressionNode) -> set[str]:
        """Collect scalar symbol tokens while excluding flow-function arguments."""
        if node.token_type in {TokenType.T_COUNTER, TokenType.T_OFFSET}:
            return set()
        if node.token_type in {TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM}:
            return {str(node.value)}
        labels = (
            cls._expression_labels(node.left_child)
            if node.left_child is not None
            else set()
        )
        if not node.is_unary and node.right_child is not None:
            labels.update(cls._expression_labels(node.right_child))
        return labels

    @staticmethod
    def _path_value(mapping: Mapping, path: str):
        """Read a dotted metadata path, returning ``None`` when it is absent."""
        value = mapping
        for component in path.split('.'):
            if not isinstance(value, Mapping) or component not in value:
                return None
            value = value[component]
        return value

    def _operand_semantic_value(self, line_object, record, index: int) -> int:
        """Resolve one ``ARG(n)`` to its source-level compile-time value."""
        if index >= len(record.operands):
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" effect references ARG({index}), '
                f'but the selected variant has {len(record.operands)} source operand(s)',
            )
            return 0
        operand = record.operands[index]
        if (
            operand.semantic_kind is not OperandSemanticKind.COMPILE_TIME_EXPRESSION
            or operand.expression is None
        ):
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" effect references ARG({index}), '
                f'but operand "{operand.source_text}" is runtime-valued',
            )
            return 0
        if operand.expression.contains_flow_value():
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" effect ARG({index}) cannot '
                'depend on COUNTER() or OFFSET()',
            )
            return 0
        try:
            return operand.expression.to_node().get_value(
                line_object.symbol_scope,
                line_object.active_named_scopes,
                line_object.line_id,
            )
        except (
            ArithmeticError,
            RuntimeError,
            SyntaxError,
            SystemExit,
            ValueError,
        ) as error:
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" cannot resolve ARG({index}) '
                f'as a compile-time value: {error}',
            )
            return 0

    def _resolve_delta(
        self,
        line_object,
        record,
        delta,
        state: _LinearCounterState,
    ) -> int:
        """Evaluate an integer or ``ARG(n)`` flow-delta expression."""
        if isinstance(delta, bool):
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" has an invalid boolean effect',
            )
            return 0
        if isinstance(delta, int):
            return delta
        if not isinstance(delta, str):
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" has a non-scalar effect for '
                f'"{state.counter_class}"; edge-dependent effects are not available in M4',
            )
            return 0
        if 'COUNT(' in delta:
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" uses COUNT(); '
                'structural operand effects are not available in M4',
            )
            return 0

        def substitute_argument(match: re.Match) -> str:
            value = self._operand_semantic_value(
                line_object,
                record,
                int(match.group(1)),
            )
            return f'({value})'

        expression_text = re.sub(r'ARG\((\d+)\)', substitute_argument, delta)
        try:
            expression = parse_expression(
                line_object.line_id,
                expression_text,
                self._model.default_numeric_base,
            )
            return expression.get_value(
                line_object.symbol_scope,
                line_object.active_named_scopes,
                line_object.line_id,
            )
        except (
            ArithmeticError,
            RuntimeError,
            SyntaxError,
            SystemExit,
            ValueError,
        ) as error:
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" has an invalid flow effect '
                f'"{delta}": {error}',
            )
            return 0

    def _instruction_delta(
        self,
        line_object,
        record,
        state: _LinearCounterState,
    ) -> int | None:
        """Fetch and resolve one active class's selected instruction effect."""
        source = state.config.get(
            'source',
            f'flow_effects.{state.counter_class}',
        )
        delta = self._path_value(record.semantics, source)
        if delta is not None:
            return self._resolve_delta(line_object, record, delta, state)

        unknown_policy = state.config.get('unknown_instructions', 'warn')
        message = (
            f'instruction "{record.source_mnemonic}" has no effect metadata '
            f'for flow counter class "{state.counter_class}"'
        )
        if unknown_policy == 'warn':
            self._diagnostic_reporter.warn(
                line_object.line_id,
                message,
                category='flow',
            )
        elif unknown_policy == 'error':
            self._error(line_object, message)
        return None

    def _apply_delta(
        self,
        line_object,
        record,
        state: _LinearCounterState,
    ) -> None:
        """Apply one selected instruction effect and update coordinate liveness."""
        if state.suspended:
            return
        delta = self._instruction_delta(line_object, record, state)
        if delta is None:
            return
        state.value += delta
        for coordinate in state.coordinates:
            if coordinate.is_valid:
                coordinate.is_valid = self._coordinate_is_live(state, coordinate)
        self._check_bounds(line_object, state)

    def _apply_instruction(self, line_object, record, expression_nodes) -> None:
        """Resolve operand uses, validate transfer metadata, and apply one delta."""
        self._resolve_expressions(line_object, expression_nodes)
        live_states = [
            state for state in self._active.values()
            if state.path_live
        ]
        if not live_states:
            return

        transfer = record.semantics.get('flow_transfer')
        if transfer is None:
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" is missing required flow_transfer metadata',
            )
            return
        terminals = record.semantics.get('flow_terminal', {})
        mapped_states = [
            state for state in live_states
            if isinstance(terminals, Mapping)
            and state.counter_class in terminals
        ]
        if mapped_states:
            if transfer != 'return':
                terminal_classes = ', '.join(sorted({
                    state.counter_class for state in mapped_states
                }))
                self._error(
                    line_object,
                    f'instruction "{record.source_mnemonic}" is a flow terminal for '
                    f'"{terminal_classes}", but its flow_transfer "{transfer}" '
                    'is not an unconditional return',
                )
                return
            for state in live_states:
                reconciliation_order = (
                    terminals.get(state.counter_class)
                    if isinstance(terminals, Mapping)
                    else None
                )
                if reconciliation_order is None:
                    self._apply_delta(line_object, record, state)
                    continue
                if state.suspended:
                    self._error(
                        line_object,
                        f'flow terminal "{record.source_mnemonic}" cannot reconcile '
                        f'suspended flow counter "{state.name}"',
                    )
                    continue
                if reconciliation_order == 'after_effect':
                    self._apply_delta(line_object, record, state)
                self._check_exit(line_object, state)
                state.path_live = False
            return

        if transfer != 'none':
            if len(live_states) == 1:
                end_action = (
                    f'end the region with #endtrack {live_states[0].name} '
                    'before this transfer'
                )
            else:
                end_directives = ', '.join(
                    f'#endtrack {state.name}' for state in live_states
                )
                end_action = (
                    f'end all active regions ({end_directives}) before this transfer'
                )
            corrective_action = (
                end_action
                if transfer in {'unconditional', 'call'}
                else 'path analysis is not yet available in M4'
            )
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" uses flow_transfer "{transfer}"; '
                f'{corrective_action}',
            )
            return
        for state in live_states:
            self._apply_delta(line_object, record, state)

    @staticmethod
    def _coordinate_is_live(
        state: _LinearCounterState,
        coordinate: CounterCoordinate,
    ) -> bool:
        """Return whether the current value has not crossed a named position."""
        zero_is_live = state.config.get('allow_zero_offset', True)
        offset_policy = state.config.get('coordinate_offsets', 'both')
        uses_positive_side = coordinate.declared_offset > 0 or (
            coordinate.declared_offset == 0 and offset_policy != 'negative'
        )
        if uses_positive_side:
            return (
                state.value >= coordinate.value
                if zero_is_live
                else state.value > coordinate.value
            )
        return (
            state.value <= coordinate.value
            if zero_is_live
            else state.value < coordinate.value
        )

    def _evaluate_directive_expression(
        self,
        line_object,
        expression: ExpressionNode,
        *,
        coordinate_state: _LinearCounterState | None = None,
    ) -> int | None:
        """Evaluate a directive expression after resolving its flow operands."""
        if expression is None:
            return None
        self._resolve_expressions(
            line_object,
            expression.deferred_flow_nodes(),
        )
        if expression.token_type in {TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM}:
            coordinate = self._lookup_coordinate(
                line_object,
                str(expression.value),
            )
            if coordinate is not None:
                if (
                    coordinate_state is None
                    or coordinate.counter_name != coordinate_state.name
                    or coordinate.counter_instance_id != coordinate_state.instance_id
                ):
                    self._error(
                        line_object,
                        f'counter coordinate "{expression.value}" does not belong '
                        f'to flow counter "{getattr(coordinate_state, "name", "")}"',
                    )
                    return None
                return coordinate.value
        try:
            return expression.get_value(
                line_object.symbol_scope,
                line_object.active_named_scopes,
                line_object.line_id,
            )
        except (
            ArithmeticError,
            FlowSymbolError,
            RuntimeError,
            SyntaxError,
            SystemExit,
            ValueError,
        ) as error:
            self._error(line_object, str(error))
            return None

    def _assert(self, line_object: AssertLine) -> None:
        """Evaluate either a general assertion or a flow-dependent checkpoint."""
        if not line_object.is_flow_dependent:
            line_object.enforce_general()
            return

        comparison = {
            '==': operator.eq,
            '!=': operator.ne,
            '<': operator.lt,
            '<=': operator.le,
            '>': operator.gt,
            '>=': operator.ge,
        }[line_object.comparison]

        if line_object.counter_name is not None:
            state = self._require_live_state(
                line_object,
                line_object.counter_name,
                '#assert',
            )
            if state is None:
                return
            if state.suspended:
                self._error(
                    line_object,
                    f'#assert cannot read suspended flow counter "{state.name}"',
                )
                return
            lhs_value = state.value
            rhs_value = self._evaluate_directive_expression(
                line_object,
                line_object.flow_rhs_expression,
            )
            if rhs_value is None:
                return
            if not comparison(lhs_value, rhs_value):
                line_object.report_flow_failure(
                    f'flow counter "{state.name}" assertion failed: '
                    f'expected {line_object.comparison} {rhs_value}, '
                    f'actual {lhs_value}',
                )
            return

        lhs_value = self._evaluate_directive_expression(
            line_object,
            line_object.flow_lhs_expression,
        )
        rhs_value = self._evaluate_directive_expression(
            line_object,
            line_object.flow_rhs_expression,
        )
        if lhs_value is None or rhs_value is None:
            return
        if not comparison(lhs_value, rhs_value):
            line_object.report_flow_failure(
                f'flow assertion failed: {line_object.condition_text}; '
                f'left side was {lhs_value}, right side was {rhs_value}',
            )

    def _set_counter(self, line_object: FlowSetLine) -> None:
        """Re-anchor one live scalar counter to a programmer-supplied value."""
        state = self._require_live_state(
            line_object,
            line_object.counter_name,
            '#set',
        )
        if state is None:
            return
        if state.suspended:
            self._error(
                line_object,
                f'flow counter "{state.name}" is suspended; use #resume to '
                'restore a known value',
            )
            return
        value = self._evaluate_directive_expression(
            line_object,
            line_object.value_expression,
        )
        if value is None:
            return
        state.value = value
        for coordinate in state.coordinates:
            if coordinate.is_valid:
                coordinate.is_valid = self._coordinate_is_live(state, coordinate)
        self._check_bounds(line_object, state)

    def _suspend_counter(self, line_object: FlowSuspendLine) -> None:
        """Put one live scalar counter into an explicit indeterminate state."""
        state = self._require_live_state(
            line_object,
            line_object.counter_name,
            '#suspend',
        )
        if state is None:
            return
        if state.suspended:
            self._error(
                line_object,
                f'flow counter "{state.name}" is already suspended',
            )
            return
        state.suspended = True

    def _resume_counter(self, line_object: FlowResumeLine) -> None:
        """Restore a suspended scalar counter and invalidate its old slots."""
        state = self._require_live_state(
            line_object,
            line_object.counter_name,
            '#resume',
        )
        if state is None:
            return
        if not state.suspended:
            self._error(
                line_object,
                f'flow counter "{state.name}" is not suspended',
            )
            return
        value = self._evaluate_directive_expression(
            line_object,
            line_object.value_expression,
            coordinate_state=state,
        )
        if value is None:
            return
        state.value = value
        state.suspended = False
        for coordinate in state.coordinates:
            coordinate.is_valid = False
        self._check_bounds(line_object, state)

    def run(self, line_objects) -> None:
        """Analyze compiled line objects once in physical source order."""
        last_line = None
        for line_object in line_objects:
            last_line = line_object
            if isinstance(line_object, FlowTrackLine):
                self._open(line_object)
                continue
            if isinstance(line_object, FlowEndTrackLine):
                self._close(line_object)
                continue
            if isinstance(line_object, AssertLine):
                self._assert(line_object)
                continue
            if isinstance(line_object, FlowSetLine):
                self._set_counter(line_object)
                continue
            if isinstance(line_object, FlowSuspendLine):
                self._suspend_counter(line_object)
                continue
            if isinstance(line_object, FlowResumeLine):
                self._resume_counter(line_object)
                continue
            if isinstance(line_object, CounterCoordinateLine):
                self._declare_coordinate(line_object)
                continue
            if isinstance(line_object, InstructionLine):
                for record, expression_nodes in line_object.analysis_units:
                    self._apply_instruction(line_object, record, expression_nodes)
                continue
            if line_object.flow_expression_nodes:
                self._resolve_expressions(line_object, line_object.flow_expression_nodes)

        for state in self._active.values():
            if state.path_live:
                self._error(
                    last_line or state.opened_by,
                    f'flow counter "{state.name}" reaches EOF without '
                    'a flow terminal or #endtrack',
                )
