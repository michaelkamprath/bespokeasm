"""Section generators for config-defined output formats.

Each section of a format names one generator and sets its options. Options are
checked when the configuration loads: a missing required option, an unknown option, a
bad value, or a generator that cannot work with the ISA's word size is a config error.
A generator's text never starts or ends with a blank line; the template decides spacing.
"""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar
from typing import NoReturn

from bespokeasm.assembler.annotations.schema import AnnotationNamespace
from bespokeasm.assembler.output_format.base import RenderContext


@dataclass
class LoadEnvironment:
    """What a generator may know about the configuration while it is loaded."""
    annotation_namespaces: dict[str, AnnotationNamespace]
    word_size: int
    error: Callable[[str, str], NoReturn]
    warn: Callable[[str, str], None]
    # Checks a format's or shared set's ``predefined`` mapping at the given path.
    check_predefined: Callable[[Any, str], None] | None = None
    # Names the top-level ``predefined`` section already uses, per kind
    # (``memory_zones``, ``constants``), mapped to a description such as "predefined constant".
    predefined_names: dict[str, dict[str, str]] = field(default_factory=dict)


class Generator(ABC):
    name: ClassVar[str]
    required_options: ClassVar[frozenset[str]] = frozenset()
    optional_options: ClassVar[frozenset[str]] = frozenset()
    required_word_size: ClassVar[int | None] = None

    def __init__(
        self,
        format_name: str,
        section_name: str,
        options: dict[str, Any],
        env: LoadEnvironment,
        path: str | None = None,
        option_paths: dict[str, str] | None = None,
    ) -> None:
        """``option_paths`` gives the config path of each option that a shared set supplied,
        so an error names the key where the value was written."""
        self.format_name = format_name
        self.section_name = section_name
        self.path = path or f'output_formats.{format_name}.sections.{section_name}'
        self.option_paths = dict(option_paths or {})
        self.env = env
        for option in options:
            if option not in self.required_options | self.optional_options:
                allowed = sorted(self.required_options | self.optional_options)
                takes = f'takes {", ".join(allowed)}' if allowed else 'takes no options'
                env.error(self.option_path(option), f"is not an option of generator '{self.name}', which {takes}")
        for option in sorted(self.required_options):
            if option not in options:
                env.error(self.path, f"uses generator '{self.name}', which requires option '{option}'")
        if self.required_word_size is not None and env.word_size != self.required_word_size:
            env.error(
                self.path,
                f"uses generator '{self.name}', which needs {self.required_word_size}-bit words; "
                f'this instruction set has {env.word_size}-bit words',
            )
        self.configure(options)

    def option_path(self, option: str) -> str:
        """The config path of an option, or of a key inside one (``lines.addr``)."""
        root, _, rest = option.partition('.')
        base = self.option_paths.get(root, f'{self.path}.{root}')
        return f'{base}.{rest}' if rest else base

    def error(self, option: str | None, problem: str) -> NoReturn:
        self.env.error(self.option_path(option) if option else self.path, problem)

    def configure(self, options: dict[str, Any]) -> None:
        """Read and check the options. Called after the common checks."""

    @abstractmethod
    def render(self, context: RenderContext) -> str:
        """Return the section text, with no leading or trailing blank lines."""


class IntelHexGenerator(Generator):
    name = 'intel_hex'
    required_word_size = 8

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.pretty_printer.intelhex import IntelHexPrettyPrinter
        return IntelHexPrettyPrinter(context.line_objects, context.model, True).pretty_print().strip('\n')


class HexGenerator(Generator):
    name = 'hex'
    required_word_size = 8

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.pretty_printer.intelhex import IntelHexPrettyPrinter
        return IntelHexPrettyPrinter(context.line_objects, context.model, False).pretty_print().strip('\n')


class ByteListGenerator(Generator):
    name = 'byte_list'
    required_word_size = 8

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.bytecode.word import Word
        from bespokeasm.assembler.line_object import LineWithWords

        values: list[str] = []
        for line in context.line_objects:
            if isinstance(line, LineWithWords) and not line.is_muted:
                values.extend(f'0x{byte:02x}' for byte in Word.words_to_bytes(line.get_words()))
        return ', '.join(values)


class ListingGenerator(Generator):
    name = 'listing'

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter
        return ListingPrettyPrinter(
            context.line_objects, context.model, context.source_file, context.export_model,
        ).pretty_print().strip('\n')


class RowsGenerator(Generator):
    """Rows of bytes, with an address line at each ``.org``.

    Each row starts with ``row_prefix`` and holds up to ``bytes_per_row`` bytes, each written
    with the ``byte`` template (field ``byte``). At each ``.org`` the current row ends and the
    ``org_line`` template (field ``address``) is written on its own line. Muted lines are skipped.
    """
    name = 'rows'
    required_options = frozenset({'bytes_per_row', 'row_prefix', 'byte', 'org_line'})
    required_word_size = 8

    def configure(self, options: dict[str, Any]) -> None:
        from bespokeasm.assembler.output_format.template import Template

        bytes_per_row = options['bytes_per_row']
        if isinstance(bytes_per_row, bool) or not isinstance(bytes_per_row, int) or bytes_per_row < 1:
            self.error('bytes_per_row', 'must be a positive whole number')
        self.bytes_per_row = bytes_per_row
        if not isinstance(options['row_prefix'], str):
            self.error('row_prefix', 'must be a string')
        self.row_prefix = options['row_prefix']
        self.byte = Template.parse(options['byte'], {'byte': 0}, lambda problem: self.error('byte', problem))
        self.org_line = Template.parse(
            options['org_line'], {'address': 0}, lambda problem: self.error('org_line', problem),
        )

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.bytecode.word import Word
        from bespokeasm.assembler.line_object import LineWithWords
        from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine

        lines: list[str] = []
        row: list[str] = []

        def end_row() -> None:
            if row:
                lines.append(self.row_prefix + ''.join(row))
                row.clear()

        for line in context.line_objects:
            if isinstance(line, LineWithWords) and not line.is_muted:
                for value in Word.words_to_bytes(line.get_words(), False, 'big'):
                    row.append(self.byte.render({'byte': value}))
                    if len(row) == self.bytes_per_row:
                        end_row()
            elif isinstance(line, AddressOrgLine):
                end_row()
                lines.append(self.org_line.render({'address': line.address}))
        end_row()
        return '\n'.join(lines)


