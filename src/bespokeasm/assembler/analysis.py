from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from typing import TYPE_CHECKING

from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import ExpressionUseContext
from bespokeasm.expression import TokenType

if TYPE_CHECKING:
    from bespokeasm.assembler.line_object.instruction_line import InstructionLine
    from bespokeasm.assembler.model.instruction import InstructionVariant


class OperandSemanticKind(enum.Enum):
    """The kind of source-level value represented by a parsed operand."""

    COMPILE_TIME_EXPRESSION = 'compile_time_expression'
    RUNTIME_REGISTER = 'runtime_register'
    OPAQUE = 'opaque'


@dataclass(frozen=True)
class FrozenExpression:
    """An immutable snapshot of an already-parsed expression tree."""

    token_type: TokenType
    value: Any
    left: FrozenExpression | None = None
    right: FrozenExpression | None = None
    expression_context: ExpressionUseContext | None = None
    default_numeric_base: str = 'decimal'

    @classmethod
    def from_node(cls, node: ExpressionNode | None) -> FrozenExpression | None:
        if node is None:
            return None
        return cls(
            token_type=node.token_type,
            value=node.value,
            left=cls.from_node(node.left_child),
            right=cls.from_node(node.right_child),
            expression_context=node.expression_context,
            default_numeric_base=node.default_numeric_base,
        )

    def to_node(self) -> ExpressionNode:
        """Rebuild a private mutable tree for semantic-value evaluation.

        Analysis records retain immutable expression snapshots so later
        passes cannot mutate the bytecode generator's live trees.  Consumers
        that need a compile-time operand value evaluate this reconstructed
        copy against the source line's completed symbol scopes.
        """
        node = ExpressionNode(
            self.token_type,
            self.value,
            self.default_numeric_base,
        )
        node.left_child = self.left.to_node() if self.left is not None else None
        node.right_child = self.right.to_node() if self.right is not None else None
        if self.expression_context is not None:
            node._expression_context = self.expression_context
        return node

    def contains_flow_value(self) -> bool:
        """Return whether the snapshot contains a ``COUNTER`` operator.

        Bare counter-coordinate references are not detectable here — they are
        ordinary labels until scope lookup; consumers that must reject them
        rely on the ``FlowSymbolError`` raised at evaluation instead.
        """
        if self.token_type == TokenType.T_COUNTER:
            return True
        return (
            self.left is not None
            and self.left.contains_flow_value()
        ) or (
            self.right is not None
            and self.right.contains_flow_value()
        )


@dataclass(frozen=True)
class SourceIdentity:
    """Stable identity for one source line object or macro constituent."""

    filename: str | None
    line_number: int
    line_object_ordinal: int
    macro_path: tuple[tuple[str, int], ...] = ()

    @classmethod
    def from_line_id(
        cls,
        line_id,
        line_object_ordinal: int = 0,
    ) -> SourceIdentity:
        return cls(
            filename=getattr(line_id, 'filename', None),
            line_number=getattr(line_id, 'line_num', line_id),
            line_object_ordinal=line_object_ordinal,
        )

    def macro_constituent(self, mnemonic: str, step: int) -> SourceIdentity:
        return SourceIdentity(
            filename=self.filename,
            line_number=self.line_number,
            line_object_ordinal=self.line_object_ordinal,
            macro_path=(*self.macro_path, (mnemonic, step)),
        )


@dataclass(frozen=True)
class AnalysisOperand:
    """Immutable source-semantic view of a matched operand."""

    operand_id: str
    operand_type: OperandType
    source_text: str
    semantic_kind: OperandSemanticKind
    expression: FrozenExpression | None
    expression_context: ExpressionUseContext = ExpressionUseContext.OPERAND_VALUE


@dataclass(frozen=True)
class InstructionAnalysisRecord:
    """Analysis-only facts retained for a selected real instruction variant."""

    source_identity: SourceIdentity
    selected_variant: InstructionVariant
    variant_number: int
    source_mnemonic: str
    canonical_mnemonic: str
    semantics: Mapping[str, Any]
    operands: tuple[AnalysisOperand, ...]
    word_count: int

    @property
    def parsed_operand_expressions(self) -> tuple[FrozenExpression | None, ...]:
        return tuple(operand.expression for operand in self.operands)


@dataclass(frozen=True)
class AnalysisExecutableNode:
    """One source-ordered real instruction, including a macro constituent."""

    source_identity: SourceIdentity
    line_object: InstructionLine
    record: InstructionAnalysisRecord
    expression_nodes: tuple[ExpressionNode, ...] = ()


@dataclass(frozen=True)
class AnalysisSourceIndex:
    """Immutable source-order index consumed by later analysis passes."""

    nodes: tuple[AnalysisExecutableNode, ...]

    @classmethod
    def from_line_objects(cls, line_objects) -> AnalysisSourceIndex:
        """Build an immutable source-order index of real instruction units."""
        nodes = []
        for line_object in line_objects:
            for record, expression_nodes in line_object.analysis_units:
                nodes.append(
                    AnalysisExecutableNode(
                        source_identity=record.source_identity,
                        line_object=line_object,
                        record=record,
                        expression_nodes=expression_nodes,
                    )
                )
        return cls(tuple(nodes))

    @property
    def records(self) -> tuple[InstructionAnalysisRecord, ...]:
        return tuple(node.record for node in self.nodes)


def freeze_analysis_value(value: Any) -> Any:
    """Recursively freeze config data before retaining it for analysis."""

    if isinstance(value, Mapping):
        return MappingProxyType({
            key: freeze_analysis_value(item)
            for key, item in value.items()
        })
    if isinstance(value, list | tuple):
        return tuple(freeze_analysis_value(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(freeze_analysis_value(item) for item in value)
    return value
