import operator
import re
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

from bespokeasm.assembler.analysis import OperandSemanticKind
from bespokeasm.assembler.control_flow import ControlFlowGraph
from bespokeasm.assembler.control_flow import ControlFlowNode
from bespokeasm.assembler.control_flow import declared_coordinate_labels
from bespokeasm.assembler.control_flow import references_declared_coordinate
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.counter_coordinate_line import CounterCoordinateLine
from bespokeasm.assembler.line_object.directive_line.memzone import SetMemoryZoneLine
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line.assert_line import AssertLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowEndTrackLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowEntryLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowResumeLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowSetLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowSuspendLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowTrackLine
from bespokeasm.assembler.symbol_scope import SymbolScopeType
from bespokeasm.assembler.symbol_scope.flow_symbols import CounterCoordinate
from bespokeasm.assembler.symbol_scope.flow_symbols import FlowSymbolError
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import parse_expression
from bespokeasm.expression import TokenType
from bespokeasm.utilities import is_unprefixed_numeric_string


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
    # Effective bounds are computed once at ``#track``: the more restrictive
    # of the class's declared ``min_value``/``max_value`` and the instance's
    # ``min=``/``max=`` parameters (tighten-only). Every bounds check reads
    # these, so instance bounds are enforced everywhere class bounds are.
    effective_min: int | None = None
    effective_max: int | None = None
    coordinates: list[CounterCoordinate] = field(default_factory=list)
    invalid_coordinate_ids: set[int] = field(default_factory=set)
    path_live: bool = True
    suspended: bool = False
    # When indeterminacy was caused by anchor invalidation rather than an
    # explicit ``#suspend``, this names the cause (watched write or direct
    # ``flow_invalidates`` instruction, with its source line) so downstream
    # diagnostics can identify it. ``None`` means explicitly suspended or
    # not indeterminate at all. Cleared by a successful re-anchor.
    invalidated_since: str | None = None
    region_id: int | None = None
    branch_provenance: dict[int, tuple[object, str]] = field(
        default_factory=dict,
    )


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
                    | FlowEntryLine
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

    @staticmethod
    def source_requires_flow_values(line_objects) -> bool:
        """Return whether emitted words depend on resolved flow expressions.

        Bare coordinate references are ordinary labels until scope lookup, so
        they count only when their spelling matches a ``:=`` declaration
        somewhere in the compiled source.
        """
        declared_labels = declared_coordinate_labels(line_objects)
        return any(
            isinstance(line_object, LineWithWords)
            and (
                bool(line_object.flow_expression_nodes)
                or references_declared_coordinate(line_object, declared_labels)
            )
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
        if not self._model.flow_checks_enabled:
            return
        minimum = state.effective_min
        maximum = state.effective_max
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
        if (
            self._model.flow_checks_enabled
            and not self._model.flow_counter_has_effect_metadata(
                line_object.counter_class,
            )
        ):
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

        if self._model.flow_checks_enabled:
            effective_bounds = self._effective_bounds(
                line_object,
                counter_config,
            )
            if effective_bounds is None:
                return
            effective_min, effective_max = effective_bounds
        else:
            effective_min, effective_max = None, None

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
            effective_min=effective_min,
            effective_max=effective_max,
        )
        self._active[counter_name] = state
        self._next_instance_id += 1
        self._check_bounds(line_object, state)

    def _effective_bounds(
        self,
        line_object: FlowTrackLine,
        counter_config: dict,
    ) -> tuple[int | None, int | None] | None:
        """Merge class bounds with ``#track`` instance bounds (tighten-only).

        Instance bounds exist because on RAM-stack machines the depth limit is
        a property of the program's memory map, not the ISA. They may only
        tighten the class's declared bounds — a program must not claim more
        than the hardware provides — so an instance bound looser than a
        declared class bound is an error on the ``#track`` line and ``None``
        is returned for the guard-and-return convention.
        """
        class_min = counter_config.get('min_value')
        class_max = counter_config.get('max_value')
        instance_min = line_object.evaluate_parameter('min')
        instance_max = line_object.evaluate_parameter('max')
        if (
            instance_min is not None
            and class_min is not None
            and instance_min < class_min
        ):
            self._error(
                line_object,
                f'flow counter instance bound min={instance_min} is looser '
                f'than the class minimum {class_min}; instance bounds may '
                'only tighten class bounds',
            )
            return None
        if (
            instance_max is not None
            and class_max is not None
            and instance_max > class_max
        ):
            self._error(
                line_object,
                f'flow counter instance bound max={instance_max} is looser '
                f'than the class maximum {class_max}; instance bounds may '
                'only tighten class bounds',
            )
            return None
        minimums = [bound for bound in (class_min, instance_min) if bound is not None]
        maximums = [bound for bound in (class_max, instance_max) if bound is not None]
        effective_min = max(minimums) if minimums else None
        effective_max = min(maximums) if maximums else None
        if (
            effective_min is not None
            and effective_max is not None
            and effective_min > effective_max
        ):
            self._error(
                line_object,
                f'flow counter instance bounds are contradictory: '
                f'effective minimum {effective_min} exceeds effective maximum '
                f'{effective_max}',
            )
            return None
        return effective_min, effective_max

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
            if (
                self._model.flow_checks_enabled
                and line_object.evaluate_parameter('exit') is not None
            ):
                self._error(
                    line_object,
                    f'#endtrack {state.name} cannot check exit= while the '
                    'counter is suspended',
                )
                return
            if (
                self._model.flow_checks_enabled
                and state.invalidated_since is not None
                and state.expected_exit is not None
            ):
                # Closing over an explicit #suspend is a deliberate
                # programmer acknowledgement and stays silent. Indeterminacy
                # caused by anchor invalidation was never acknowledged, so
                # the skipped exit contract is surfaced with its provenance.
                self._diagnostic_reporter.warn(
                    line_object.line_id,
                    f'exit contract not checked: flow counter "{state.name}" '
                    f'indeterminate since {state.invalidated_since}',
                    category='flow',
                )
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
        if not self._model.flow_checks_enabled:
            return
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

    def _resolve_coordinate_reference(self, line_object, node: ExpressionNode) -> None:
        """Resolve one bare coordinate reference at the pre-line state.

        The node is an ordinary label leaf; a name that does not resolve to a
        declared coordinate is silently left for ordinary symbol resolution.
        """
        label = str(node.value)
        coordinate = self._lookup_coordinate(line_object, label)
        if coordinate is None:
            return
        state = self._active.get(coordinate.counter_name)
        if state is None:
            self._coordinate_reference_error(
                line_object,
                node,
                f'counter coordinate "{label}" references inactive flow counter '
                f'"{coordinate.counter_name}"',
            )
            return
        if not state.path_live:
            self._coordinate_reference_error(
                line_object,
                node,
                f'counter coordinate "{label}" is unreachable after the flow '
                'counter path terminated',
            )
            return
        if state.suspended:
            self._coordinate_reference_error(
                line_object,
                node,
                f'counter coordinate "{label}" cannot be resolved while flow '
                f'counter "{state.name}" is {self._indeterminate_tail(state)}',
            )
            return
        if coordinate.counter_instance_id != state.instance_id:
            self._coordinate_reference_error(
                line_object,
                node,
                f'counter coordinate "{label}" belongs to an earlier tracking '
                f'instance of counter "{coordinate.counter_name}"',
            )
            return
        if id(coordinate) in state.invalid_coordinate_ids:
            self._coordinate_reference_error(
                line_object,
                node,
                f'counter coordinate "{label}" is invalid because its saved position '
                'was crossed and is no longer live',
            )
            return
        if not isinstance(state.value, int):
            self._coordinate_reference_error(
                line_object,
                node,
                f'counter coordinate "{label}" cannot be resolved after call to '
                f'"{state.value.callee}" because no caller-visible summary is '
                f'declared for "{state.counter_class}"',
            )
            return
        resolved_offset = state.value - coordinate.value
        node.resolve_flow_value(resolved_offset)
        line_object.record_flow_observation(label, resolved_offset)

    def _coordinate_reference_error(
        self,
        line_object,
        node: ExpressionNode,
        message: str,
    ) -> None:
        """Report one coordinate-reference failure; graph analysis dedups."""
        self._error(line_object, message)

    def _resolve_expressions(self, line_object, nodes: tuple[ExpressionNode, ...]) -> None:
        """Deposit the active pre-instruction value into deferred expressions."""
        for node in nodes:
            if node.token_type == TokenType.T_LABEL:
                self._resolve_coordinate_reference(line_object, node)
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
                    f'"{counter_name}" is {self._indeterminate_tail(state)}',
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
                f'while the counter is {self._indeterminate_tail(state)}',
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
        line_object.record_flow_observation(
            line_object.label,
            declared_offset,
        )

    @classmethod
    def _expression_labels(cls, node: ExpressionNode) -> set[str]:
        """Collect scalar symbol tokens while excluding flow-function arguments."""
        if node.token_type == TokenType.T_COUNTER:
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
                'depend on COUNTER()',
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

    @staticmethod
    def _write_target_values(line_object, record) -> tuple[int | None, ...]:
        """Resolve configured memory-write operands conservatively.

        A concrete integer is returned for a compile-time target. ``None``
        means the target is runtime-valued or otherwise cannot be proven, so
        it may alias any address watched by an active counter.
        """
        targets = []
        for index in record.semantics.get('flow_write_operands', ()):
            if index < 0 or index >= len(record.operands):
                # Config-load validation normally makes this unreachable. Keep
                # analysis guarded for a future accumulating reporter.
                targets.append(None)
                continue
            operand = record.operands[index]
            if (
                operand.semantic_kind
                is not OperandSemanticKind.COMPILE_TIME_EXPRESSION
                or operand.expression is None
                or operand.expression.contains_flow_value()
            ):
                targets.append(None)
                continue
            try:
                targets.append(
                    operand.expression.to_node().get_value(
                        line_object.symbol_scope,
                        line_object.active_named_scopes,
                        line_object.line_id,
                    )
                )
            except (
                ArithmeticError,
                RuntimeError,
                SyntaxError,
                SystemExit,
                ValueError,
            ):
                targets.append(None)
        return tuple(targets)

    @staticmethod
    def _indeterminate_tail(state: _LinearCounterState) -> str:
        """Describe why a counter has no value, naming invalidation causes.

        Explicit ``#suspend`` keeps its established one-word description;
        an invalidation-caused indeterminacy identifies the invalidating
        write or instruction and points at the required ``#resume``.
        """
        if state.invalidated_since is None:
            return 'suspended'
        return (
            f'indeterminate since {state.invalidated_since}; '
            '#resume with a known value is required'
        )

    def _suspended_terminal_message(
        self,
        record,
        state: _LinearCounterState,
    ) -> str:
        """Explain why a terminal cannot reconcile one indeterminate counter."""
        if state.invalidated_since is None:
            return (
                f'flow terminal "{record.source_mnemonic}" cannot reconcile '
                f'suspended flow counter "{state.name}"'
            )
        return (
            f'flow terminal "{record.source_mnemonic}" cannot reconcile '
            f'flow counter "{state.name}": {self._indeterminate_tail(state)}'
        )

    @staticmethod
    def _invalidate_state(state: _LinearCounterState, provenance: str) -> None:
        """Make one counter indeterminate and invalidate all its coordinates.

        An already-indeterminate counter — explicitly suspended or hit by an
        earlier invalidation — is deliberately not early-returned: the
        coordinates alive at this invalidation must still be permanently
        invalidated (a future slot-preservation contract on ``#resume`` must
        never resurrect them), and the provenance must be recorded. The
        first invalidation's provenance is retained.
        """
        if state.invalidated_since is None:
            state.invalidated_since = provenance
        state.suspended = True
        for coordinate in state.coordinates:
            state.invalid_coordinate_ids.add(id(coordinate))
            coordinate.is_valid = False

    def _apply_instruction_invalidations(self, line_object, record) -> None:
        """Apply direct and watched-write invalidation metadata.

        ``flow_invalidates`` unconditionally invalidates every active instance
        of the named classes. ``flow_write_operands`` works with each class's
        ``invalidate_on_write`` addresses and invalidates only a possible
        matching write. Both forms use the same indeterminate state as
        ``#suspend``, additionally recording the invalidation provenance;
        ``#resume`` is the explicit re-anchoring operation.
        """
        invalidated_classes = record.semantics.get('flow_invalidates', ())
        for state in self._active.values():
            if state.counter_class in invalidated_classes:
                self._invalidate_state(
                    state,
                    f'instruction "{record.source_mnemonic}" '
                    f'at {line_object.line_id}',
                )

        targets = self._write_target_values(line_object, record)
        if not targets:
            return
        for state in self._active.values():
            watched_addresses = state.config.get('invalidate_on_write', ())
            if (
                not watched_addresses
                or not any(
                    target is None or target in watched_addresses
                    for target in targets
                )
            ):
                continue
            matched_address = next(
                (
                    target
                    for target in targets
                    if target is not None and target in watched_addresses
                ),
                # A runtime target conservatively aliases every watched
                # address; the class's first declared address names the
                # anchor in that case.
                watched_addresses[0],
            )
            self._invalidate_state(
                state,
                f'the write to {matched_address:#x} at {line_object.line_id}',
            )

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
        if (
            unknown_policy == 'warn'
            and self._model.flow_checks_enabled
        ):
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
            if (
                id(coordinate) not in state.invalid_coordinate_ids
                and not self._coordinate_is_live(state, coordinate)
            ):
                state.invalid_coordinate_ids.add(id(coordinate))
                coordinate.is_valid = False
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
        self._apply_instruction_invalidations(line_object, record)
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
                    # A live counter not mapped on this terminal has no way
                    # across a return: there is no fall-through successor, so
                    # its region has no reachable end — the same rule as a
                    # bare return with no terminal at all. The path is closed
                    # so following lines are uniformly unreachable.
                    self._error(
                        line_object,
                        f'instruction "{record.source_mnemonic}" returns while '
                        f'flow counter "{state.name}" is still active; end the '
                        f'region with #endtrack {state.name} before this transfer',
                    )
                    state.path_live = False
                    continue
                if state.suspended:
                    self._error(
                        line_object,
                        self._suspended_terminal_message(record, state),
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
        """Evaluate a directive expression after resolving its flow operands.

        With ``coordinate_state`` set (the ``#resume`` anchor form), a
        top-level coordinate symbol evaluates to its saved counter position;
        everywhere else a bare coordinate reference evaluates to its current
        offset, exactly like an instruction operand.
        """
        if expression is None:
            return None
        if (
            coordinate_state is not None
            and expression.token_type in {TokenType.T_LABEL, TokenType.T_LABEL_OR_NUM}
        ):
            coordinate = self._lookup_coordinate(
                line_object,
                str(expression.value),
            )
            if coordinate is not None:
                if (
                    coordinate.counter_name != coordinate_state.name
                    or coordinate.counter_instance_id != coordinate_state.instance_id
                ):
                    self._error(
                        line_object,
                        f'counter coordinate "{expression.value}" does not belong '
                        f'to flow counter "{coordinate_state.name}"',
                    )
                    return None
                if (
                    self._model.flow_checks_enabled
                    and id(coordinate)
                    in coordinate_state.invalid_coordinate_ids
                ):
                    # Re-anchoring to a coordinate the analysis already proved
                    # crossed is accepted on faith, but deserves a warning.
                    self._diagnostic_reporter.warn(
                        line_object.line_id,
                        f'counter coordinate "{expression.value}" was invalidated '
                        'before this directive; re-anchoring to its saved '
                        'position is taken on faith',
                        category='flow',
                    )
                return coordinate.value
        self._resolve_expressions(
            line_object,
            expression.deferred_flow_nodes()
            + expression.coordinate_candidate_nodes(),
        )
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
        """Evaluate a flow-dependent checkpoint against the current state.

        General assertions were already enforced once at parse time by the
        ``AssertLine`` constructor (which is also what keeps them active under
        ``--no-flow-checks``); re-enforcing them here would double-report
        under an accumulate-and-continue reporter.
        """
        if (
            not self._model.flow_checks_enabled
            or not line_object.is_flow_dependent
        ):
            return

        comparison = {
            '==': operator.eq,
            '!=': operator.ne,
            '<': operator.lt,
            '<=': operator.le,
            '>': operator.gt,
            '>=': operator.ge,
        }[line_object.comparison]

        if (
            line_object.counter_name is not None
            and line_object.counter_name not in self._active
            and self._lookup_coordinate(
                line_object,
                line_object.counter_name,
            ) is not None
        ):
            # The bare-name shorthand resolved to a counter coordinate, not a
            # counter instance: fall through to generic expression evaluation,
            # which compares the coordinate's current offset.
            pass
        elif line_object.counter_name is not None:
            state = self._require_live_state(
                line_object,
                line_object.counter_name,
                '#assert',
            )
            if state is None:
                return
            if state.suspended:
                message = (
                    f'#assert cannot read suspended flow counter "{state.name}"'
                    if state.invalidated_since is None
                    else (
                        f'#assert cannot read flow counter "{state.name}": '
                        f'{self._indeterminate_tail(state)}'
                    )
                )
                self._error(line_object, message)
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
            message = (
                f'flow counter "{state.name}" is suspended; use #resume to '
                'restore a known value'
                if state.invalidated_since is None
                else (
                    f'flow counter "{state.name}" is '
                    f'{self._indeterminate_tail(state)}'
                )
            )
            self._error(line_object, message)
            return
        value = self._evaluate_directive_expression(
            line_object,
            line_object.value_expression,
        )
        if value is None:
            return
        state.value = value
        # A re-anchor means the effect model could not express what happened
        # to the counter, so no prior slot's survival is provable: #set
        # permanently invalidates every coordinate, exactly like #resume.
        for coordinate in state.coordinates:
            state.invalid_coordinate_ids.add(id(coordinate))
            coordinate.is_valid = False
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
            message = (
                f'flow counter "{state.name}" is already suspended'
                if state.invalidated_since is None
                else (
                    f'flow counter "{state.name}" is already indeterminate '
                    f'since {state.invalidated_since}'
                )
            )
            self._error(line_object, message)
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
        # The explicit re-anchor resolves the indeterminacy, so a later
        # diagnostic must not cite this (cured) invalidation as its cause.
        state.invalidated_since = None
        for coordinate in state.coordinates:
            state.invalid_coordinate_ids.add(id(coordinate))
            coordinate.is_valid = False
        self._check_bounds(line_object, state)

    def _flow_values(self) -> dict[str, object]:
        """Return the live scalar values used by listing annotations."""
        return {
            state.name: '?' if state.suspended else state.value
            for state in self._active.values()
            if state.path_live
        }

    def _warn_external_label(self, line_object: LabelLine) -> None:
        """Warn when a non-local label exposes a non-entry tracked state."""
        if not self._model.flow_checks_enabled:
            return
        label = line_object.get_label()
        if label.startswith('.'):
            return
        for state in self._active.values():
            if not state.path_live:
                self._diagnostic_reporter.warn(
                    line_object.line_id,
                    f'label "{label}" is an unreachable potential entry '
                    f'inside flow counter region "{state.name}"; add '
                    f'#entry {state.name} value=<expression> or a lexical '
                    f'#endtrack {state.name}',
                    category='flow',
                )
            elif (
                state.suspended
                or state.value != state.initial_value
            ):
                self._diagnostic_reporter.warn(
                    line_object.line_id,
                    f'label "{label}" is a potential external entry where '
                    f'flow counter "{state.name}" has value '
                    f'{"suspended" if state.suspended else state.value}, not '
                    f'entry value {state.initial_value}; add '
                    f'#entry {state.name}',
                    category='flow',
                )

    def run(self, line_objects) -> None:
        """Analyze compiled line objects once in physical source order."""
        last_line = None
        for line_object in line_objects:
            last_line = line_object
            before = self._flow_values()
            if isinstance(line_object, FlowTrackLine):
                self._open(line_object)
            elif isinstance(line_object, FlowEndTrackLine):
                self._close(line_object)
            elif isinstance(line_object, AssertLine):
                self._assert(line_object)
            elif isinstance(line_object, FlowSetLine):
                self._set_counter(line_object)
            elif isinstance(line_object, FlowSuspendLine):
                self._suspend_counter(line_object)
            elif isinstance(line_object, FlowResumeLine):
                self._resume_counter(line_object)
            elif isinstance(line_object, CounterCoordinateLine):
                self._declare_coordinate(line_object)
            elif (
                isinstance(line_object, LabelLine)
                and not line_object.is_constant
            ):
                self._warn_external_label(line_object)
            elif isinstance(line_object, InstructionLine):
                for record, expression_nodes in line_object.analysis_units:
                    self._apply_instruction(line_object, record, expression_nodes)
            elif (
                line_object.flow_expression_nodes
                or line_object.flow_candidate_nodes
            ):
                self._resolve_expressions(
                    line_object,
                    line_object.flow_expression_nodes
                    + line_object.flow_candidate_nodes,
                )
            if self._model.flow_checks_enabled:
                line_object.record_flow_transition(
                    before,
                    self._flow_values(),
                )

        for state in self._active.values():
            if state.path_live:
                if self._model.flow_checks_enabled:
                    self._error(
                        last_line or state.opened_by,
                        f'flow counter "{state.name}" reaches EOF without '
                        'a flow terminal or #endtrack',
                    )


@dataclass(frozen=True)
class _UnresolvedCall:
    callee: str
    counter_class: str

    def __str__(self) -> str:
        return f'?call({self.callee})'


@dataclass
class _GraphInput:
    states: dict[str, _LinearCounterState]
    sources: dict[str, object]


@dataclass
class _LexicalRegion:
    region_id: int
    name: str
    counter_class: str
    track_index: int
    end_index: int | None
    track_line: FlowTrackLine


class FlowGraphAnalyzer(FlowLinearAnalyzer):
    """Address-based M5 CFG analyzer for scalar ``require-equal`` counters."""

    def __init__(self, model, diagnostic_reporter) -> None:
        super().__init__(model, diagnostic_reporter)
        self._graph = None
        self._line_objects = ()
        self._inputs: dict[int, _GraphInput] = {}
        self._queue = deque()
        self._memberships: list[dict[str, _LexicalRegion]] = []
        self._regions: dict[int, _LexicalRegion] = {}
        self._region_by_track_index: dict[int, _LexicalRegion] = {}
        self._templates: dict[int, _LinearCounterState] = {}
        self._entries_by_label: dict[int, tuple[FlowEntryLine, ...]] = {}
        self._entry_lines: set[int] = set()
        self._coordinates_by_line: dict[int, CounterCoordinate] = {}
        self._coordinate_line_index: dict[int, int] = {}
        self._reported_expression_errors: set[tuple[int, str]] = set()

    def _expression_error_once(
        self,
        line_object,
        expression: ExpressionNode,
        message: str,
    ) -> None:
        """Report one expression failure once across worklist revisits."""
        diagnostic_key = (id(expression), message)
        if diagnostic_key in self._reported_expression_errors:
            return
        self._reported_expression_errors.add(diagnostic_key)
        self._error(line_object, message)

    def _coordinate_reference_error(
        self,
        line_object,
        node: ExpressionNode,
        message: str,
    ) -> None:
        """Report a coordinate failure once across worklist revisits."""
        self._expression_error_once(line_object, node, message)

    @staticmethod
    def _clone_state(state: _LinearCounterState) -> _LinearCounterState:
        return replace(
            state,
            coordinates=list(state.coordinates),
            invalid_coordinate_ids=set(state.invalid_coordinate_ids),
            branch_provenance=dict(state.branch_provenance),
        )

    @classmethod
    def _clone_states(
        cls,
        states: dict[str, _LinearCounterState],
    ) -> dict[str, _LinearCounterState]:
        return {
            name: cls._clone_state(state)
            for name, state in states.items()
        }

    def _prepare_regions(self) -> None:
        """Index lexical counter membership at every compiled source line."""
        active: dict[str, _LexicalRegion] = {}
        for line_index, line_object in enumerate(self._line_objects):
            if isinstance(line_object, FlowTrackLine):
                if line_object.counter_name in active:
                    prior = active[line_object.counter_name]
                    terminal_seen = any(
                        isinstance(candidate, InstructionLine)
                        and any(
                            record.semantics.get('flow_transfer') == 'return'
                            for record, _ in candidate.analysis_units
                        )
                        for candidate in self._line_objects[
                            prior.track_index + 1:line_index
                        ]
                    )
                    guidance = (
                        'the prior region is still lexically open after its '
                        f'terminal; add a lexical #endtrack {prior.name} '
                        'before opening another counter'
                        if terminal_seen
                        else f'insert #endtrack {prior.name} before opening '
                        'another counter'
                    )
                    self._error(
                        line_object,
                        f'flow counter "{line_object.counter_name}" is still '
                        f'active; {guidance}',
                    )
                    self._memberships.append(dict(active))
                    continue
                region = _LexicalRegion(
                    region_id=len(self._regions),
                    name=line_object.counter_name,
                    counter_class=line_object.counter_class,
                    track_index=line_index,
                    end_index=None,
                    track_line=line_object,
                )
                self._regions[region.region_id] = region
                self._region_by_track_index[line_index] = region
                active[region.name] = region
                self._memberships.append(dict(active))
                continue

            self._memberships.append(dict(active))
            if isinstance(line_object, FlowEndTrackLine):
                region = active.get(line_object.counter_name)
                if region is None:
                    self._error(
                        line_object,
                        f'#endtrack {line_object.counter_name} has no active counter',
                    )
                    continue
                region.end_index = line_index
                del active[line_object.counter_name]
            elif isinstance(line_object, SetMemoryZoneLine):
                for region in active.values():
                    region.end_index = line_index
                active.clear()

        final_index = max(len(self._line_objects) - 1, 0)
        for region in active.values():
            region.end_index = final_index

    def _validate_coordinate_scopes(self) -> None:
        """Reject coordinate names that cannot exist in their lexical scope.

        This validation is independent of reachability. In particular, a
        relocation resets the ordinary local-label scope before it also
        auto-closes flow regions, so the established symbol-scope diagnostic
        must not be hidden by a later control-flow boundary diagnostic.
        """
        reset_by_layout_boundary = False
        for line_object in self._line_objects:
            if isinstance(line_object, SetMemoryZoneLine):
                reset_by_layout_boundary = True
                continue
            if (
                isinstance(line_object, LabelLine)
                and not line_object.is_constant
                and not line_object.get_label().startswith('.')
            ):
                reset_by_layout_boundary = False
                continue
            if not isinstance(line_object, CounterCoordinateLine):
                continue
            requested_scope = SymbolScopeType.get_symbol_scope(
                line_object.label,
            )
            if (
                not reset_by_layout_boundary
                or requested_scope.value <= line_object.symbol_scope.type.value
            ):
                continue
            self._error(
                line_object,
                f"coordinate '{line_object.label}' is too low of scope for "
                'available scopes at this line',
            )

    def _prepare_entries(self) -> None:
        """Validate grouped ``#entry`` declarations and attach their labels."""
        index = 0
        while index < len(self._line_objects):
            if not isinstance(self._line_objects[index], FlowEntryLine):
                index += 1
                continue
            group_start = index
            entries = []
            while index < len(self._line_objects):
                candidate = self._line_objects[index]
                if isinstance(candidate, FlowEntryLine):
                    entries.append(candidate)
                    self._entry_lines.add(index)
                    index += 1
                    continue
                if type(candidate) is LineObject:
                    index += 1
                    continue
                break
            if (
                index >= len(self._line_objects)
                or not isinstance(self._line_objects[index], LabelLine)
                or self._line_objects[index].is_constant
            ):
                self._error(
                    self._line_objects[group_start],
                    '#entry must be followed by the next compilable address label',
                )
                return
            seen = set()
            for entry in entries:
                if entry.counter_name in seen:
                    self._error(
                        entry,
                        f'duplicate #entry declaration for flow counter '
                        f'"{entry.counter_name}"',
                    )
                    return
                seen.add(entry.counter_name)
                region = self._memberships[index].get(entry.counter_name)
                if region is None:
                    self._error(
                        entry,
                        f'#entry references inactive flow counter '
                        f'"{entry.counter_name}"',
                    )
                    return
            self._entries_by_label[index] = tuple(entries)

    def _node_for_line(self, line_index: int) -> ControlFlowNode:
        """Return the structural node anchored to one significant source line."""
        node = next(
            (
                node
                for node in self._graph.nodes
                if node.line_index == line_index
            ),
            None,
        )
        if node is None:
            raise RuntimeError(
                f'no control-flow node exists for source line index {line_index}'
            )
        return node

    @staticmethod
    def _graph_flow_values(
        states: dict[str, _LinearCounterState],
    ) -> dict[str, object]:
        """Return display values for one graph input or output state."""
        return {
            name: (
                '?'
                if state.suspended
                else state.value
            )
            for name, state in states.items()
        }

    def _state_description(self, state: _LinearCounterState) -> str:
        """Render a scalar or suspended state for a path diagnostic."""
        if state.suspended:
            return 'suspended'
        return str(state.value)

    def _merge_state(
        self,
        node: ControlFlowNode,
        existing: _LinearCounterState,
        incoming: _LinearCounterState,
        existing_source,
        incoming_source,
    ) -> tuple[_LinearCounterState, bool]:
        """Require equal scalar inputs and conservatively merge slot liveness."""
        if (
            existing.suspended != incoming.suspended
            or (
                not existing.suspended
                and existing.value != incoming.value
            )
        ):
            self._error(
                node.line_object,
                f'flow counter "{existing.name}" join mismatch: '
                f'{self._state_description(existing)} from '
                f'{existing_source.line_id} versus '
                f'{self._state_description(incoming)} from '
                f'{incoming_source.line_id}',
            )

        merged = self._clone_state(existing)
        existing_coordinates = {
            id(coordinate): coordinate
            for coordinate in existing.coordinates
        }
        incoming_coordinates = {
            id(coordinate): coordinate
            for coordinate in incoming.coordinates
        }
        merged.coordinates = list({
            **existing_coordinates,
            **incoming_coordinates,
        }.values())
        merged_invalid = (
            existing.invalid_coordinate_ids
            | incoming.invalid_coordinate_ids
            | (existing_coordinates.keys() ^ incoming_coordinates.keys())
        )
        merged_provenance = {
            branch_id: provenance
            for branch_id, provenance in existing.branch_provenance.items()
            if incoming.branch_provenance.get(branch_id) == provenance
        }
        # Two invalidated paths may carry different invalidation provenance
        # (e.g. one watched write per branch); the join keeps one of them
        # deterministically — the lexicographically first — independent of
        # worklist arrival order.
        invalidation_candidates = [
            provenance
            for provenance in (
                existing.invalidated_since,
                incoming.invalidated_since,
            )
            if provenance is not None
        ]
        merged_invalidated_since = (
            min(invalidation_candidates) if invalidation_candidates else None
        )
        changed = (
            merged_invalid != existing.invalid_coordinate_ids
            or merged_provenance != existing.branch_provenance
            or merged_invalidated_since != existing.invalidated_since
        )
        merged.invalid_coordinate_ids = set(merged_invalid)
        merged.branch_provenance = merged_provenance
        merged.invalidated_since = merged_invalidated_since
        return merged, changed

    def _validate_boundary(
        self,
        source: ControlFlowNode | None,
        target: ControlFlowNode,
        states: dict[str, _LinearCounterState],
    ) -> bool:
        """Reject an edge that enters or leaves a lexical tracking region."""
        target_regions = self._memberships[target.line_index]
        for state in states.values():
            region = target_regions.get(state.name)
            if (
                region is not None
                and target.line_index == region.track_index
                and state.region_id == region.region_id
            ):
                self._error(
                    source.line_object if source is not None else target.line_object,
                    f'control flow reaches #track {region.counter_class} while '
                    f'flow counter "{state.name}" is already active; end the '
                    f'region with #endtrack {state.name} before this transfer',
                )
                return False
            if region is None or region.region_id != state.region_id:
                transfer = (
                    source.record.semantics.get('flow_transfer')
                    if source is not None and source.record is not None
                    else None
                )
                guidance = (
                    f'; end the region with #endtrack {state.name} before '
                    'this transfer'
                    if transfer in {'unconditional', 'call'}
                    else ''
                )
                self._error(
                    source.line_object if source is not None else target.line_object,
                    f'control flow leaves flow counter region "{state.name}" '
                    f'before its terminal or #endtrack{guidance}',
                )
                return False
        for name, region in target_regions.items():
            if name in states:
                continue
            if target.line_index == region.track_index:
                continue
            self._error(
                source.line_object if source is not None else target.line_object,
                f'control flow enters flow counter region "{name}" after '
                f'#track {region.counter_class}',
            )
            return False
        return True

    def _enqueue(
        self,
        node: ControlFlowNode,
        states: dict[str, _LinearCounterState],
        sources: dict[str, object],
        *,
        source_node: ControlFlowNode | None = None,
    ) -> None:
        """Merge an incoming state at a node and schedule changed work."""
        if node is None:
            return
        if not self._validate_boundary(source_node, node, states):
            return
        incoming_states = self._clone_states(states)
        existing = self._inputs.get(node.node_id)
        if existing is None:
            self._inputs[node.node_id] = _GraphInput(
                incoming_states,
                dict(sources),
            )
            self._queue.append(node.node_id)
            return
        if existing.states.keys() != incoming_states.keys():
            self._error(
                node.line_object,
                'control-flow paths cross a flow-counter region boundary',
            )
            return
        changed = False
        merged_states = {}
        for name, current in existing.states.items():
            merged, state_changed = self._merge_state(
                node,
                current,
                incoming_states[name],
                existing.sources[name],
                sources[name],
            )
            merged_states[name] = merged
            changed = changed or state_changed
        if changed:
            existing.states = merged_states
            self._queue.append(node.node_id)

    def _resolve_expressions(
        self,
        line_object,
        nodes: tuple[ExpressionNode, ...],
    ) -> None:
        """Resolve deferred flow operands against one graph input state."""
        for node in nodes:
            if node.token_type == TokenType.T_LABEL:
                self._resolve_coordinate_reference(line_object, node)
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
                    f'COUNTER({counter_name}) cannot be resolved while flow '
                    f'counter "{counter_name}" is '
                    f'{self._indeterminate_tail(state)}',
                )
                continue
            if not isinstance(state.value, int):
                self._error(
                    line_object,
                    f'COUNTER({counter_name}) cannot be resolved after call to '
                    f'"{state.value.callee}" because no caller-visible summary '
                    f'is declared for "{state.counter_class}"',
                )
                continue
            node.resolve_flow_value(state.value)

    def _assert(self, line_object: AssertLine) -> None:
        """Reject bare-counter assertions whose call effect is unresolved."""
        if not self._model.flow_checks_enabled:
            return
        if line_object.counter_name is not None:
            state = self._active.get(line_object.counter_name)
            if state is not None and not isinstance(state.value, int):
                self._error(
                    line_object,
                    f'#assert cannot resolve flow counter "{state.name}" after '
                    f'call to "{state.value.callee}" because no caller-visible '
                    f'summary is declared for "{state.counter_class}"',
                )
                return
        super()._assert(line_object)

    def _check_exit(
        self,
        line_object,
        state: _LinearCounterState,
        expected: int | None = None,
    ) -> None:
        """Reject an exit check whose caller-visible value is unresolved."""
        if not self._model.flow_checks_enabled:
            return
        if not isinstance(state.value, int):
            self._error(
                line_object,
                f'flow counter "{state.name}" has an unresolved caller-visible '
                f'effect after call to "{state.value.callee}"',
            )
            return
        if expected is None:
            expected = state.expected_exit
        if expected is None or state.value == expected:
            return
        provenance = (
            state.branch_provenance[max(state.branch_provenance)]
            if state.branch_provenance
            else None
        )
        branch_suffix = (
            f'; path distinguished by branch at {provenance[0]} '
            f'({provenance[1]})'
            if provenance is not None
            else ''
        )
        self._error(
            line_object,
            f'flow counter "{state.name}" exit mismatch: '
            f'expected {expected}, actual {state.value}{branch_suffix}',
        )

    def _declare_coordinate(self, line_object: CounterCoordinateLine) -> None:
        """Declare a coordinate once and attach it to every reaching path."""
        line_index = self._line_objects.index(line_object)
        existing = self._coordinates_by_line.get(line_index)
        if existing is not None:
            state = self._active.get(existing.counter_name)
            if state is not None and all(
                coordinate is not existing
                for coordinate in state.coordinates
            ):
                state.coordinates.append(existing)
            return
        super()._declare_coordinate(line_object)
        coordinate = self._lookup_coordinate(line_object, line_object.label)
        if coordinate is not None:
            self._coordinates_by_line[line_index] = coordinate
            self._coordinate_line_index[id(coordinate)] = line_index

    def _apply_graph_delta(
        self,
        node: ControlFlowNode,
        state: _LinearCounterState,
        delta=None,
    ) -> None:
        """Apply one instruction or call-summary delta to a graph path."""
        if state.suspended:
            return
        resolved = (
            self._instruction_delta(node.line_object, node.record, state)
            if delta is None
            else self._resolve_delta(node.line_object, node.record, delta, state)
        )
        if resolved is None or not isinstance(state.value, int):
            return
        state.value += resolved
        for coordinate in state.coordinates:
            if (
                id(coordinate) not in state.invalid_coordinate_ids
                and not self._coordinate_is_live(state, coordinate)
            ):
                state.invalid_coordinate_ids.add(id(coordinate))
                coordinate.is_valid = False
        self._check_bounds(node.line_object, state)

    def _target_resolution(
        self,
        node: ControlFlowNode,
        target_address: int,
    ):
        """Resolve a known direct-target value without reporting diagnostics."""
        target_index = node.record.semantics['flow_target_operand']
        operand = node.record.operands[target_index]
        expression = operand.expression
        if (
            expression is not None
            and expression.token_type in {
                TokenType.T_LABEL,
                TokenType.T_LABEL_OR_NUM,
            }
            and expression.left is None
            and expression.right is None
        ):
            resolution = self._graph.label_named(
                str(expression.value),
                target_address,
            )
            if (
                resolution.node is None
                and expression.token_type == TokenType.T_LABEL_OR_NUM
                and is_unprefixed_numeric_string(
                    str(expression.value),
                    self._model.default_numeric_base,
                )
            ):
                # LABEL_OR_NUM evaluation gives an existing label precedence
                # over its numeric fallback; target identity must do likewise.
                resolution = self._graph.direct_target_at(target_address)
        else:
            resolution = self._graph.direct_target_at(target_address)
        return resolution

    def _target_node(self, node: ControlFlowNode) -> ControlFlowNode | None:
        """Resolve a direct target by exact label identity or unique address."""
        target_index = node.record.semantics.get('flow_target_operand')
        target_address = self._operand_semantic_value(
            node.line_object,
            node.record,
            target_index,
        )
        resolution = self._target_resolution(node, target_address)
        if resolution.node is None:
            self._error(
                node.line_object,
                f'instruction "{node.record.source_mnemonic}" target '
                f'{target_address:#x} is invalid: {resolution.error}',
            )
            return None
        return resolution.node

    def _fallthrough_node(
        self,
        node: ControlFlowNode,
    ) -> ControlFlowNode | None:
        """Resolve physical fall-through at the instruction's end address."""
        source_successor = self._graph.source_successor(node)
        if (
            source_successor.node is not None
            and source_successor.node.kind == 'boundary'
        ):
            return source_successor.node
        resolution = self._graph.fallthrough_at(node.end_address)
        if resolution.node is None:
            if self._graph.is_source_end(node):
                if not self._model.flow_checks_enabled:
                    return None
                names = ', '.join(sorted(self._active))
                self._error(
                    node.line_object,
                    f'flow counter(s) {names} reaches EOF without a flow '
                    'terminal or #endtrack',
                )
                return None
            self._error(
                node.line_object,
                f'instruction "{node.record.source_mnemonic}" has no valid '
                f'physical fall-through: {resolution.error}',
            )
            return None
        return resolution.node

    def _source_successor(
        self,
        node: ControlFlowNode,
    ) -> ControlFlowNode | None:
        """Resolve the next structural node after a zero-width source item."""
        resolution = self._graph.source_successor(node)
        if resolution.node is None:
            if self._graph.is_source_end(node):
                if not self._model.flow_checks_enabled:
                    return None
                names = ', '.join(sorted(self._active))
                self._error(
                    node.line_object,
                    f'flow counter(s) {names} reaches EOF without a flow '
                    'terminal or #endtrack',
                )
                return None
            self._error(node.line_object, resolution.error)
            return None
        return resolution.node

    def _process_instruction(
        self,
        node: ControlFlowNode,
    ) -> tuple[ControlFlowNode, ...]:
        """Apply instruction semantics and return its structural successors."""
        self._resolve_expressions(node.line_object, node.expression_nodes)
        if not self._active:
            return ()
        transfer = node.record.semantics.get('flow_transfer')
        if transfer is None:
            self._error(
                node.line_object,
                f'instruction "{node.record.source_mnemonic}" is missing '
                'required flow_transfer metadata',
            )
            return ()
        self._apply_instruction_invalidations(node.line_object, node.record)
        terminals = node.record.semantics.get('flow_terminal', {})
        mapped = [
            state
            for state in self._active.values()
            if isinstance(terminals, Mapping)
            and state.counter_class in terminals
        ]
        if mapped:
            if transfer == 'conditional':
                if not self._model.flow_checks_enabled:
                    return ()
                self._error(
                    node.line_object,
                    'conditional terminals are not yet supported',
                )
                return ()
            if transfer != 'return':
                if not self._model.flow_checks_enabled:
                    return ()
                self._error(
                    node.line_object,
                    f'instruction "{node.record.source_mnemonic}" is a flow '
                    f'terminal but its flow_transfer is "{transfer}"',
                )
                return ()
            for state in self._active.values():
                order = terminals.get(state.counter_class)
                if order is None:
                    if self._model.flow_checks_enabled:
                        self._error(
                            node.line_object,
                            f'instruction '
                            f'"{node.record.source_mnemonic}" returns while '
                            f'flow counter "{state.name}" is still active; '
                            f'end the region with #endtrack {state.name} '
                            'before this transfer',
                        )
                    continue
                if state.suspended:
                    if self._model.flow_checks_enabled:
                        self._error(
                            node.line_object,
                            self._suspended_terminal_message(
                                node.record,
                                state,
                            ),
                        )
                    continue
                if order == 'after_effect':
                    self._apply_graph_delta(node, state)
                self._check_exit(node.line_object, state)
            return ()

        if transfer == 'return':
            if self._model.flow_checks_enabled:
                names = ', '.join(sorted(self._active))
                self._error(
                    node.line_object,
                    f'instruction "{node.record.source_mnemonic}" returns '
                    f'while flow counter(s) {names} remain active',
                )
            return ()
        if transfer == 'indirect':
            if not self._model.flow_checks_enabled:
                return ()
            self._error(
                node.line_object,
                f'indirect control transfer "{node.record.source_mnemonic}" '
                'cannot be analyzed inside an active flow-counter region',
            )
            return ()
        if transfer == 'multiway':
            if not self._model.flow_checks_enabled:
                return ()
            self._error(
                node.line_object,
                'multiway control transfers are not available in M5',
            )
            return ()

        if transfer == 'call':
            target_index = node.record.semantics.get('flow_target_operand')
            target_address = self._operand_semantic_value(
                node.line_object,
                node.record,
                target_index,
            )
            resolution = self._target_resolution(node, target_address)
            if resolution.node is None and self._graph.has_program_content_at(
                target_address,
            ):
                # The address holds program content that cannot be entered
                # (emitted data, an ambiguous overlap): a real target error.
                # An address with no content at all is an external callee —
                # a ROM routine named by a predefined constant, for example —
                # whose declared call summary governs the caller-visible
                # effect; the callee body is not the analyzer's to verify.
                self._error(
                    node.line_object,
                    f'instruction "{node.record.source_mnemonic}" target '
                    f'{target_address:#x} is invalid: {resolution.error}',
                )
                return ()
            call_effects = node.record.semantics.get('flow_call_effects', {})
            for state in self._active.values():
                if state.suspended:
                    continue
                delta = (
                    call_effects.get(state.counter_class)
                    if isinstance(call_effects, Mapping)
                    else None
                )
                if delta is None:
                    operand_index = node.record.semantics['flow_target_operand']
                    state.value = _UnresolvedCall(
                        node.record.operands[operand_index].source_text,
                        state.counter_class,
                    )
                else:
                    self._apply_graph_delta(node, state, delta)
            fallthrough = self._fallthrough_node(node)
            return (fallthrough,) if fallthrough is not None else ()

        for state in self._active.values():
            self._apply_graph_delta(node, state)
        if transfer == 'none':
            fallthrough = self._fallthrough_node(node)
            return (fallthrough,) if fallthrough is not None else ()
        if transfer == 'conditional':
            target = self._target_node(node)
            fallthrough = self._fallthrough_node(node)
            return tuple(
                successor
                for successor in (target, fallthrough)
                if successor is not None
            )
        if transfer == 'unconditional':
            target = self._target_node(node)
            return (target,) if target is not None else ()
        self._error(
            node.line_object,
            f'instruction "{node.record.source_mnemonic}" has unsupported '
            f'flow_transfer "{transfer}"',
        )
        return ()

    def _process_node(self, node: ControlFlowNode) -> None:
        """Transfer one merged input state through a structural program point."""
        incoming = self._inputs[node.node_id]
        self._active = self._clone_states(incoming.states)
        before = self._graph_flow_values(self._active)
        line_object = node.line_object

        if isinstance(line_object, FlowTrackLine):
            region = self._region_by_track_index.get(node.line_index)
            if region is None:
                return
            self._open(line_object)
            state = self._active.get(line_object.counter_name)
            if (
                state is None
                or state.opened_by is not line_object
            ):
                return
            state.region_id = region.region_id
            self._templates[region.region_id] = self._clone_state(state)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, FlowEndTrackLine):
            self._close(line_object)
            successor = (
                self._source_successor(node)
                if self._active
                else None
            )
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, FlowEntryLine | LabelLine):
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, AssertLine):
            self._assert(line_object)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, FlowSetLine):
            self._set_counter(line_object)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, FlowSuspendLine):
            self._suspend_counter(line_object)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, FlowResumeLine):
            self._resume_counter(line_object)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, CounterCoordinateLine):
            self._declare_coordinate(line_object)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif isinstance(line_object, SetMemoryZoneLine):
            for state in self._active.values():
                self._check_exit(line_object, state)
                if self._model.flow_checks_enabled:
                    self._diagnostic_reporter.warn(
                        line_object.line_id,
                        f'{line_object.instruction.split()[0]} auto-closes '
                        f'flow counter region "{state.name}" at a physical '
                        'layout boundary',
                        category='flow',
                    )
            self._active.clear()
            successors = ()
        elif node.kind in {'data', 'observation'}:
            self._resolve_expressions(line_object, node.expression_nodes)
            successor = self._source_successor(node)
            successors = (successor,) if successor is not None else ()
        elif node.kind == 'instruction':
            successors = self._process_instruction(node)
        else:
            successors = ()

        is_terminal = (
            node.record is not None
            and node.record.semantics.get('flow_transfer') == 'return'
        )
        is_composite_instruction = (
            isinstance(line_object, InstructionLine)
            and len(line_object.analysis_units) > 1
        )
        exits_source_line = (
            not successors
            or any(
                successor.line_object is not line_object
                for successor in successors
            )
        )
        if not is_composite_instruction or exits_source_line:
            annotation_before = before
            if is_composite_instruction:
                first_node = next(
                    candidate
                    for candidate in self._graph.nodes
                    if candidate.line_object is line_object
                )
                first_input = self._inputs.get(first_node.node_id)
                if first_input is not None:
                    annotation_before = self._graph_flow_values(
                        first_input.states,
                    )
            if self._model.flow_checks_enabled:
                line_object.record_flow_transition(
                    annotation_before,
                    (
                        {}
                        if is_terminal
                        else self._graph_flow_values(self._active)
                    ),
                )
        sources = {
            name: line_object
            for name in self._active
        }
        transfer = (
            node.record.semantics.get('flow_transfer')
            if node.record is not None
            else None
        )
        for successor_index, successor in enumerate(successors):
            outgoing_states = self._active
            if transfer == 'conditional':
                outgoing_states = self._clone_states(self._active)
                outcome = (
                    'taken'
                    if successor_index == 0
                    else 'fall-through'
                )
                for state in outgoing_states.values():
                    state.branch_provenance[node.node_id] = (
                        line_object.line_id,
                        outcome,
                    )
            self._enqueue(
                successor,
                outgoing_states,
                sources,
                source_node=node,
            )

    def _drain(self) -> None:
        """Process scheduled nodes until the scalar fixed point is reached."""
        while self._queue:
            node_id = self._queue.popleft()
            self._process_node(self._graph.nodes[node_id])

    def _add_entry_roots(self) -> None:
        """Add explicit roots, then resolve value-less roots to a fixed point."""
        pending = dict(self._entries_by_label)
        while pending:
            ready = []
            for label_index, entries in pending.items():
                label_node = self._node_for_line(label_index)
                ordinary = self._inputs.get(label_node.node_id)
                if all(
                    entry.value_expression is not None
                    or (
                        ordinary is not None
                        and entry.counter_name in ordinary.states
                    )
                    for entry in entries
                ):
                    ready.append((label_index, label_node, entries, ordinary))
            if not ready:
                label_index, entries = next(iter(pending.items()))
                entry = next(
                    (
                        candidate
                        for candidate in entries
                        if candidate.value_expression is None
                    ),
                    entries[0],
                )
                self._error(
                    entry,
                    f'#entry {entry.counter_name} is unreachable; '
                    'value= is required',
                )
                return

            for label_index, label_node, entries, ordinary in ready:
                root_states = {}
                root_sources = {}
                for entry in entries:
                    region = self._memberships[label_index][entry.counter_name]
                    template = self._templates.get(region.region_id)
                    if template is None:
                        self._error(
                            entry,
                            f'#entry cannot resolve flow counter '
                            f'"{entry.counter_name}" because its #track root '
                            'is unreachable',
                        )
                        return
                    state = self._clone_state(template)
                    if entry.value_expression is None:
                        state = self._clone_state(
                            ordinary.states[entry.counter_name]
                        )
                    else:
                        try:
                            value = entry.evaluate_parameter('value')
                        except (
                            ArithmeticError,
                            RuntimeError,
                            SyntaxError,
                            SystemExit,
                            ValueError,
                        ) as error:
                            self._error(entry, str(error))
                            return
                        state.value = value
                        state.suspended = False
                        state.invalidated_since = None
                        prior_coordinates = [
                            coordinate
                            for coordinate_index, coordinate
                            in self._coordinates_by_line.items()
                            if coordinate_index < label_index
                            and coordinate.counter_name == state.name
                            and self._memberships[coordinate_index].get(
                                state.name
                            ) is region
                        ]
                        state.coordinates.extend(
                            coordinate
                            for coordinate in prior_coordinates
                            if coordinate not in state.coordinates
                        )
                        if value != state.initial_value:
                            state.invalid_coordinate_ids.update(
                                id(coordinate)
                                for coordinate in prior_coordinates
                            )
                        self._check_bounds(entry, state)
                    root_states[entry.counter_name] = state
                    root_sources[entry.counter_name] = entry
                self._enqueue(
                    label_node,
                    root_states,
                    root_sources,
                )
                del pending[label_index]
            self._drain()

    def _is_declared_region_entry(
        self,
        target_line_index: int,
        region: _LexicalRegion,
    ) -> bool:
        """Return whether a call target is an initial or explicit region root."""
        if any(
            entry.counter_name == region.name
            for entry in self._entries_by_label.get(target_line_index, ())
        ):
            return True
        return all(
            type(line_object) is LineObject
            or isinstance(line_object, FlowTrackLine)
            for line_object in self._line_objects[
                region.track_index + 1:target_line_index
            ]
        )

    def _validate_static_transfer_entries(self) -> None:
        """Reject direct transfers that enter tracked regions illegally."""
        if not self._model.flow_checks_enabled:
            return
        for node in self._graph.nodes:
            if node.record is None:
                continue
            transfer = node.record.semantics.get('flow_transfer')
            if transfer not in {'conditional', 'unconditional', 'call'}:
                continue
            target_index = node.record.semantics['flow_target_operand']
            operand = node.record.operands[target_index]
            if (
                operand.semantic_kind
                is not OperandSemanticKind.COMPILE_TIME_EXPRESSION
                or operand.expression is None
                or operand.expression.contains_flow_value()
            ):
                continue
            try:
                target_address = operand.expression.to_node().get_value(
                    node.line_object.symbol_scope,
                    node.line_object.active_named_scopes,
                    node.line_object.line_id,
                )
            except (
                ArithmeticError,
                RuntimeError,
                SyntaxError,
                SystemExit,
                ValueError,
            ):
                # Ordinary bytecode generation owns diagnostics for branches
                # unrelated to a tracked region. This pre-scan exists only to
                # catch otherwise-unreachable edges entering a region.
                continue
            resolution = self._target_resolution(node, target_address)
            if resolution.node is None:
                continue
            target = resolution.node
            source_regions = self._memberships[node.line_index]
            target_regions = self._memberships[target.line_index]
            for name, target_region in target_regions.items():
                source_region = source_regions.get(name)
                if transfer == 'call':
                    if (
                        source_region is target_region
                        or self._is_declared_region_entry(
                            target.line_index,
                            target_region,
                        )
                    ):
                        continue
                    self._error(
                        node.line_object,
                        f'call target enters flow counter region "{name}" '
                        'at non-entry label; target the region entry or '
                        f'declare #entry {name}',
                    )
                    continue
                if (
                    source_region is target_region
                    or target.line_index == target_region.track_index
                ):
                    continue
                self._error(
                    node.line_object,
                    f'control flow enters flow counter region "{name}" after '
                    f'#track {target_region.counter_class}',
                )

    def _warn_external_labels(self) -> None:
        """Warn about public labels that expose an undeclared entry state."""
        if not self._model.flow_checks_enabled:
            return
        for node in self._graph.nodes:
            if node.kind != 'label':
                continue
            label = node.line_object.get_label()
            if label.startswith('.'):
                continue
            incoming = self._inputs.get(node.node_id)
            entries = {
                entry.counter_name
                for entry in self._entries_by_label.get(node.line_index, ())
            }
            for name, region in self._memberships[node.line_index].items():
                if name in entries:
                    continue
                state = (
                    incoming.states.get(name)
                    if incoming is not None
                    else None
                )
                template = self._templates.get(region.region_id)
                if state is None:
                    self._diagnostic_reporter.warn(
                        node.line_object.line_id,
                        f'label "{label}" is an unreachable potential entry '
                        f'inside flow counter region "{name}"; add '
                        f'#entry {name} value=<expression> or a lexical '
                        f'#endtrack {name}',
                        category='flow',
                    )
                elif (
                    template is not None
                    and (
                        state.suspended
                        or state.value != template.initial_value
                    )
                ):
                    self._diagnostic_reporter.warn(
                        node.line_object.line_id,
                        f'label "{label}" is a potential external entry where '
                        f'flow counter "{name}" has value '
                        f'{self._state_description(state)}, not entry value '
                        f'{template.initial_value}; add #entry {name}',
                        category='flow',
                    )

    def _check_unreached_flow_constructs(self) -> None:
        """Diagnose flow constructs that no propagated graph state reached."""
        for node in self._graph.nodes:
            if node.node_id in self._inputs:
                continue
            memberships = self._memberships[node.line_index]
            if memberships:
                if not node.expression_nodes:
                    continue
                self._active = {}
                for name, region in memberships.items():
                    template = self._templates.get(region.region_id)
                    if template is None:
                        continue
                    state = self._clone_state(template)
                    state.path_live = False
                    self._active[name] = state
                self._resolve_expressions(
                    node.line_object,
                    node.expression_nodes,
                )
                continue

            self._active = {}
            line_object = node.line_object
            if node.expression_nodes:
                self._active = {}
                self._resolve_expressions(
                    line_object,
                    node.expression_nodes,
                )
            elif (
                isinstance(line_object, AssertLine)
                and line_object.is_flow_dependent
            ):
                if self._model.flow_checks_enabled:
                    self._assert(line_object)
            elif isinstance(line_object, FlowSetLine):
                self._set_counter(line_object)
            elif isinstance(line_object, FlowSuspendLine):
                self._suspend_counter(line_object)
            elif isinstance(line_object, FlowResumeLine):
                self._resume_counter(line_object)
            elif isinstance(line_object, CounterCoordinateLine):
                self._declare_coordinate(line_object)

    def run(self, line_objects) -> None:
        """Build the structural CFG and propagate scalar states to a fixed point."""
        self._line_objects = tuple(line_objects)
        self._graph = ControlFlowGraph.from_line_objects(self._line_objects)
        self._validate_coordinate_scopes()
        self._prepare_regions()
        self._prepare_entries()
        self._validate_static_transfer_entries()

        for node in self._graph.nodes:
            if not isinstance(node.line_object, FlowTrackLine):
                continue
            enclosing = {
                name: region
                for name, region in self._memberships[node.line_index].items()
                if region.track_index != node.line_index
            }
            if not enclosing:
                self._enqueue(node, {}, {})
        self._drain()
        self._add_entry_roots()
        self._check_unreached_flow_constructs()
        if self._model.flow_checks_enabled:
            self._warn_external_labels()
