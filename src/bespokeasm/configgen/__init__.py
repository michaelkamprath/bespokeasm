import re
from bespokeasm.assembler.model import AssemblerModel


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
        self._model = AssemblerModel(config_file_path, is_verbose)
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
