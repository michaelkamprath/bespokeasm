import re

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.configgen.expression_scopes import CURRENT_ADDRESS_PATTERN
from bespokeasm.configgen.expression_scopes import CURRENT_ADDRESS_SCOPE
from bespokeasm.configgen.expression_scopes import LOW_HIGH_OPERATOR_PATTERN
from bespokeasm.configgen.expression_scopes import LOW_HIGH_OPERATOR_SCOPE
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

    def _expression_operator_rules(self) -> list[tuple[str, str]]:
        """(regex, scope) rules for `*` as the current address and `<`/`>` as the low and high
        operators, for the features this instruction set turns on."""
        syntax = self.model.expression_syntax
        rules = []
        if syntax.current_address is not None:
            rules.append((CURRENT_ADDRESS_PATTERN, CURRENT_ADDRESS_SCOPE))
        if syntax.low_high_operators is not None:
            rules.append((LOW_HIGH_OPERATOR_PATTERN, LOW_HIGH_OPERATOR_SCOPE))
        return rules

    def _enclosed_addressing_patterns(self) -> list[tuple[str, int, str, str]]:
        """(enclosure, depth, begin, end) regexes for operands written in parentheses or braces,
        deepest first, for the forms this instruction set configures. Brackets have rules of
        their own in every grammar.

        Braces never appear in an expression, so any `{` in an operand opens one. Parentheses
        also group, and a grammar can't tell `(vec)` from grouping the way the assembler does,
        per instruction, so it colors a parenthesized group as addressing when the group is a
        whole operand: it follows whitespace or a comma and is followed by a comma, a comment or
        the end of the line. `($10+1)*2` stays grouping. One level of inner parentheses is
        recognized."""
        body = r'(?:[^();\n]|\([^();\n]*\))*'
        forms = sorted(
            (form for form in self.model.enclosed_operand_forms if form[0] in ('parentheses', 'braces')),
            key=lambda form: (-form[1], form[0]),
        )
        patterns = []
        for enclosure, depth in forms:
            if enclosure == 'parentheses':
                begin = fr'(?<![^\s,]){"\\(" * depth}(?={body}{"\\)" * depth}\s*(?:[,;]|$))'
                patterns.append((enclosure, depth, begin, r'\)' * depth))
            else:
                patterns.append((enclosure, depth, r'\{' * depth, r'\}' * depth))
        return patterns

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
