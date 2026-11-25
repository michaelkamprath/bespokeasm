"""The built-in ``-t symbols`` format: every label and constant as JSON.

Other tools can read annotations from this file without a config-defined output
format. The layout is versioned by ``format_version``; add fields freely, but change
or remove one only with a new version.
"""
import json
import os

from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.assembler.annotations.model import AnnotatedSymbol
from bespokeasm.assembler.annotations.model import ExportModel
from bespokeasm.assembler.annotations.model import symbol_scope_name
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase

SYMBOLS_FORMAT_NAME = 'bespokeasm-symbols'
SYMBOLS_FORMAT_VERSION = 1


class SymbolsPrettyPrinter(PrettyPrinterBase):
    """Writes the configuration's predefined symbols, then the source's in definition order."""

    def __init__(
        self,
        line_objs: list[LineObject],
        model: AssemblerModel,
        main_filename: str,
        export_model: ExportModel | None,
        source_line_objects: list[LineObject] | None,
    ) -> None:
        super().__init__(line_objs, model)
        self._main_filename = main_filename
        self._export_model = export_model if export_model is not None else ExportModel([])
        self._source_line_objects = source_line_objects if source_line_objects is not None else line_objs

    def pretty_print(self) -> str:
        document = {
            'format': SYMBOLS_FORMAT_NAME,
            'format_version': SYMBOLS_FORMAT_VERSION,
            'bespokeasm_version': BESPOKEASM_VERSION_STR,
            'isa': {
                'name': self.model.isa_name,
                'version': self.model.isa_version,
                'word_size': self.model.word_size,
                'address_size': self.model.address_size,
            },
            'source_file': os.path.basename(self._main_filename),
            'symbols': self._predefined_symbols() + self._source_symbols(),
            # Every #verbatim block, in source order, with its text as formats write it.
            'verbatim': [
                {
                    'namespace': block.namespace,
                    'file': self._display_path(block.line_id.filename),
                    'line': block.line_id.line_num,
                    'text': block.text,
                }
                for block in self._export_model.verbatim_blocks
            ],
        }
        return json.dumps(document, indent=2)

    def _predefined_symbols(self) -> list[dict]:
        """Symbols the ISA configuration defines, attributed to the configuration file (no line number)."""
        config_file = os.path.basename(self.model.config_file_path)
        symbols = []
        for constant in self.model.predefined_constants:
            symbols.append(self._entry(constant['name'], 'constant', 'global', constant['value'], config_file, None))
        for data in self.model.predefined_data_blocks:
            symbols.append(self._entry(data['name'], 'label', 'global', data['address'], config_file, None))
        return symbols

    def _source_symbols(self) -> list[dict]:
        annotated = {
            (symbol.line_id.filename, symbol.line_id.line_num, symbol.name): symbol
            for symbol in self._export_model.symbols
        }
        symbols = []
        for line in self._source_line_objects:
            if not isinstance(line, LabelLine) or not line.compilable:
                continue
            name = line.get_label()
            entry = self._entry(
                name,
                'constant' if line.is_constant else 'label',
                symbol_scope_name(name),
                line.get_value(),
                self._display_path(line.line_id.filename),
                line.line_id.line_num,
            )
            symbol = annotated.get((line.line_id.filename, line.line_id.line_num, name))
            if symbol is not None:
                self._add_annotations(entry, symbol)
            symbols.append(entry)
        return symbols

    @staticmethod
    def _entry(name: str, kind: str, scope: str, value: int, file: str | None, line: int | None) -> dict:
        return {
            'name': name,
            'kind': kind,
            'scope': scope,
            'value': value,
            'file': file,
            'line': line,
            'annotations': {},
        }

    @staticmethod
    def _add_annotations(entry: dict, symbol: AnnotatedSymbol) -> None:
        entry['annotations'] = {
            name: {
                'arguments': dict(annotation.arguments),
                'resolved_symbols': dict(annotation.resolved_symbols),
            }
            for name, annotation in symbol.annotations.items()
        }
        if symbol.is_label:
            entry['data'] = {
                'size': symbol.size,
                'words': [word.value for word in symbol.words],
            }

    def _display_path(self, filename: str) -> str:
        """A source path relative to the main file's directory, so the output does not depend on the cwd."""
        base = os.path.dirname(os.path.abspath(self._main_filename))
        relative = os.path.relpath(os.path.abspath(filename), base)
        return filename if relative.startswith('..') else relative
