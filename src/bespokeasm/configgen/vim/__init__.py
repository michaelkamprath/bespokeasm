import os
from pathlib import Path

from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import EXPRESSION_FUNCTIONS_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.configgen import LanguageConfigGenerator
from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
from bespokeasm.configgen.color_scheme import SyntaxElement


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

    def _get_vim_cterm_approximation(self, hex_color: str) -> int:
        """
        Convert hex color to approximate 256-color terminal color code for VIM.

        This uses a generic RGB-to-256-color mapping algorithm that works for any
        hex color, not just pre-defined ones. The 256-color palette consists of:
        - Colors 0-15: Standard ANSI colors
        - Colors 16-231: 6x6x6 RGB cube (216 colors)
        - Colors 232-255: Grayscale ramp (24 colors)

        Args:
            hex_color: Hex color string (with # prefix, case insensitive)

        Returns:
            Terminal color code (0-255)
        """
        # Parse hex color to RGB components
        hex_color = hex_color.lstrip('#').upper()
        if len(hex_color) != 6:
            return 15  # Default to white for invalid colors

        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except ValueError:
            return 15  # Default to white for invalid hex

        # Check if it's close to grayscale first (colors 232-255)
        # If R, G, B are very close to each other, use grayscale ramp
        if abs(r - g) < 10 and abs(g - b) < 10 and abs(r - b) < 10:
            # Convert to grayscale (average of RGB)
            gray = (r + g + b) // 3
            # Map to 24-step grayscale ramp (232-255)
            # Each step represents about 10.4 gray levels (255/24.6)
            if gray < 8:
                return 16  # Very dark, use black from RGB cube
            elif gray > 247:
                return 231  # Very light, use white from RGB cube
            else:
                # Map to grayscale ramp: 232 + (0-23)
                gray_index = min(23, max(0, (gray - 8) // 10))
                return 232 + gray_index

        # Use 6x6x6 RGB cube (colors 16-231)
        # Each component (R,G,B) is mapped to 6 levels: 0,1,2,3,4,5
        # Formula: 16 + 36*r + 6*g + b (where r,g,b are 0-5)

        # Convert 0-255 RGB values to 0-5 cube coordinates
        # The 6 levels correspond to: 0, 95, 135, 175, 215, 255
        def rgb_to_cube_level(value):
            if value < 48:    # 0-47 -> 0
                return 0
            elif value < 115:  # 48-114 -> 1 (closest to 95)
                return 1
            elif value < 155:  # 115-154 -> 2 (closest to 135)
                return 2
            elif value < 195:  # 155-194 -> 3 (closest to 175)
                return 3
            elif value < 235:  # 195-234 -> 4 (closest to 215)
                return 4
            else:             # 235-255 -> 5 (closest to 255)
                return 5

        r_cube = rgb_to_cube_level(r)
        g_cube = rgb_to_cube_level(g)
        b_cube = rgb_to_cube_level(b)

        # Calculate color index in 6x6x6 cube
        color_index = 16 + (36 * r_cube) + (6 * g_cube) + b_cube

        return min(231, max(16, color_index))

    def _generate_vim_color_lines(self, lang_group: str) -> list:
        """
        Generate VIM color highlight lines by mapping generic syntax elements
        to VIM-specific highlighting groups.

        Args:
            lang_group: Language group prefix for VIM syntax highlighting

        Returns:
            List of VIM highlight command strings
        """
        lines = []

        # Set overall editor colors using Normal highlight group
        bg_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BACKGROUND)
        fg_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.FOREGROUND)
        bg_cterm = self._get_vim_cterm_approximation(bg_color)
        fg_cterm = self._get_vim_cterm_approximation(fg_color)
        lines.append(f'hi Normal guifg={fg_color} guibg={bg_color} ctermfg={fg_cterm} ctermbg={bg_cterm}')

        # Set selection colors
        selection_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.SELECTION)
        selection_cterm = self._get_vim_cterm_approximation(selection_color)
        lines.append(f'hi Visual guibg={selection_color} ctermbg={selection_cterm}')

        # Set current line highlighting
        line_highlight_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.LINE_HIGHLIGHT)
        line_highlight_cterm = self._get_vim_cterm_approximation(line_highlight_color)
        lines.append(f'hi CursorLine guibg={line_highlight_color} ctermbg={line_highlight_cterm} cterm=NONE gui=NONE')

        # Mapping from generic syntax elements to VIM highlight groups
        vim_mappings = [
            (f'{lang_group}HexNumber', SyntaxElement.HEX_NUMBER),
            (f'{lang_group}BinNumber', SyntaxElement.BINARY_NUMBER),
            (f'{lang_group}DecNumber', SyntaxElement.DECIMAL_NUMBER),
            (f'{lang_group}CharNumber', SyntaxElement.CHARACTER_NUMBER),
            (f'{lang_group}LabelName', SyntaxElement.LABEL_NAME),
            (f'{lang_group}LabelColon', SyntaxElement.PUNCTUATION_LABEL_COLON),
            (f'{lang_group}String', SyntaxElement.STRING),
            (f'{lang_group}StringPunc', SyntaxElement.PUNCTUATION_STRING),
            (f'{lang_group}Escape', SyntaxElement.STRING_ESCAPE),
            (f'{lang_group}Comment', SyntaxElement.COMMENT),
            (f'{lang_group}Instruction', SyntaxElement.INSTRUCTION),
            (f'{lang_group}Macro', SyntaxElement.MACRO),
            (f'{lang_group}Register', SyntaxElement.REGISTER),
            (f'{lang_group}ConstName', SyntaxElement.CONSTANT_NAME),
            (f'{lang_group}CompilerLabel', SyntaxElement.COMPILER_LABEL),
            (f'{lang_group}PreProc', SyntaxElement.PREPROCESSOR),
            (f'{lang_group}PreProcPunc', SyntaxElement.PUNCTUATION_PREPROCESSOR),
            (f'{lang_group}DataType', SyntaxElement.DATA_TYPE),
            (f'{lang_group}Operator', SyntaxElement.OPERATOR),
            (f'{lang_group}Directive', SyntaxElement.DIRECTIVE),
        ]

        # Generate standard color lines with background color inheritance
        for vim_name, syntax_element in vim_mappings:
            hex_color = DEFAULT_COLOR_SCHEME.get_color(syntax_element)
            cterm_color = self._get_vim_cterm_approximation(hex_color)
            # Use NONE for background to inherit from Normal highlight group
            lines.append(f'hi {vim_name} guifg={hex_color} guibg=NONE ctermfg={cterm_color} ctermbg=NONE')

        # Special colors with styling (brackets get bold formatting)
        bracket_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BRACKET)
        bracket_cterm = self._get_vim_cterm_approximation(bracket_color)
        lines.append(f'hi {lang_group}Bracket guifg={bracket_color} guibg=NONE ctermfg={bracket_cterm} \
ctermbg=NONE gui=bold cterm=bold')

        double_bracket_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.DOUBLE_BRACKET)
        double_bracket_cterm = self._get_vim_cterm_approximation(double_bracket_color)
        lines.append(f'hi {lang_group}DoubleBracket guifg={double_bracket_color} guibg=NONE ctermfg={double_bracket_cterm} \
ctermbg=NONE gui=bold cterm=bold')

        paren_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.PARENTHESIS)
        paren_cterm = self._get_vim_cterm_approximation(paren_color)
        lines.append(f'hi {lang_group}Paren guifg={paren_color} guibg=NONE ctermfg={paren_cterm} ctermbg=NONE')

        return lines

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
        # Strings (double and single quoted) - only allow escape sequences inside
        # This prevents all keywords and other syntax elements from being highlighted within strings
        lines.append(f'syn region {lang_group}String matchgroup={lang_group}StringPunc start=+"+ \
skip=+\\.+ end=+"+ oneline contains={lang_group}Escape')
        lines.append(f"syn region {lang_group}String matchgroup={lang_group}StringPunc start=+'+ \
skip=+\\.+ end=+'+ oneline contains={lang_group}Escape")
        # Escapes inside strings
        lines.append(
            fr"syn match {lang_group}Escape /\\x[0-9A-Fa-f]\{{2}}\|\\o[0-7]\{{2}}\|\\[abfnrtv\"']\|\\\\/ contained"
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
            # Highlight the leading '#' separately as punctuation and chain to macro name
            lines.append(fr'syn match {lang_group}PreProcPunc /^#/ nextgroup={lang_group}PreProc skipwhite')
            # Highlight the macro name as a contained match following '#'
            for w in preproc_directives:
                lines.append(fr'syn match {lang_group}PreProc /\<' + self._vim_escape(w) + r'\>/ contained')
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
        # BespokeASM color scheme from central configuration
        color_lines = self._generate_vim_color_lines(lang_group)
        lines.extend(color_lines)
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
