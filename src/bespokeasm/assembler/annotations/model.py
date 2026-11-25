"""The export model: annotated symbols as later features (listings, output formats) read them.

Annotations are recorded on the ``LabelLine`` that defines the symbol while source is
parsed. After the first assembly pass assigns addresses, ``ExportModel.build`` collects
every annotated symbol, measures each label's data run, checks ``data_size``, and
resolves ``symbol``-typed arguments. A data run's words are read only on request, after
the second pass has generated them. It also holds the ``#verbatim`` blocks, in source order.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from bespokeasm.assembler.annotations.schema import AnnotationNamespace
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_continuation import ContinuationLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.assembler.line_object.directive_line.fill_data import FillDataLine
from bespokeasm.assembler.line_object.directive_line.fill_data import FillUntilDataLine
from bespokeasm.assembler.line_object.emdedded_string import EmbeddedString
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line.verbatim import VerbatimLine
from bespokeasm.assembler.symbol_scope import SymbolScopeType

DATA_LINE_TYPES = (DataLine, FillDataLine, FillUntilDataLine, EmbeddedString)

_SCOPE_NAMES = {
    SymbolScopeType.GLOBAL: 'global',
    SymbolScopeType.FILE: 'file',
    SymbolScopeType.LOCAL: 'local',
}


def symbol_scope_name(symbol: str) -> str:
    """The annotation scope name (global, file or local) implied by a symbol's prefix."""
    return _SCOPE_NAMES[SymbolScopeType.get_symbol_scope(symbol)]


def _terminator_text(element: int, terminator: int | None) -> str:
    value = '' if terminator is None else f'{terminator} '
    return f'{value}terminator' if element == 1 else f'{element}-word {value}terminator'


def _found_data(size: int) -> str:
    if size == 0:
        return 'no data follows it'
    return f'{_plural(size, "word")} of data {"follows" if size == 1 else "follow"} it'


def _plural(count: int, noun: str) -> str:
    return f'{count} {noun}' if count == 1 else f'{count} {noun}s'