class ByteLinesGenerator(Generator):
    """A table with one row per assembled byte, in address order, using the shared column model.

    Fields: ``label`` (the labels at that byte's address, on the line's first byte, else empty),
    ``address``, ``byte``, ``source`` (the line's instruction text, on its first byte only) and
    ``comment`` (the same). Only bytes from source are listed: predefined data blocks from the
    ISA configuration are not. Muted lines are skipped.
    """
    name = 'byte_lines'
    required_options = frozenset({'columns'})
    optional_options = frozenset({'separator', 'header_rule', 'rule_separator'})
    required_word_size = 8
    FIELDS = {'label': 'x', 'address': 0, 'byte': 0, 'source': 'x', 'comment': 'x'}

    def configure(self, options: dict[str, Any]) -> None:
        from bespokeasm.assembler.output_format.columns import ColumnTable

        self.table = ColumnTable.load(
            options['columns'], options.get('separator'), self.FIELDS,
            lambda option, problem: self.error(option, problem),
            header_rule=options.get('header_rule'),
            rule_separator=options.get('rule_separator'),
            warn=lambda option, problem: self.env.warn(self.option_path(option), problem),
        )

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.bytecode.word import Word
        from bespokeasm.assembler.line_object import LineWithWords
        from bespokeasm.assembler.line_object.label_line import LabelLine
        from bespokeasm.assembler.line_object.predefined_data import PredefinedDataLine

        rows: list[dict[str, Any]] = []
        labels: list[LabelLine] = []
        for line in context.line_objects:
            if line.is_muted or isinstance(line, PredefinedDataLine):
                continue
            if isinstance(line, LabelLine):
                if not line.is_constant:
                    labels.append(line)
                continue
            if not isinstance(line, LineWithWords) or line.word_count == 0:
                continue
            # Labels name the first byte at their address; one left behind by an .org names nothing.
            names = [label.get_label() for label in labels if label.address == line.address]
            labels.clear()
            for offset, value in enumerate(Word.words_to_bytes(line.get_words(), False, 'big')):
                first = offset == 0
                rows.append({
                    'label': ' '.join(names) if first and names else None,
                    'address': line.address + offset,
                    'byte': value,
                    'source': line.instruction.strip() if first else None,
                    'comment': (line.comment or '').strip() if first else None,
                })
        return self.table.render(rows)


class VerbatimGenerator(Generator):
    """Every ``#verbatim`` block of one annotation namespace, in source order, joined by
    ``separator`` (default: one blank line between blocks)."""
    name = 'verbatim'
    required_options = frozenset({'namespace'})
    optional_options = frozenset({'separator'})

    def configure(self, options: dict[str, Any]) -> None:
        namespace = options['namespace']
        spec = self.env.annotation_namespaces.get(namespace) if isinstance(namespace, str) else None
        if spec is None or not spec.accepts_verbatim:
            accepting = sorted(name for name, item in self.env.annotation_namespaces.items() if item.accepts_verbatim)
            which = (
                f'namespaces that do: {", ".join(accepting)}' if accepting
                else 'no annotation namespace of this configuration does (set verbatim on one)'
            )
            self.error('namespace', f"names '{namespace}', which does not accept #verbatim blocks; {which}")
        self.verbatim_namespace = namespace
        self.separator = options.get('separator', '\n\n')
        if not isinstance(self.separator, str):
            self.error('separator', 'must be a string, such as "\\n\\n"')

    def render(self, context: RenderContext) -> str:
        texts = [block.text for block in context.export_model.verbatim_for(self.verbatim_namespace) if block.text]
        return self.separator.join(texts)


def generator_classes() -> dict[str, type[Generator]]:
    from bespokeasm.assembler.output_format.generators.exports import ExportsGenerator
    return {
        cls.name: cls
        for cls in (
            IntelHexGenerator, HexGenerator, ByteListGenerator, ListingGenerator, RowsGenerator, ByteLinesGenerator,
            ExportsGenerator, VerbatimGenerator,
        )
    }


def build_generator(
    format_name: str,
    section_name: str,
    config: Any,
    env: LoadEnvironment,
    path: str | None = None,
    option_paths: dict[str, str] | None = None,
) -> Generator:
    path = path or f'output_formats.{format_name}.sections.{section_name}'
    option_paths = option_paths or {}
    if not isinstance(config, dict):
        env.error(path, 'must be a mapping with a generator and its options')
    generator_name = config.get('generator')
    classes = generator_classes()
    if generator_name not in classes:
        if generator_name is None:
            env.error(f'{path}.generator', f'is required; generators are {", ".join(sorted(classes))}')
        env.error(
            option_paths.get('generator', f'{path}.generator'),
            f"names unknown generator '{generator_name}'; generators are {', '.join(sorted(classes))}",
        )
    options = {key: value for key, value in config.items() if key != 'generator'}
    return classes[generator_name](format_name, section_name, options, env, path, option_paths)
