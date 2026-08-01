from __future__ import annotations

from dataclasses import dataclass

from bespokeasm.assembler.analysis import InstructionAnalysisRecord
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.counter_coordinate_line import CounterCoordinateLine
from bespokeasm.assembler.line_object.directive_line.memzone import SetMemoryZoneLine
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line.assert_line import AssertLine
from bespokeasm.assembler.line_object.preprocessor_line.flow_counter import (
    FlowCounterDirectiveLine,
)
from bespokeasm.expression import ExpressionNode


def declared_coordinate_labels(line_objects) -> frozenset[str]:
    """Collect the exact spellings of every ``:=`` coordinate declaration."""
    return frozenset(
        line_object.label
        for line_object in line_objects
        if isinstance(line_object, CounterCoordinateLine)
    )


def references_declared_coordinate(
    line_object,
    declared_labels: frozenset[str],
) -> bool:
    """Return whether a line's expressions reference a declared coordinate.

    Ordinary labels outrank coordinates at evaluation, so a candidate that an
    already-registered label satisfies is not a coordinate reference even
    when a coordinate shares its spelling.
    """
    if not declared_labels:
        return False
    for node in line_object.flow_candidate_nodes:
        name = str(node.value)
        if name not in declared_labels:
            continue
        try:
            label_value = line_object.symbol_scope.get_label_value(
                name,
                line_object.line_id,
            )
        except (SystemExit, ValueError):
            label_value = None
        if label_value is None:
            return True
    return False


@dataclass(frozen=True)
class ControlFlowNode:
    """One structurally relevant program point in source and address space."""

    node_id: int
    source_order: int
    line_index: int
    line_object: LineObject
    address: int
    word_count: int
    kind: str
    record: InstructionAnalysisRecord | None = None
    expression_nodes: tuple[ExpressionNode, ...] = ()

    @property
    def end_address(self) -> int:
        """Return the physical address immediately following this node."""
        return self.address + self.word_count


@dataclass(frozen=True)
class ControlFlowResolution:
    """Result of resolving one physical executable address."""

    node: ControlFlowNode | None
    error: str | None = None
    permits_zero_width_fallback: bool = False