@dataclass
class Annotation:
    """One validated ``#annotate`` line."""
    namespace: AnnotationNamespace
    arguments: dict[str, Any]
    line_id: LineIdentifier
    resolved_symbols: dict[str, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.namespace.name


@dataclass
class AnnotatedSymbol:
    name: str
    kind: str                         # 'label' or 'constant'
    scope: str                        # 'global', 'file' or 'local'
    value: int                        # the address of a label, the value of a constant
    line_id: LineIdentifier
    annotations: dict[str, Annotation]
    data_run: tuple[LineWithWords, ...] = ()
    # Annotations whose data must end with a terminator element, with that element's word count.
    # Checked once words exist (``ExportModel.check_terminators``).
    terminated: list[tuple[Annotation, int]] = field(default_factory=list)

    @property
    def is_label(self) -> bool:
        return self.kind == 'label'

    @property
    def address(self) -> int | None:
        return self.value if self.is_label else None

    @property
    def size(self) -> int | None:
        """The word count of a label's data run; None for a constant."""
        if not self.is_label:
            return None
        return sum(line.word_count for line in self.data_run)

    @property
    def words(self) -> list[Word]:
        """The words of a label's data run. Valid only after bytecode generation."""
        return [word for line in self.data_run for word in line.get_words()]


@dataclass(frozen=True)
class VerbatimBlock:
    """One ``#verbatim`` block: its namespace and part, where it starts, and its text as formats
    write it."""
    namespace: str
    line_id: LineIdentifier
    text: str
    last_line: int                    # the line number of its #endverbatim
    part: str | None = None           # None when the block names no part


class ExportModel:
    def __init__(self, symbols: list[AnnotatedSymbol], verbatim_blocks: list[VerbatimBlock] | None = None) -> None:
        self._symbols = symbols
        self._verbatim_blocks = verbatim_blocks or []

    @property
    def verbatim_blocks(self) -> list[VerbatimBlock]:
        """Every ``#verbatim`` block, in source order (included files where they are included)."""
        return list(self._verbatim_blocks)

    def verbatim_for(self, namespace: str, part: str | None = None) -> list[VerbatimBlock]:
        """The blocks of one namespace that name ``part`` (``None``: the blocks that name no part)."""
        return [block for block in self._verbatim_blocks if block.namespace == namespace and block.part == part]

    @property
    def symbols(self) -> list[AnnotatedSymbol]:
        """Every annotated symbol, in the order it is defined in source."""
        return list(self._symbols)

    def for_namespace(self, namespace: str) -> list[AnnotatedSymbol]:
        return [symbol for symbol in self._symbols if namespace in symbol.annotations]

    def check_terminators(self, terminator: int) -> None:
        """After bytecode generation: each terminated data run must end with a terminator element,
        every word of which is ``terminator`` (the ISA's ``.cstr`` terminator)."""
        for symbol in self._symbols:
            for annotation, element in symbol.terminated:
                last = symbol.words[-element:]
                if all(word.value == terminator for word in last):
                    continue
                found = ' '.join(f'0x{word.value:02x}' for word in last)
                raise AssemblerError(
                    symbol.line_id,
                    f"'{symbol.name}' is annotated as "
                    f'{annotation.namespace.data_size.inferring_arguments(annotation.arguments)}, '
                    'which needs its data to end '
                    f'with a {_terminator_text(element, terminator)}, but it ends with {found} '
                    f"(annotation '{annotation.name}')",
                )

    @classmethod
    def build(cls, line_objects: list[LineObject]) -> ExportModel:
        """Collect annotated symbols from source-ordered line objects after the first pass."""
        symbols: list[AnnotatedSymbol] = []
        blocks: list[VerbatimBlock] = []
        for index, line in enumerate(line_objects):
            if isinstance(line, VerbatimLine) and line.compilable:
                last_line = line.line_id.line_num + len(line.text_lines) + 1
                blocks.append(VerbatimBlock(line.namespace, line.line_id, line.text, last_line, line.part))
                continue
            if not isinstance(line, LabelLine) or not line.compilable or not line.annotations:
                continue
            name = line.get_label()
            is_label = not line.is_constant
            symbol = AnnotatedSymbol(
                name=name,
                kind='label' if is_label else 'constant',
                scope=symbol_scope_name(name),
                value=line.get_value(),
                line_id=line.line_id,
                annotations=dict(line.annotations),
                data_run=cls._data_run(line_objects, index) if is_label else (),
            )
            for annotation in symbol.annotations.values():
                if is_label:
                    cls._check_data_size(symbol, annotation)
                cls._resolve_symbol_arguments(line, annotation)
            symbols.append(symbol)
        return ExportModel(symbols, blocks)

    @staticmethod
    def _data_run(line_objects: list[LineObject], label_index: int) -> tuple[LineWithWords, ...]:
        """The data directives that follow a label without a break.

        Blank lines never become line objects, and comment-only lines and the later lines of a
        continued line are skipped. Anything else ends the run, including the end of the label's file.
        """
        label = line_objects[label_index]
        run: list[LineWithWords] = []
        for line in line_objects[label_index + 1:]:
            if line.line_id.filename != label.line_id.filename:
                break
            if isinstance(line, DATA_LINE_TYPES) and line.compilable:
                run.append(line)
                continue
            if type(line) is LineObject and line.compilable and line.instruction == '':
                continue
            if isinstance(line, ContinuationLine) and line.compilable:
                continue
            break
        return tuple(run)

    @staticmethod
    def _check_data_size(symbol: AnnotatedSymbol, annotation: Annotation) -> None:
        namespace = annotation.namespace
        try:
            element = namespace.element_words(annotation.arguments)
            expected = namespace.expected_words(annotation.arguments) if element is None else None
        except ValueError as exc:
            raise AssemblerError(annotation.line_id, str(exc))
        if element is not None:
            terminated = namespace.is_terminated(annotation.arguments)
            minimum = 2 if terminated else 1
            if symbol.size >= minimum * element and symbol.size % element == 0:
                # The data sets the count, which then reads like any given argument.
                annotation.arguments[namespace.data_size.times] = symbol.size // element - (minimum - 1)
                if terminated:
                    symbol.terminated.append((annotation, element))
                return
            if symbol.size < minimum * element:
                needs = f'at least one {element}-word element'
                if terminated:
                    needs += f' and a {_terminator_text(element, None)}'
            else:
                needs = f'a whole number of {element}-word elements'
            raise AssemblerError(
                symbol.line_id,
                f"'{symbol.name}' is annotated as {namespace.data_size_basis(annotation.arguments)}, "
                f"which needs {needs}, but {_found_data(symbol.size)} (annotation '{annotation.name}')",
            )
        if expected is None or expected == symbol.size:
            return
        found = _found_data(symbol.size)
        basis = annotation.namespace.data_size_basis(annotation.arguments)
        annotated = (
            f'as {basis}, which needs {_plural(expected, "word")},' if basis
            else f'as {_plural(expected, "word")}'
        )
        raise AssemblerError(
            symbol.line_id,
            f"'{symbol.name}' is annotated {annotated} but {found} (annotation '{annotation.name}')",
        )

    @staticmethod
    def _resolve_symbol_arguments(line: LabelLine, annotation: Annotation) -> None:
        for spec in annotation.namespace.arguments.values():
            if spec.type != 'symbol' or spec.name not in annotation.arguments:
                continue
            target = annotation.arguments[spec.name]
            named_scopes = line.active_named_scopes
            if named_scopes is not None:
                value = named_scopes.named_scope_manager.get_label_value(
                    target, line.symbol_scope, named_scopes, annotation.line_id,
                )
            else:
                value = line.symbol_scope.get_label_value(target, annotation.line_id)
            if value is None:
                raise AssemblerError(
                    annotation.line_id,
                    f"annotation '{annotation.name}': '{spec.name}' names unknown symbol '{target}'",
                )
            annotation.resolved_symbols[spec.name] = value
