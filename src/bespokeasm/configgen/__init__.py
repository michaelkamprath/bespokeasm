import re

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.utilities import PATTERN_CONSTANT_SYMBOL
from bespokeasm.utilities import PATTERN_FILE_SYMBOL
from bespokeasm.utilities import PATTERN_GLOBAL_SYMBOL
from bespokeasm.utilities import PATTERN_LOCAL_SYMBOL
from bespokeasm.utilities import PATTERN_SYMBOL


class LanguageConfigGenerator:
    def __init__(
                self,
                config_file_path: str,
                is_verbose: int,
                export_dir: str,
                language_name: str,
                language_version: str,
                code_extension: str,
            ) -> None:
        self._model = AssemblerModel(config_file_path, is_verbose, DiagnosticReporter())
        self._verbose = is_verbose
        self._export_dir = export_dir
        self._language_name = self.model.isa_name if language_name is None else language_name
        self._language_version = self.model.isa_version if language_version is None else language_version
        self._extension = code_extension if code_extension is not None else self.model.assembly_file_extenions

    @property
    def model(self) -> AssemblerModel:
        return self._model

    @property
    def verbose(self) -> int:
        return self._verbose

    @property
    def export_dir(self) -> str:
        return self._export_dir

    @property
    def language_name(self) -> str:
        return self._language_name

    @property
    def language_id(self) -> str:
        return self.language_name + '-assembly'

    @property
    def language_version(self) -> str:
        return self._language_version

    @property
    def code_extension(self) -> str:
        return self._extension

    def _replace_token_with_regex_list(
        self,
        template_str: str,
        token: str,
        item_list: list[str]
    ) -> str:
        # first, convert the item list into individual regex strings, which is
        # mostly escaping any periods or other special characters
        regex_list = [re.escape(item) for item in item_list]
        regex_str = '\\b' + '\\b|\\b'.join(regex_list) + '\\b'
        return template_str.replace(token, regex_str)

    def _replace_token_in_file(self, file_path: str, token_to_replace: str, replacement_string: str):
        """
        Replaces all instances of a specified token within a text file
        with a given replacement string, writing the changes back to the same file.

        Args:
            file_path: The path to the text file.
            token_to_replace: The string to be replaced.
            replacement_string: The string to replace the token with.
        """
        with open(file_path) as file:
            content = file.read()

        modified_content = content.replace(token_to_replace, replacement_string)

        with open(file_path, 'w') as file:
            file.write(modified_content)

    def _label_pattern(self) -> str:
        """Return the unanchored canonical pattern for any scoped symbol."""
        return PATTERN_SYMBOL

    def _constant_pattern(self) -> str:
        """Return the canonical pattern for a constant symbol."""
        return PATTERN_CONSTANT_SYMBOL

    def _global_symbol_pattern(self) -> str:
        """Return the canonical pattern for a global symbol."""
        return PATTERN_GLOBAL_SYMBOL

    def _file_symbol_pattern(self) -> str:
        """Return the canonical pattern for a file-scoped symbol."""
        return PATTERN_FILE_SYMBOL

    def _local_symbol_pattern(self) -> str:
        """Return the canonical pattern for a local symbol."""
        return PATTERN_LOCAL_SYMBOL

    def _replace_symbol_pattern_tokens(self, value):
        """Replace canonical symbol-pattern placeholders recursively."""
        replacements = {
            '##SYMBOL_PATTERN##': self._label_pattern(),
            '##LABEL_PATTERN##': self._label_pattern(),
            '##CONSTANT_PATTERN##': self._constant_pattern(),
            '##GLOBAL_SYMBOL_PATTERN##': self._global_symbol_pattern(),
            '##FILE_SYMBOL_PATTERN##': self._file_symbol_pattern(),
            '##LOCAL_SYMBOL_PATTERN##': self._local_symbol_pattern(),
        }
        if isinstance(value, str):
            for token, pattern in replacements.items():
                value = value.replace(token, pattern)
            return value
        if isinstance(value, list):
            for index, item in enumerate(value):
                value[index] = self._replace_symbol_pattern_tokens(item)
            return value
        if isinstance(value, dict):
            for key, item in value.items():
                value[key] = self._replace_symbol_pattern_tokens(item)
        return value

    def _mnemonic_pattern(self) -> str:
        mnemonics = list(self.model.instruction_mnemonics) + list(self.model.macro_mnemonics)
        if not mnemonics:
            return '(?!)'
        return self._replace_token_with_regex_list('##MNEMONICS##', '##MNEMONICS##', mnemonics)
