#!/usr/bin/env python3
"""
Visual color mapping demo for BespokeASM syntax highlighting.

This demo shows the RGB hex colors from the central color scheme alongside
their 256-color terminal approximations, displayed with actual terminal colors.
"""
import sys

from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
from bespokeasm.configgen.color_scheme import SyntaxElement
from bespokeasm.configgen.vim import VimConfigGenerator


ELEMENT_COLUMN_WIDTH = max(25, *(len(element.name) for element in SyntaxElement))


class ColorDemo:
    """Visual demonstration of color mappings."""
    def __init__(self):
        # Create VIM generator instance for color conversion
        class TestVim(VimConfigGenerator):
            def __init__(self): pass
        self.vim_generator = TestVim()

    def hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def print_color_sample(self, hex_color: str, term_color: int, name: str, description: str = ''):
        """Print a color sample with both RGB and terminal versions."""
        r, g, b = self.hex_to_rgb(hex_color)

        # ANSI escape codes for colors
        # True color (24-bit RGB) - if supported
        rgb_bg = f"\033[48;2;{r};{g};{b}m"
        # 256-color terminal
        term_bg = f"\033[48;5;{term_color}m"
        reset = '\033[0m'

        # Text colors for contrast
        white_text = '\033[38;5;15m'  # White text
        black_text = '\033[38;5;0m'   # Black text

        # Choose text color based on brightness
        brightness = (r * 0.299 + g * 0.587 + b * 0.114)
        text_color = black_text if brightness > 128 else white_text

        # Print color samples
        print(
            f"{name:{ELEMENT_COLUMN_WIDTH}} {hex_color:8} → {term_color:3} ",
            end='',
        )
        print(f"{rgb_bg}{text_color}  RGB  {reset} ", end='')
        print(f"{term_bg}{text_color} TERM {reset} ", end='')
        if description:
            print(f" {description}")
        else:
            print()

    def print_header(self):
        """Print demo header."""
        print('=' * 80)
        print('🎨 BespokeASM Color Scheme - Terminal Color Mapping Demo')
        print('=' * 80)
        print()
        print('This demo shows RGB hex colors next to their 256-color terminal approximations.')
        print('The left sample shows true RGB color, the right shows terminal approximation.')
        print()
        print(
            f"{'Element':{ELEMENT_COLUMN_WIDTH}} {'Hex':8}   {'Term':3}  "
            f"{'True RGB':6}  {'Terminal':8}  Description"
        )
        print('-' * 80)

    def demo_syntax_colors(self):
        """Demo all syntax highlighting colors."""
        self.print_header()

        # Define color categories with descriptions
        color_categories = [
            ('BACKGROUND', 'Editor background'),
            ('FOREGROUND', 'Default text color'),
            ('CARET', 'Cursor color'),
            ('SELECTION', 'Selected text background'),
            ('LINE_HIGHLIGHT', 'Current line highlight'),
        ]

        number_colors = [
            ('HEX_NUMBER', 'Hexadecimal literals'),
            ('BINARY_NUMBER', 'Binary literals'),
            ('DECIMAL_NUMBER', 'Decimal literals'),
            ('CHARACTER_NUMBER', 'Character literals'),
        ]

        syntax_colors = [
            ('LABEL_NAME', 'Assembly labels'),
            ('LABEL_DEFINITION', 'Label definitions'),
            ('LABEL_USAGE', 'Label references'),
            ('PUNCTUATION_LABEL_COLON', 'Label colon separator'),
            ('OPERAND_LABEL_AT', 'Operand-label @ prefix'),
            ('OPERAND_LABEL_NAME', 'Operand-label definitions'),
            ('OPERAND_LABEL_COLON', 'Operand-label colon separator'),
            ('STRING', 'String literals'),
            ('STRING_ESCAPE', 'Escape sequences'),
            ('PUNCTUATION_STRING', 'String quotes'),
            ('COMMENT', 'Code comments'),
            ('INSTRUCTION', 'CPU instructions'),
            ('MACRO', 'Macro calls'),
            ('REGISTER', 'CPU registers'),
            ('CONSTANT_NAME', 'Named constants'),
            ('CONSTANT_DEFINITION', 'Constant definitions'),
            ('CONSTANT_USAGE', 'Constant references'),
            ('FLOW_COUNTER_NAME', 'Flow-counter names'),
            ('FLOW_COUNTER_USAGE', 'Flow-counter references'),
            ('FLOW_COORDINATE_NAME', 'Flow-coordinate names'),
            ('FLOW_COORDINATE_DEFINITION', 'Flow-coordinate definitions'),
            ('FLOW_COORDINATE_USAGE', 'Flow-coordinate references'),
            ('COMPILER_LABEL', 'Compiler-generated labels'),
            ('PARAMETER', 'Function parameters'),
            ('PREPROCESSOR', 'Preprocessor directives'),
            ('DATA_TYPE', 'Data type keywords'),
            ('DIRECTIVE', 'Assembler directives'),
            ('OPERATOR', 'Operators'),
            ('FLOW_OPERATOR', 'Flow-counter expression operators'),
            ('PUNCTUATION_SEPARATOR', 'Punctuation separators'),
            ('PUNCTUATION_VARIABLE', 'Variable punctuation'),
            ('PUNCTUATION_PREPROCESSOR', 'Preprocessor punctuation'),
            ('BRACKET', 'Addressing brackets'),
            ('DOUBLE_BRACKET', 'Double brackets'),
            ('PARENTHESIS', 'Parentheses'),
        ]

        # Demo each category
        categories = [
            ('🎛️  Theme Colors', color_categories),
            ('🔢 Number Literals', number_colors),
            ('🔤 Syntax Elements', syntax_colors),
        ]

        for category_name, colors in categories:
            print(f"\n{category_name}")
            print('-' * len(category_name))

            for element_name, description in colors:
                try:
                    element = SyntaxElement[element_name]
                    hex_color = DEFAULT_COLOR_SCHEME.get_color(element)
                    term_color = self.vim_generator._get_vim_cterm_approximation(hex_color)

                    self.print_color_sample(hex_color, term_color, element_name, description)
                except KeyError:
                    print(f"⚠️  Unknown element: {element_name}")

    def demo_color_space(self):
        """Demo the 256-color space regions."""
        print('\n' + '=' * 80)
        print('🌈 256-Color Terminal Space Demo')
        print('=' * 80)
        print()

        # Demo primary colors
        print('Primary Colors:')
        test_colors = [
            ('#FF0000', 'Pure Red'),
            ('#00FF00', 'Pure Green'),
            ('#0000FF', 'Pure Blue'),
            ('#FFFF00', 'Yellow'),
            ('#FF00FF', 'Magenta'),
            ('#00FFFF', 'Cyan'),
            ('#FFFFFF', 'White'),
            ('#000000', 'Black'),
        ]

        for hex_color, name in test_colors:
            term_color = self.vim_generator._get_vim_cterm_approximation(hex_color)
            self.print_color_sample(hex_color, term_color, name)

        print('\nGrayscale Ramp:')
        # Demo grayscale colors
        for i in range(0, 256, 32):
            hex_color = f"#{i:02x}{i:02x}{i:02x}"
            term_color = self.vim_generator._get_vim_cterm_approximation(hex_color)
            self.print_color_sample(hex_color, term_color, f"Gray {i}")

    def demo_terminal_palette(self):
        """Show a visual representation of the 256-color palette."""
        print('\n' + '=' * 80)
        print('🎨 256-Color Terminal Palette')
        print('=' * 80)
        print()

        # Standard colors (0-15)
        print('Standard ANSI Colors (0-15):')
        for i in range(16):
            bg = f"\033[48;5;{i}m"
            text = '\033[38;5;15m' if i < 8 else '\033[38;5;0m'
            reset = '\033[0m'
            print(f"{bg}{text}{i:3}{reset}", end=' ')
            if i == 7:
                print()
        print('\n')

        # 6x6x6 RGB cube (16-231) - show multiple slices
        print('6×6×6 RGB Cube Samples (colors 16-231):')
        print('Formula: 16 + (36×R) + (6×G) + B  where R,G,B ∈ {0,1,2,3,4,5}')
        print()

        # Show multiple red levels
        red_levels = [0, 2, 4]  # Show a few slices through the cube
        for r in red_levels:
            print(f"Red={r}, varying Green and Blue:")
            for g in range(6):
                for b in range(6):
                    color_index = 16 + (r * 36) + (g * 6) + b
                    bg = f"\033[48;5;{color_index}m"
                    text = '\033[38;5;15m' if r < 3 else '\033[38;5;0m'
                    reset = '\033[0m'
                    print(f"{bg}{text}{color_index:3}{reset}", end=' ')
                print()
            print()

        # Show red progression with fixed green and blue
        print('Red progression (Green=2, Blue=2):')
        for r in range(6):
            color_index = 16 + (r * 36) + (2 * 6) + 2
            bg = f"\033[48;5;{color_index}m"
            text = '\033[38;5;15m' if r < 3 else '\033[38;5;0m'
            reset = '\033[0m'
            print(f"{bg}{text}R={r} ({color_index:3}){reset}", end='  ')
        print('\n')

        # Grayscale ramp (232-255)
        print('Grayscale Ramp (232-255):')
        for i in range(232, 256):
            bg = f"\033[48;5;{i}m"
            text = '\033[38;5;15m' if i < 244 else '\033[38;5;0m'
            reset = '\033[0m'
            print(f"{bg}{text}{i:3}{reset}", end=' ')
            if (i - 232 + 1) % 8 == 0:
                print()
        print()

    def run_demo(self):
        """Run the complete color demo."""
        # Check if terminal supports colors
        if not sys.stdout.isatty():
            print('⚠️  This demo requires a color terminal.')
            return

        print('\033[?25l')  # Hide cursor for cleaner display

        try:
            self.demo_syntax_colors()
            self.demo_color_space()
            self.demo_terminal_palette()

            print('\n' + '=' * 80)
            print("✅ Demo complete! Your terminal's color support looks great.")
            print('💡 Try changing colors in color_scheme.py and run this demo again!')
            print('=' * 80)

        finally:
            print('\033[?25h')  # Show cursor again


def main():
    """Main entry point."""
    demo = ColorDemo()
    demo.run_demo()


if __name__ == '__main__':
    main()
