from bespokeasm.assembler.annotations.model import Annotation
from bespokeasm.assembler.annotations.parser import parse_annotation_directive
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel


class AnnotationLine(PreprocessorLine):
    """An ``#annotate`` directive. It emits nothing and occupies no address.

    The arguments are validated against the namespace's declaration when the line is
    parsed; the annotation is attached to the next label or constant definition by
    ``AnnotationBinder``. A directive continued over several lines is parsed from ``directive``,
    the joined text, while ``instruction`` is its first line as written, for the listing.
    """

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        isa_model: AssemblerModel,
        directive: str | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        namespace_name, raw_arguments = parse_annotation_directive(
            line_id, instruction if directive is None else directive,
        )
        namespace = isa_model.annotation_namespaces.get(namespace_name)
        if namespace is None:
            defined = ', '.join(sorted(isa_model.annotation_namespaces))
            raise AssemblerError(
                line_id,
                f"this instruction set does not define annotation '{namespace_name}'; "
                f'defined annotations: {defined}',
            )
        self._annotation = Annotation(
            namespace=namespace,
            arguments=namespace.validate_arguments(raw_arguments, line_id, isa_model.default_numeric_base),
            line_id=line_id,
        )

    def __repr__(self) -> str:
        return f'AnnotationLine<{self._annotation.name}: {self._annotation.arguments}>'

    @property
    def annotation(self) -> Annotation:
        return self._annotation
