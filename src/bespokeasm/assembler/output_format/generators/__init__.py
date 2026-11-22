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
        return ListingPrettyPrinter(context.line_objects, context.model, context.source_file).pretty_print().strip('\n')


def generator_classes() -> dict[str, type[Generator]]:
    from bespokeasm.assembler.output_format.generators.exports import ExportsGenerator
    return {
        cls.name: cls
        for cls in (IntelHexGenerator, HexGenerator, ByteListGenerator, ListingGenerator, ExportsGenerator)
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
