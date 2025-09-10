import os
from pathlib import Path

from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import EXPRESSION_FUNCTIONS_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.configgen import LanguageConfigGenerator


class VimConfigGenerator(LanguageConfigGenerator):
    def __init__(
                self,
                config_file_path: str,
                is_verbose: int,
                vim_config_dir: str,
                language_name: str,
                language_version: str,
                code_extension: str,
            ) -> None:
        super().__init__(config_file_path, is_verbose, vim_config_dir, language_name, language_version, code_extension)

    def generate(self) -> None:
        syntax_dir_path = os.path.join(self.export_dir, 'syntax')
        ftdetect_dir_path = os.path.join(self.export_dir, 'ftdetect')

        Path(syntax_dir_path).mkdir(parents=True, exist_ok=True)
        Path(ftdetect_dir_path).mkdir(parents=True, exist_ok=True)

        if self.verbose >= 1:
            print(f'Generating Vim syntax files for language "{self.language_id}" into: {self.export_dir}')

        # Sanitize Vim filetype: lowercase, no dashes
        vim_filetype = self.language_id.replace('-', '').lower()

        syntax_fp = os.path.join(syntax_dir_path, f'{vim_filetype}.vim')
        ftdetect_fp = os.path.join(ftdetect_dir_path, f'{vim_filetype}.vim')

        syntax_text = self._build_syntax_vim(vim_filetype)
        with open(syntax_fp, 'w', encoding='utf-8') as f:
            f.write(syntax_text)
            if self.verbose > 1:
                print(f'  generated {os.path.basename(syntax_fp)}')

        ftdetect_text = self._build_ftdetect_vim(vim_filetype)
        with open(ftdetect_fp, 'w', encoding='utf-8') as f:
            f.write(ftdetect_text)
            if self.verbose > 1:
                print(f'  generated {os.path.basename(ftdetect_fp)}')

    def _vim_escape(self, token: str) -> str:
        # Escape Vim regex special chars
        # Escape backslash first
        escaped = token.replace('\\', '\\\\')
        for ch in ['.', '+', '*', '?', '^', '$', '(', ')', '[', ']', '{', '}', '|', '-']:
            escaped = escaped.replace(ch, '\\' + ch)
        return escaped

    def _alternation(self, items: list[str]) -> str:
        if len(items) == 0:
            return ''
        return '\\%(' + '\\|'.join([self._vim_escape(it) for it in items]) + '\\)'

    def _join_keywords(self, items: list[str]) -> str:
        # space-separated; do not escape to allow Vim to treat each as a keyword
        return ' '.join(items)

    def _build_syntax_vim(self, vim_filetype: str) -> str:
        # Collect token groups
        instructions = list(self.model.instruction_mnemonics)
        macros = list(self.model.macro_mnemonics)
        registers = list(self.model.registers)
        predefined_labels = list(self.model.predefined_labels)

        # Directives and datatypes prefixed with '.'
        compiler_directives = ['.' + d for d in COMPILER_DIRECTIVES_SET]
        data_types = ['.' + d for d in BYTECODE_DIRECTIVES_SET]

        # Preprocessor directives (sorted by length desc to avoid prefix shadowing)
        preproc_directives = sorted(list(PREPROCESSOR_DIRECTIVES_SET), key=len, reverse=True)

        expr_functions = list(EXPRESSION_FUNCTIONS_SET)

        # Build vim regex alternations
        directives_words = [d.lstrip('.') for d in compiler_directives]
        datatypes_words = [d.lstrip('.') for d in data_types]
        # We'll emit separate syn match lines for each directive to keep patterns simple
        preproc_alt = self._alternation(preproc_directives)
        registers_kw = self._join_keywords(registers)
        instructions_alt = self._alternation(instructions)
        macros_alt = self._alternation(macros)
        # Add word boundary to each label alternative as well
        if predefined_labels:
            labels_alt = '\\%(' + '\\|'.join([self._vim_escape(w) + r'\>' for w in predefined_labels]) + '\\)'
        else:
            labels_alt = ''
        expr_funcs_alt = self._alternation(expr_functions)

        lang_group = vim_filetype

        lines: list[str] = []
        lines.append('if exists("b:current_syntax")')
        lines.append('  finish')
        lines.append('endif')
        lines.append('')
        lines.append('syn case ignore')
        lines.append('')
        # Comments
        lines.append(f'syn match {lang_group}Comment /;.*/ contains=@Spell')
        # Strings (double and single quoted) - restrict to one line to avoid swallowing following lines
        # lines.append(f'syn region {lang_group}String start=+"+ skip=+\\"+ end=+"+ oneline contains={lang_group}Escape')
        # lines.append(f"syn region {lang_group}String start=+'+ skip=+\\'+ end=+'+ oneline contains={lang_group}Escape")
        lines.append(fr'syn match {lang_group}String /"[^"\\]*\(\\"[^"\\]*\)*"/')
        # Escapes inside strings
        lines.append(
            fr"syn match {lang_group}Escape /\\\|\\\"\|\\'\|\\[abfnrtv]\|\\o[0-7]\{{2}}\|\\x[0-9A-Fa-f]\{{2}}/ contained"
        )
        # Numbers (split for per-type coloring)
        # - Ensure prefixes like '$' and '%' are included in the match
        # - Prevent numbers from being highlighted inside strings
        lines.append(fr'syn match {lang_group}HexNumber /\$\x\+\>/')
        lines.append(fr'syn match {lang_group}HexNumber /\<0x\x\+\>/')
        lines.append(fr'syn match {lang_group}HexNumber /\<[0-9A-Fa-f]\+H\>/')
        lines.append(fr'syn match {lang_group}BinNumber /\%\(b\|%\)[01]\+\>/')
        lines.append(fr'syn match {lang_group}DecNumber /\<\d\+\>/')
        lines.append(f"syn match {lang_group}CharNumber /'.'/")
        # Labels
        lines.append(fr'syn match {lang_group}LabelName /^\s*\%(' + '\\.' + '\\w\\+\\|_\\w\\+\\|\\w\\+\\)\\s*\\ze:/ contained')
        lines.append(fr'syn match {lang_group}LabelColon /:/ contained')
        lines.append(
            fr'syn match {lang_group}LabelName /^\s*\%('
            + '\\.'
            + f'\\w\\+\\|_\\w\\+\\|\\w\\+\\)\\s*:/ contains={lang_group}LabelName,{lang_group}LabelColon'
        )

        # Constant assignments (name before '=' or EQU at start-of-line)
        lines.append(fr'syn match {lang_group}ConstName /^\s*\zs\w\+\ze\s*\%(=\|EQU\)/')
        lines.append(fr'syn match {lang_group}AssignOp /^\s*\w\+\s*\zs\%(=\|EQU\)/')
        # Directives and datatypes
        for w in directives_words:
            lines.append(fr'syn match {lang_group}Directive /\s*\.' + self._vim_escape(w) + r'\>/')
        for w in datatypes_words:
            lines.append(fr'syn match {lang_group}DataType /\s*\.' + self._vim_escape(w) + r'\>/')
        # Preprocessor
        if preproc_alt:
            # Emit one rule per directive so tests can match `<pp>\>/` at end of pattern
            for w in preproc_directives:
                lines.append(fr'syn match {lang_group}PreProc /^#' + self._vim_escape(w) + r'\>/')
        # Expression functions
        if expr_funcs_alt:
            lines.append(fr'syn match {lang_group}Operator /\<' + expr_funcs_alt + r'\>/')
        # Operators
        lines.append(rf'syn match {lang_group}Operator /==\|!=\|>=\|<=\|>>\|<<\|[+\-*/&|^]/')
        # Registers
        if registers_kw:
            lines.append(f'syn keyword {lang_group}Register ' + registers_kw)
        # Instructions and macros
        if instructions_alt:
            lines.append(fr'syn match {lang_group}Instruction /\<' + instructions_alt + r'\>/')
        if macros_alt:
            lines.append(fr'syn match {lang_group}Macro /\<' + macros_alt + r'\>/')
        # Compiler predefined labels
        if labels_alt:
            lines.append(fr'syn match {lang_group}CompilerLabel /\<' + labels_alt + r'/')

        # Punctuation
        lines.append(fr'syn match {lang_group}Bracket /\[\|\]/')
        lines.append(fr'syn match {lang_group}DoubleBracket /\[\[\|\]\]/')
        lines.append(fr'syn match {lang_group}Paren /(\|)/')

        lines.append('')
        # Base links (fallbacks if explicit colors below are not supported)
        lines.append(f'hi def link {lang_group}Comment Comment')
        lines.append(f'hi def link {lang_group}String String')
        lines.append(f'hi def link {lang_group}HexNumber Number')
        lines.append(f'hi def link {lang_group}BinNumber Number')
        lines.append(f'hi def link {lang_group}DecNumber Number')
        lines.append(f'hi def link {lang_group}CharNumber Number')
        lines.append(f'hi def link {lang_group}LabelName Label')
        lines.append(f'hi def link {lang_group}LabelColon Delimiter')
        lines.append(f'hi def link {lang_group}Directive Statement')
        lines.append(f'hi def link {lang_group}DataType Type')
        lines.append(f'hi def link {lang_group}PreProc PreProc')
        lines.append(f'hi def link {lang_group}Operator Operator')
        lines.append(f'hi def link {lang_group}Register Identifier')
        lines.append(f'hi def link {lang_group}Instruction Keyword')
        lines.append(f'hi def link {lang_group}Macro Keyword')
        lines.append(f'hi def link {lang_group}ConstName Constant')
        lines.append(f'hi def link {lang_group}AssignOp Operator')
        lines.append(f'hi def link {lang_group}Escape SpecialChar')
        # Explicit BespokeASM-inspired colors (GUI + cterm approximations)
        lines.append(f'hi {lang_group}HexNumber guifg=#ffe80b ctermfg=220')
        lines.append(f'hi {lang_group}BinNumber guifg=#d6d300 ctermfg=184')
        lines.append(f'hi {lang_group}DecNumber guifg=#fffd80 ctermfg=229')
        lines.append(f'hi {lang_group}CharNumber guifg=#FFE880 ctermfg=222')
        lines.append(f'hi {lang_group}LabelName guifg=#278ed8 ctermfg=67')
        lines.append(f'hi {lang_group}LabelColon guifg=#ed80a2 ctermfg=176')
        lines.append(f'hi {lang_group}String guifg=#aaff4d ctermfg=148')
        lines.append(f'hi {lang_group}Escape guifg=#7ab736 ctermfg=106')
        lines.append(f'hi {lang_group}Comment guifg=#568c3b ctermfg=65')
        lines.append(f'hi {lang_group}Instruction guifg=#ffa83f ctermfg=215')
        lines.append(f'hi {lang_group}Macro guifg=#ff883f ctermfg=208')
        lines.append(f'hi {lang_group}Register guifg=#2ea9d2 ctermfg=38')
        lines.append(f'hi {lang_group}ConstName guifg=#abd7ed ctermfg=153')
        lines.append(f'hi {lang_group}CompilerLabel guifg=#abedc1 ctermfg=151')
        lines.append(f'hi {lang_group}PreProc guifg=#c080ff ctermfg=141')
        lines.append(f'hi {lang_group}DataType guifg=#d6adff ctermfg=183')
        lines.append(f'hi {lang_group}Operator guifg=#cc99ff ctermfg=177')
        lines.append(f'hi {lang_group}Directive guifg=#c080ff ctermfg=141')
        # Punctuation coloring similar to Sublime
        lines.append(f'hi {lang_group}Bracket guifg=#b72dd2 ctermfg=171 gui=bold cterm=bold')
        lines.append(f'hi {lang_group}DoubleBracket guifg=#d22d9b ctermfg=169 gui=bold cterm=bold')
        lines.append(f'hi {lang_group}Paren guifg=#dc81e4 ctermfg=176')
        # Do not relink CompilerLabel after assigning explicit colors above, to avoid
        # overriding the custom palette with a generic Constant link.
        lines.append('')
        lines.append(f'let b:current_syntax = "{vim_filetype}"')

        return '\n'.join(lines) + '\n'

    def _build_ftdetect_vim(self, vim_filetype: str) -> str:
        ext = self.code_extension
        guard = f'g:did_bespokeasm_ftdetect_{vim_filetype}'
        lines = [
            f'if exists("{guard}") | finish | endif',
            f'let {guard} = 1',
            f'autocmd BufRead,BufNewFile *.{ext} setfiletype {vim_filetype}',
            '',
        ]
        return '\n'.join(lines)
