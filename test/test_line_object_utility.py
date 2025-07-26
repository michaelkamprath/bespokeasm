import re
import unittest

from bespokeasm.assembler.line_object.utility import is_valid_label
from bespokeasm.assembler.line_object.utility import PATTERN_ALLOWED_LABELS


class TestLineObjectUtility(unittest.TestCase):
    """Test cases for the utility functions in assembler.line_object.utility"""

    def test_valid_label_patterns(self):
        """Test various valid label patterns"""
        # Basic valid labels
        self.assertTrue(is_valid_label('a_str'), 'simple lowercase label')
        self.assertTrue(is_valid_label('A_STR'), 'simple uppercase label')
        self.assertTrue(is_valid_label('a_str_with_123'), 'label with numbers')
        self.assertTrue(is_valid_label('A_STR_WITH_123'), 'uppercase label with numbers')

        # Labels starting with dot
        self.assertTrue(is_valid_label('.start_with_dot'), 'label starting with dot')
        self.assertTrue(is_valid_label('.START_WITH_DOT'), 'uppercase label starting with dot')
        self.assertTrue(is_valid_label('.start_with_dot_123'), 'dot label with numbers')

        # Labels starting with underscore
        self.assertTrue(is_valid_label('_start_with_underscore'), 'label starting with underscore')
        self.assertTrue(is_valid_label('_START_WITH_UNDERSCORE'), 'uppercase label starting with underscore')
        self.assertTrue(is_valid_label('_start_with_underscore_123'), 'underscore label with numbers')

        # Mixed case labels
        self.assertTrue(is_valid_label('MixedCase'), 'mixed case label')
        self.assertTrue(is_valid_label('mixed_Case_123'), 'mixed case with underscore and numbers')

        # Single character labels
        self.assertTrue(is_valid_label('a'), 'single lowercase letter')
        self.assertTrue(is_valid_label('A'), 'single uppercase letter')
        self.assertFalse(is_valid_label('_'), 'single underscore should be invalid')
        self.assertFalse(is_valid_label('.'), 'single dot should be invalid')

        # Labels with multiple underscores
        self.assertTrue(is_valid_label('multiple__underscores'), 'multiple consecutive underscores')
        self.assertTrue(is_valid_label('_multiple__underscores_'), 'underscores at start and end')

    def test_invalid_label_patterns(self):
        """Test various invalid label patterns"""
        # Labels starting with numbers
        self.assertFalse(is_valid_label('12_monkeys'), 'label starting with numbers')
        self.assertFalse(is_valid_label('8675309'), 'label with only numbers')
        self.assertFalse(is_valid_label('123abc'), 'label starting with numbers')

        # Numeric-only labels (should be invalid)
        self.assertFalse(is_valid_label('123'), 'numeric-only label should be invalid')
        self.assertFalse(is_valid_label('0'), 'single digit should be invalid')
        self.assertFalse(is_valid_label('42'), 'two digits should be invalid')
        self.assertFalse(is_valid_label('999999'), 'many digits should be invalid')

        # Labels with invalid characters
        self.assertFalse(is_valid_label('m+g'), 'label with operators')
        self.assertFalse(is_valid_label('final frontier'), 'label with spaces')
        self.assertFalse(is_valid_label('label-with-dash'), 'label with hyphens')
        self.assertFalse(is_valid_label('label@domain'), 'label with @ symbol')
        self.assertFalse(is_valid_label('label#hash'), 'label with # symbol')
        self.assertFalse(is_valid_label('label$dollar'), 'label with $ symbol')
        self.assertFalse(is_valid_label('label%percent'), 'label with % symbol')
        self.assertFalse(is_valid_label('label^caret'), 'label with ^ symbol')
        self.assertFalse(is_valid_label('label&ampersand'), 'label with & symbol')
        self.assertFalse(is_valid_label('label*asterisk'), 'label with * symbol')
        self.assertFalse(is_valid_label('label(open'), 'label with ( symbol')
        self.assertFalse(is_valid_label('label)close'), 'label with ) symbol')
        self.assertFalse(is_valid_label('label[bracket'), 'label with [ symbol')
        self.assertFalse(is_valid_label('label]close_bracket'), 'label with ] symbol')
        self.assertFalse(is_valid_label('label{brace'), 'label with { symbol')
        self.assertFalse(is_valid_label('label}close_brace'), 'label with } symbol')
        self.assertFalse(is_valid_label('label|pipe'), 'label with | symbol')
        self.assertFalse(is_valid_label('label\\backslash'), 'label with \\ symbol')
        self.assertFalse(is_valid_label('label/slash'), 'label with / symbol')
        self.assertFalse(is_valid_label('label?question'), 'label with ? symbol')
        self.assertFalse(is_valid_label('label,comma'), 'label with , symbol')
        self.assertFalse(is_valid_label('label;semicolon'), 'label with ; symbol')
        self.assertFalse(is_valid_label('label:colon'), 'label with : symbol')
        self.assertFalse(is_valid_label('label"quote'), 'label with " symbol')
        self.assertFalse(is_valid_label("label'apostrophe"), 'label with \' symbol')
        self.assertFalse(is_valid_label('label`backtick'), 'label with ` symbol')
        self.assertFalse(is_valid_label('label~tilde'), 'label with ~ symbol')

        # Reserved patterns (double underscore and double dot)
        self.assertFalse(is_valid_label('__reserved'), 'label starting with double underscore')
        self.assertTrue(is_valid_label('reserved__'), 'label ending with double underscore is valid')
        self.assertTrue(is_valid_label('reserved__middle'), 'label with double underscore in middle is valid')
        self.assertFalse(is_valid_label('..reserved'), 'label starting with double dot')
        self.assertFalse(is_valid_label('reserved..'), 'label ending with double dot is invalid (dots only allowed at start)')
        self.assertFalse(
            is_valid_label('reserved..middle'),
            'label with double dot in middle is invalid (dots only allowed at start)'
        )

        # Empty and whitespace
        self.assertFalse(is_valid_label(''), 'empty string')
        self.assertFalse(is_valid_label(' '), 'whitespace only')
        self.assertFalse(is_valid_label('\t'), 'tab only')
        self.assertFalse(is_valid_label('\n'), 'newline only')
        self.assertFalse(is_valid_label('  label  '), 'label with leading/trailing whitespace')

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Very long labels
        long_label = 'a' * 1000
        self.assertTrue(is_valid_label(long_label), 'very long valid label')

        # Labels with maximum allowed characters
        max_chars_label = 'a' + 'b' * 999
        self.assertTrue(is_valid_label(max_chars_label), 'label with many characters')

        # Unicode characters (should be invalid)
        self.assertFalse(is_valid_label('labelé'), 'label with unicode character')
        self.assertFalse(is_valid_label('labelñ'), 'label with unicode character')
        self.assertFalse(is_valid_label('labelα'), 'label with greek letter')
        self.assertFalse(is_valid_label('label中'), 'label with chinese character')

        # Control characters
        self.assertFalse(is_valid_label('label\x00'), 'label with null character')
        self.assertFalse(is_valid_label('label\x01'), 'label with control character')
        self.assertFalse(is_valid_label('label\x7f'), 'label with delete character')

    def test_regex_pattern_consistency(self):
        """Test that the regex pattern matches the function behavior"""
        test_cases = [
            ('valid_label', True),
            ('VALID_LABEL', True),
            ('valid_label_123', True),
            ('.start_with_dot', True),
            ('_start_with_underscore', True),
            ('12_invalid', False),
            ('invalid space', False),
            ('invalid-dash', False),
            ('__reserved', False),
            ('..reserved', False),
            ('', False),
            (' ', False),
        ]

        for test_string, expected_result in test_cases:
            regex_match = PATTERN_ALLOWED_LABELS.search(test_string) is not None
            function_result = is_valid_label(test_string)

            self.assertEqual(
                regex_match,
                function_result,
                f'Regex and function disagree on "{test_string}": regex={regex_match}, function={function_result}'
            )

    def test_case_insensitivity(self):
        """Test that the regex is case insensitive as specified"""
        # Test that the regex pattern has the IGNORECASE flag
        self.assertTrue(PATTERN_ALLOWED_LABELS.flags & re.IGNORECASE, 'Pattern should be case insensitive')

        # Test case variations
        variations = [
            'testlabel',
            'TESTLABEL',
            'TestLabel',
            'testLabel',
            'TESTlabel',
        ]

        for variation in variations:
            self.assertTrue(is_valid_label(variation), f'Case variation should be valid: {variation}')

    def test_multiline_flag(self):
        """Test that the regex has the MULTILINE flag as specified"""
        self.assertTrue(PATTERN_ALLOWED_LABELS.flags & re.MULTILINE, 'Pattern should have MULTILINE flag')


if __name__ == '__main__':
    unittest.main()
