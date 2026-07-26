from collections.abc import Mapping
from dataclasses import dataclass

from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowEndTrackLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import FlowTrackLine
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import TokenType


@dataclass
class _LinearCounterState:
    counter_class: str
    name: str
    value: int
    initial_value: int
    expected_exit: int | None
    config: dict
    opened_by: FlowTrackLine


class FlowLinearAnalyzer:
    """M1 source-order analyzer for one scalar, straight-line counter."""

    def __init__(self, model, diagnostic_reporter) -> None:
        """Create an analyzer bound to one immutable ISA model and reporter."""
        self._model = model
        self._diagnostic_reporter = diagnostic_reporter
        self._active: _LinearCounterState | None = None

    @staticmethod
    def source_uses_flow(line_objects) -> bool:
        """Return whether compiled source contains any M1 flow construct."""
        return any(
            isinstance(line_object, FlowTrackLine | FlowEndTrackLine)
            or bool(line_object.flow_expression_nodes)
            for line_object in line_objects
        )

    def _error(self, line_object, message: str) -> None:
        self._diagnostic_reporter.error(
            line_object.line_id,
            message,
            category='flow',
        )

    def _check_bounds(self, line_object) -> None:
        """Report a bound violation for the active counter at this source line."""
        minimum = self._active.config.get('min_value')
        maximum = self._active.config.get('max_value')
        if minimum is not None and self._active.value < minimum:
            self._error(
                line_object,
                f'flow counter "{self._active.name}" underflow: '
                f'value {self._active.value} is below minimum {minimum}',
            )
        if maximum is not None and self._active.value > maximum:
            self._error(
                line_object,
                f'flow counter "{self._active.name}" overflow: '
                f'value {self._active.value} exceeds maximum {maximum}',
            )

    def _open(self, line_object: FlowTrackLine) -> None:
        """Validate and initialize the scalar counter named by ``#track``."""
        if self._active is not None:
            self._error(
                line_object,
                f'flow counter "{self._active.name}" is still active; '
                f'insert #endtrack {self._active.name} before opening another counter',
            )
        counter_config = self._model.flow_counters.get(line_object.counter_class)
        if counter_config is None:
            self._error(
                line_object,
                f'flow counter class "{line_object.counter_class}" is not declared by this instruction set',
            )
        if counter_config.get('join', 'require-equal') != 'require-equal':
            self._error(
                line_object,
                f'flow counter class "{line_object.counter_class}" is not scalar; '
                'interval analysis is not available in M1',
            )
        if not self._model.flow_counter_has_effect_metadata(line_object.counter_class):
            self._error(
                line_object,
                f'flow counter class "{line_object.counter_class}" is inert: '
                'no instruction declares an effect or terminal',
            )

        initial = line_object.evaluate_parameter('init')
        if initial is None:
            initial = counter_config.get('default_init', 0)
        expected_exit = line_object.evaluate_parameter('exit')
        if expected_exit is None and counter_config.get('exit_policy', 'balanced') == 'balanced':
            expected_exit = initial
        self._active = _LinearCounterState(
            counter_class=line_object.counter_class,
            name=line_object.counter_class,
            value=initial,
            initial_value=initial,
            expected_exit=expected_exit,
            config=counter_config,
            opened_by=line_object,
        )
        self._check_bounds(line_object)

    def _close(self, line_object: FlowEndTrackLine) -> None:
        """Apply the exit contract and close the active tracking region."""
        if self._active is None:
            self._error(
                line_object,
                f'#endtrack {line_object.counter_name} has no active counter',
            )
        if line_object.counter_name != self._active.name:
            self._error(
                line_object,
                f'#endtrack names "{line_object.counter_name}", but active counter is '
                f'"{self._active.name}"',
            )
        expected = line_object.evaluate_parameter('exit')
        if expected is None:
            expected = self._active.expected_exit
        if expected is not None and self._active.value != expected:
            self._error(
                line_object,
                f'flow counter "{self._active.name}" exit mismatch: '
                f'expected {expected}, actual {self._active.value}',
            )
        self._active = None

    def _counter_name(self, line_object, node: ExpressionNode) -> str:
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
        return str(argument.value)

    def _resolve_expressions(self, line_object, nodes: tuple[ExpressionNode, ...]) -> None:
        """Deposit the active pre-instruction value into deferred expressions."""
        for node in nodes:
            counter_name = self._counter_name(line_object, node)
            if self._active is None:
                self._error(
                    line_object,
                    f'COUNTER({counter_name}) references an inactive flow counter',
                )
            if counter_name != self._active.name:
                self._error(
                    line_object,
                    f'COUNTER({counter_name}) does not name active counter "{self._active.name}"',
                )
            node.resolve_flow_value(self._active.value)

    @staticmethod
    def _path_value(mapping: Mapping, path: str):
        """Read a dotted metadata path, returning ``None`` when it is absent."""
        value = mapping
        for component in path.split('.'):
            if not isinstance(value, Mapping) or component not in value:
                return None
            value = value[component]
        return value

    def _apply_instruction(self, line_object, record, expression_nodes) -> None:
        """Resolve operand uses, validate transfer metadata, and apply one delta."""
        self._resolve_expressions(line_object, expression_nodes)
        if self._active is None:
            return

        transfer = record.semantics.get('flow_transfer')
        if transfer is None:
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" is missing required flow_transfer metadata',
            )
        if transfer != 'none':
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" uses flow_transfer "{transfer}"; '
                'path analysis is not yet available in M1',
            )

        source = self._active.config.get(
            'source',
            f'flow_effects.{self._active.counter_class}',
        )
        delta = self._path_value(record.semantics, source)
        if delta is None:
            unknown_policy = self._active.config.get('unknown_instructions', 'warn')
            message = (
                f'instruction "{record.source_mnemonic}" has no effect metadata '
                f'for flow counter class "{self._active.counter_class}"'
            )
            if unknown_policy == 'warn':
                self._diagnostic_reporter.warn(
                    line_object.line_id,
                    message,
                    category='flow',
                )
            elif unknown_policy == 'error':
                self._error(line_object, message)
            return
        if isinstance(delta, bool) or not isinstance(delta, int):
            self._error(
                line_object,
                f'instruction "{record.source_mnemonic}" has a non-constant effect for '
                f'"{self._active.counter_class}"; M1 supports integer deltas only',
            )
        self._active.value += delta
        self._check_bounds(line_object)

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
            if isinstance(line_object, InstructionLine):
                for record, expression_nodes in line_object.analysis_units:
                    self._apply_instruction(line_object, record, expression_nodes)
                continue
            if line_object.flow_expression_nodes:
                self._resolve_expressions(line_object, line_object.flow_expression_nodes)

        if self._active is not None:
            self._error(
                last_line or self._active.opened_by,
                f'flow counter "{self._active.name}" reaches EOF without #endtrack',
            )