class ControlFlowGraph:
    """Analysis-neutral source/layout index used to construct execution edges."""

    def __init__(
        self,
        nodes: tuple[ControlFlowNode, ...],
        source_items: tuple[ControlFlowNode, ...],
    ) -> None:
        self.nodes = nodes
        self._source_items = source_items
        self._source_position = {
            node.node_id: index
            for index, node in enumerate(source_items)
        }
        self._instruction_nodes_by_address: dict[int, list[ControlFlowNode]] = {}
        self._data_nodes_by_address: dict[int, list[ControlFlowNode]] = {}
        self._observation_nodes_by_address: dict[
            int,
            list[ControlFlowNode],
        ] = {}
        self._zero_nodes_by_address: dict[int, list[ControlFlowNode]] = {}
        self._label_nodes_by_object: dict[int, ControlFlowNode] = {}
        for node in nodes:
            if node.kind == 'instruction':
                self._instruction_nodes_by_address.setdefault(
                    node.address,
                    [],
                ).append(node)
            elif node.kind == 'data':
                for address in range(node.address, node.end_address):
                    self._data_nodes_by_address.setdefault(address, []).append(node)
            elif node.kind == 'observation' and node.word_count > 0:
                for address in range(node.address, node.end_address):
                    self._observation_nodes_by_address.setdefault(
                        address,
                        [],
                    ).append(node)
            elif node.kind == 'label':
                self._label_nodes_by_object[id(node.line_object)] = node
            if node.word_count == 0:
                self._zero_nodes_by_address.setdefault(node.address, []).append(node)

    @classmethod
    def from_line_objects(cls, line_objects) -> ControlFlowGraph:
        """Build immutable program points after first-pass address assignment."""
        nodes = []
        source_order = 0
        declared_labels = declared_coordinate_labels(line_objects)
        for line_index, line_object in enumerate(line_objects):
            if isinstance(line_object, InstructionLine):
                address = line_object.address
                for record, expression_nodes in line_object.analysis_units:
                    nodes.append(
                        ControlFlowNode(
                            node_id=len(nodes),
                            source_order=source_order,
                            line_index=line_index,
                            line_object=line_object,
                            address=address,
                            word_count=record.word_count,
                            kind='instruction',
                            record=record,
                            expression_nodes=expression_nodes,
                        )
                    )
                    source_order += 1
                    address += record.word_count
                continue

            kind = None
            if isinstance(line_object, LabelLine) and not line_object.is_constant:
                kind = 'label'
            elif isinstance(line_object, FlowCounterDirectiveLine | AssertLine):
                kind = 'directive'
            elif isinstance(line_object, CounterCoordinateLine):
                kind = 'coordinate'
            elif isinstance(line_object, SetMemoryZoneLine):
                kind = 'boundary'
            elif line_object.flow_expression_nodes or references_declared_coordinate(
                line_object,
                declared_labels,
            ):
                kind = 'observation'
            elif (
                isinstance(line_object, LineWithWords)
                and line_object.word_count > 0
            ):
                kind = 'data'

            if kind is None:
                continue
            nodes.append(
                ControlFlowNode(
                    node_id=len(nodes),
                    source_order=source_order,
                    line_index=line_index,
                    line_object=line_object,
                    address=line_object.address,
                    word_count=(
                        line_object.word_count
                        if isinstance(line_object, LineWithWords)
                        else 0
                    ),
                    kind=kind,
                    expression_nodes=(
                        line_object.flow_expression_nodes
                        + line_object.flow_candidate_nodes
                    ),
                )
            )
            source_order += 1
        immutable_nodes = tuple(nodes)
        return cls(immutable_nodes, immutable_nodes)

    def node_for_label(self, label_line: LabelLine) -> ControlFlowNode | None:
        """Return the exact source node representing an address label."""
        return self._label_nodes_by_object.get(id(label_line))

    def has_program_content_at(self, address: int) -> bool:
        """Return whether the program emits anything at an address.

        An address with no content at all is outside the assembled program —
        the distinguishing mark of an external target such as a ROM routine
        named by a predefined constant.
        """
        return bool(
            self._instruction_nodes_by_address.get(address)
            or self._data_nodes_by_address.get(address)
            or self._observation_nodes_by_address.get(address)
        )

    def label_named(
        self,
        label: str,
        address: int,
    ) -> ControlFlowResolution:
        """Resolve a label only when its address contains executable code."""
        matches = [
            node
            for node in self._label_nodes_by_object.values()
            if node.line_object.get_label() == label
            and node.address == address
        ]
        if len(matches) > 1:
            return ControlFlowResolution(
                None,
                f'label "{label}" is ambiguous at address {address:#x}',
            )
        if not matches:
            return ControlFlowResolution(
                None,
                f'label "{label}" does not identify executable code at '
                f'address {address:#x}',
            )
        executable = self.direct_target_at(address)
        if executable.node is None:
            return executable
        return ControlFlowResolution(matches[0])

    def source_successor(
        self,
        node: ControlFlowNode,
    ) -> ControlFlowResolution:
        """Resolve the next source-adjacent node for a zero-width program point."""
        position = self._source_position[node.node_id] + 1
        if position >= len(self._source_items):
            return ControlFlowResolution(
                None,
                f'no executable instruction follows {node.line_object.instruction or "this program point"}',
            )
        successor = self._source_items[position]
        if successor.kind == 'boundary':
            return ControlFlowResolution(successor)
        if successor.address != node.end_address:
            return ControlFlowResolution(
                None,
                f'physical fall-through from address {node.end_address:#x} enters an address gap',
            )
        if successor.kind == 'data':
            return ControlFlowResolution(
                None,
                f'physical fall-through at address {successor.address:#x} '
                'enters emitted data',
            )
        return ControlFlowResolution(successor)

    def is_source_end(self, node: ControlFlowNode) -> bool:
        """Return whether no later structural source item follows this node."""
        return self._source_position[node.node_id] + 1 >= len(self._source_items)

    def executable_at(self, address: int) -> ControlFlowResolution:
        """Resolve one unambiguous executable entry at an exact address."""
        data = self._data_nodes_by_address.get(address, ())
        if data:
            return ControlFlowResolution(
                None,
                f'physical fall-through at address {address:#x} enters emitted data',
                True,
            )
        observations = self._observation_nodes_by_address.get(address, ())
        if any(node.address != address for node in observations):
            return ControlFlowResolution(
                None,
                f'physical fall-through at address {address:#x} enters emitted data',
                True,
            )
        executable_nodes = (
            tuple(self._instruction_nodes_by_address.get(address, ()))
            + tuple(observations)
        )
        if not executable_nodes:
            return ControlFlowResolution(
                None,
                f'physical fall-through at address {address:#x} enters an address gap '
                'or non-executable target',
                True,
            )
        if len(executable_nodes) > 1:
            return ControlFlowResolution(
                None,
                f'physical fall-through at address {address:#x} resolves to '
                'multiple executable nodes',
            )

        executable = executable_nodes[0]
        position = self._source_position[executable.node_id]
        entry = executable
        while position > 0:
            predecessor = self._source_items[position - 1]
            if predecessor.address != address or predecessor.word_count != 0:
                break
            entry = predecessor
            position -= 1
        return ControlFlowResolution(entry)

    def direct_target_at(self, address: int) -> ControlFlowResolution:
        """Resolve an address-only branch target without executing directives.

        A direct machine transfer lands on emitted code. Address labels at
        that location retain useful source identity, but analysis-only
        directives sharing the address are not executed merely because the
        machine target has the same numeric value.
        """
        data = self._data_nodes_by_address.get(address, ())
        observations = self._observation_nodes_by_address.get(address, ())
        instructions = self._instruction_nodes_by_address.get(address, ())
        if data or observations:
            return ControlFlowResolution(
                None,
                f'direct target at address {address:#x} enters emitted data',
            )
        if not instructions:
            return ControlFlowResolution(
                None,
                f'direct target at address {address:#x} enters an address gap '
                'or non-executable target',
            )
        if len(instructions) > 1:
            return ControlFlowResolution(
                None,
                f'direct target at address {address:#x} resolves to multiple '
                'executable nodes',
            )

        instruction = instructions[0]
        position = self._source_position[instruction.node_id]
        entry = instruction
        while position > 0:
            predecessor = self._source_items[position - 1]
            if (
                predecessor.address != address
                or predecessor.word_count != 0
                or predecessor.kind != 'label'
            ):
                break
            entry = predecessor
            position -= 1
        return ControlFlowResolution(entry)

    def fallthrough_at(self, address: int) -> ControlFlowResolution:
        """Resolve an executable or zero-width exit/checkpoint at an address."""
        resolution = self.executable_at(address)
        if resolution.node is not None:
            return resolution
        if not resolution.permits_zero_width_fallback:
            return resolution
        zero_nodes = self._zero_nodes_by_address.get(address, ())
        if not zero_nodes:
            return resolution
        positions = sorted(
            self._source_position[node.node_id]
            for node in zero_nodes
        )
        if any(
            right != left + 1
            for left, right in zip(positions, positions[1:])
        ):
            return ControlFlowResolution(
                None,
                f'physical fall-through at address {address:#x} encounters '
                'multiple noncontiguous zero-width source groups',
            )
        return ControlFlowResolution(
            self._source_items[positions[0]],
        )
