"""
Central color scheme configuration for BespokeASM syntax highlighting.

This module defines color hex values for generic syntax elements used across
all editor syntax highlighting generators. Each editor module is responsible
for mapping these generic elements to their specific highlighting constructs.

The color scheme provides clear visual distinction between different syntax
elements while maintaining good readability across all supported editors.
"""
from dataclasses import dataclass
from enum import Enum


class SyntaxElement(Enum):
    """Enumeration of all generic syntax elements that can be highlighted."""

    # Global/theme colors
    BACKGROUND = 'background'
    FOREGROUND = 'foreground'
    CARET = 'caret'
    SELECTION = 'selection'
    LINE_HIGHLIGHT = 'line_highlight'

    # Number literals
    HEX_NUMBER = 'hex_number'
    BINARY_NUMBER = 'binary_number'
    DECIMAL_NUMBER = 'decimal_number'
    CHARACTER_NUMBER = 'character_number'

    # Labels and identifiers
    LABEL_NAME = 'label_name'
    LABEL_DEFINITION = 'label_definition'
    LABEL_USAGE = 'label_usage'
    PUNCTUATION_LABEL_COLON = 'label_colon'

    # Strings and escapes
    STRING = 'string'
    STRING_ESCAPE = 'string_escape'
    PUNCTUATION_STRING = 'string_punctuation'

    # Comments
    COMMENT = 'comment'

    # Instructions and functions
    INSTRUCTION = 'instruction'
    MACRO = 'macro'

    # Variables and constants
    REGISTER = 'register'
    CONSTANT_NAME = 'constant_name'
    CONSTANT_DEFINITION = 'constant_definition'
    CONSTANT_USAGE = 'constant_usage'
    COMPILER_LABEL = 'compiler_label'
    PARAMETER = 'parameter'

    # Preprocessor and directives
    PREPROCESSOR = 'preprocessor'
    DATA_TYPE = 'data_type'
    DIRECTIVE = 'directive'

    # Operators
    OPERATOR = 'operator'

    # Punctuation
    PUNCTUATION_SEPARATOR = 'punctuation_separator'
    PUNCTUATION_VARIABLE = 'punctuation_variable'
    PUNCTUATION_PREPROCESSOR = 'punctuation_preprocessor'

    # Special punctuation (may have additional styling like bold)
    BRACKET = 'bracket'
    DOUBLE_BRACKET = 'double_bracket'
    PARENTHESIS = 'parenthesis'


@dataclass
class ColorScheme:
    """Central color scheme configuration for all syntax elements.

    All colors are defined as hex values (with # prefix) for consistency.
    Individual editor modules map these to their specific highlighting systems.
    """

    colors: dict[SyntaxElement, str]

    def get_color(self, element: SyntaxElement) -> str:
        """Get the color hex value for a syntax element."""
        return self.colors[element]


# Default BespokeASM color scheme
DEFAULT_COLOR_SCHEME = ColorScheme(
    colors={
        # Global/theme colors
        SyntaxElement.BACKGROUND: '#111111',
        SyntaxElement.FOREGROUND: '#EEEEEE',
        SyntaxElement.CARET: '#BBBBBB',
        SyntaxElement.SELECTION: '#294f7a',
        SyntaxElement.LINE_HIGHLIGHT: '#444444',  # Keep as hex for consistency

        # Number literals
        SyntaxElement.HEX_NUMBER: '#ffe80b',
        SyntaxElement.BINARY_NUMBER: '#d6d300',
        SyntaxElement.DECIMAL_NUMBER: '#fffd80',
        SyntaxElement.CHARACTER_NUMBER: '#FFE880',

        # Labels and identifiers
        SyntaxElement.LABEL_NAME: '#278ed8',
        SyntaxElement.LABEL_DEFINITION: '#278ed8',
        SyntaxElement.LABEL_USAGE: '#7fcaff',
        SyntaxElement.PUNCTUATION_LABEL_COLON: '#ed80a2',

        # Strings and escapes
        SyntaxElement.STRING: '#17d75a',
        SyntaxElement.STRING_ESCAPE: '#89c616',
        SyntaxElement.PUNCTUATION_STRING: '#afea41',

        # Comments
        SyntaxElement.COMMENT: '#568c3b',

        # Instructions and functions
        SyntaxElement.INSTRUCTION: '#ffa83f',
        SyntaxElement.MACRO: '#ff883f',  # Consistent across all editors

        # Variables and constants
        SyntaxElement.REGISTER: '#2ea9d2',
        SyntaxElement.CONSTANT_NAME: '#abd7ed',
        SyntaxElement.CONSTANT_DEFINITION: '#29e768',
        SyntaxElement.CONSTANT_USAGE: '#6fe797',
        SyntaxElement.COMPILER_LABEL: '#abedc1',
        SyntaxElement.PARAMETER: '#abd7ed',

        # Preprocessor and directives
        SyntaxElement.PREPROCESSOR: '#c080ff',
        SyntaxElement.DATA_TYPE: '#d6adff',
        SyntaxElement.DIRECTIVE: '#c080ff',

        # Operators
        SyntaxElement.OPERATOR: '#cc99ff',

        # Punctuation
        SyntaxElement.PUNCTUATION_SEPARATOR: '#ed80a2',
        SyntaxElement.PUNCTUATION_VARIABLE: '#ed80a2',
        SyntaxElement.PUNCTUATION_PREPROCESSOR: '#ed80a2',


        # Special punctuation (may have additional styling)
        SyntaxElement.BRACKET: '#b72dd2',
        SyntaxElement.DOUBLE_BRACKET: '#d22d9b',
        SyntaxElement.PARENTHESIS: '#dc81e4',
    }
)


# Hover styling color keys consumed by generated editor extensions.
HOVER_COLOR_ELEMENT_MAP: dict[str, SyntaxElement] = {
    'instruction': SyntaxElement.INSTRUCTION,
    'compiler_label': SyntaxElement.COMPILER_LABEL,
    'label_usage': SyntaxElement.LABEL_USAGE,
    'constant_usage': SyntaxElement.CONSTANT_USAGE,
    'parameter': SyntaxElement.PARAMETER,
    'number': SyntaxElement.DECIMAL_NUMBER,
    'punctuation': SyntaxElement.PUNCTUATION_SEPARATOR,
}


# Hover UI colors that are not direct syntax token colors.
HOVER_UI_COLOR_DEFAULTS: dict[str, str] = {
    'inline_code': '#6fb1ff',
    'table_header': '#D98C8C',
    'table_boundary': '#5F748A',
}


def build_hover_color_map(color_scheme: ColorScheme | None = None) -> dict[str, str]:
    """Build the hover color palette from the central color scheme."""
    scheme = color_scheme or DEFAULT_COLOR_SCHEME
    hover_colors = {
        key: scheme.get_color(syntax_element)
        for key, syntax_element in HOVER_COLOR_ELEMENT_MAP.items()
    }
    hover_colors.update(HOVER_UI_COLOR_DEFAULTS)
    return hover_colors
