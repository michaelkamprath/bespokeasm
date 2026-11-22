"""Attaches ``#annotate`` lines to the label or constant definition directly below them."""
from __future__ import annotations

from bespokeasm.assembler.annotations.model import Annotation
from bespokeasm.assembler.annotations.model import symbol_scope_name
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line.annotate import AnnotationLine


def _join(items: tuple[str, ...]) -> str:
    if len(items) == 1:
        return items[0]
    return ', '.join(items[:-1]) + f' and {items[-1]}'


class AnnotationBinder:
    """Tracks the ``#annotate`` lines waiting for a definition in one source file.

    ``AssemblyFile`` reports every source line to the binder: annotations with
    ``add``, definitions with ``bind``, and anything else with ``interrupt``, which is
    an error while annotations are pending.
    """

    def __init__(self) -> None:
        self._pending: list[AnnotationLine] = []

    @property
    def has_pending(self) -> bool:
        return len(self._pending) > 0

    def add(self, line: AnnotationLine) -> None:
        self._pending.append(line)

    def interrupt(self, line_id: LineIdentifier, description: str) -> None:
        """Report that a line which is not a definition follows pending annotations."""
        if not self._pending:
            return
        first = self._pending[0]
        raise AssemblerError(
            first.line_id,
            f'#annotate must be directly above a label or constant definition, '
            f'but line {line_id.line_num} is {description}',
        )

    def finish(self) -> None:
        """Report annotations left pending at the end of a file."""
        if not self._pending:
            return
        raise AssemblerError(
            self._pending[0].line_id,
            '#annotate at the end of the file has no label or constant definition after it',
        )

    def bind(self, definition: LabelLine) -> None:
        """Attach the pending annotations to a definition, checking each one against it."""
        if not self._pending:
            return
        name = definition.get_label()
        kind = 'constant' if definition.is_constant else 'label'
        scope = symbol_scope_name(name)
        annotations: dict[str, Annotation] = {}
        for line in self._pending:
            annotation = line.annotation
            namespace = annotation.namespace
            if namespace.name in annotations:
                raise AssemblerError(
                    line.line_id,
                    f"symbol '{name}' already has an annotation in the '{namespace.name}' namespace",
                )
            if kind not in namespace.applies_to:
                raise AssemblerError(
                    line.line_id,
                    f"annotation '{namespace.name}' is not allowed on {kind} '{name}'; "
                    f'it applies only to {_join(tuple(k + "s" for k in namespace.applies_to))}',
                )
            if scope not in namespace.scopes:
                raise AssemblerError(
                    line.line_id,
                    f"annotation '{namespace.name}' is not allowed on {scope} {kind} '{name}'; "
                    f'it applies only to {_join(namespace.scopes)} symbols',
                )
            if definition.is_constant:
                self._check_value_range(definition, annotation)
            annotations[namespace.name] = annotation
        definition.annotations = annotations
        self._pending = []

    @staticmethod
    def _check_value_range(definition: LabelLine, annotation: Annotation) -> None:
        try:
            allowed = annotation.namespace.allowed_range(annotation.arguments)
        except ValueError as exc:
            raise AssemblerError(annotation.line_id, str(exc))
        if allowed is None:
            return
        value = definition.get_value()
        low, high = allowed
        if not low <= value <= high:
            basis = annotation.namespace.value_range_basis(annotation.arguments)
            range_of = f', the range of {basis}' if basis else ''
            raise AssemblerError(
                definition.line_id,
                f"'{definition.get_label()}' value {value} is outside {low} to {high}{range_of} "
                f"(annotation '{annotation.name}')",
            )
