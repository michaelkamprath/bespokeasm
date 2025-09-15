"""
Tests for the LanguageVersionEvaluator class.

This module tests the shared language version expression evaluator that is used
by #if, #elif, and #require preprocessor directives when they encounter
language version symbols.
"""
import importlib.resources as pkg_resources
import unittest

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.language_version_evaluator import LanguageVersionEvaluator

from test import config_files


class TestLanguageVersionEvaluator(unittest.TestCase):
    """Test cases for LanguageVersionEvaluator class."""

    def setUp(self):
        """Set up test fixtures."""
        fp = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        self.isa_model = AssemblerModel(str(fp), 0)
        self.preprocessor = Preprocessor(self.isa_model.predefined_symbols, self.isa_model)
        self.line_id = LineIdentifier(1, 'test_language_version_evaluator')

    def test_contains_language_version_symbols(self):
        """Test detection of language version symbols in expressions."""
        # Test expressions that contain language version symbols
        self.assertTrue(LanguageVersionEvaluator.contains_language_version_symbols('__LANGUAGE_NAME__ == "test"'))
        self.assertTrue(LanguageVersionEvaluator.contains_language_version_symbols('__LANGUAGE_VERSION__ >= "1.0.0"'))
        self.assertTrue(LanguageVersionEvaluator.contains_language_version_symbols('__LANGUAGE_VERSION_MAJOR__ >= 1'))
        self.assertTrue(LanguageVersionEvaluator.contains_language_version_symbols('__LANGUAGE_VERSION_MINOR__ < 5'))
        self.assertTrue(LanguageVersionEvaluator.contains_language_version_symbols('__LANGUAGE_VERSION_PATCH__ != 0'))

        # Test expressions that don't contain language version symbols
        self.assertFalse(LanguageVersionEvaluator.contains_language_version_symbols('OTHER_SYMBOL >= 1'))
        self.assertFalse(LanguageVersionEvaluator.contains_language_version_symbols('SOME_VAR == "value"'))
        self.assertFalse(LanguageVersionEvaluator.contains_language_version_symbols('1 + 2 * 3'))

    def test_evaluate_numeric_comparisons(self):
        """Test evaluation of numeric comparison expressions."""
        # Test >= operator
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ >= 0', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ >= 1', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ >= 2', self.preprocessor, self.line_id))

        # Test > operator
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MINOR__ > 0', self.preprocessor, self.line_id))  # 0 > 0 = False
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__ > 0', self.preprocessor, self.line_id))  # 1 > 0 = True

        # Test == operator
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ == 0', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ == 1', self.preprocessor, self.line_id))

        # Test != operator
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ != 1', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ != 0', self.preprocessor, self.line_id))

        # Test < operator
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ < 1', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ < 0', self.preprocessor, self.line_id))

        # Test <= operator
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ <= 0', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ <= 1', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ <= -1', self.preprocessor, self.line_id))

    def test_evaluate_string_comparisons(self):
        """Test evaluation of string comparison expressions."""
        # Test language name comparison
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_NAME__ == eater-sap1-isa', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_NAME__ == other-language', self.preprocessor, self.line_id))

        # Test version string comparison
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION__ == 0.0.1', self.preprocessor, self.line_id))
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION__ == 1.0.0', self.preprocessor, self.line_id))

    def test_evaluate_implied_format(self):
        """Test evaluation of implied format (symbol only, implies != 0)."""
        # Test with patch version (should be 1, so truthy)
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__', self.preprocessor, self.line_id))

        # Test with major version (should be 0, so falsy)
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__', self.preprocessor, self.line_id))

    def test_evaluate_complex_expressions(self):
        """Test evaluation of more complex expressions."""
        # Test with different version components
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MINOR__ >= __LANGUAGE_VERSION_MAJOR__', self.preprocessor, self.line_id))

        # Test with numeric literals
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__ >= 1', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__ == 1', self.preprocessor, self.line_id))

    def test_operator_precedence(self):
        """Test that operators are parsed correctly when multiple operators are present."""
        # Test that >= is matched before >
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ >= 0', self.preprocessor, self.line_id))

        # Test that <= is matched before <
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ <= 0', self.preprocessor, self.line_id))

        # Test that == is matched correctly
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ == 0', self.preprocessor, self.line_id))

    def test_whitespace_handling(self):
        """Test that expressions with various whitespace are handled correctly."""
        # Test expressions with extra whitespace
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '  __LANGUAGE_VERSION_MAJOR__   >=   0  ', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '\t__LANGUAGE_VERSION_PATCH__\t==\t1\t', self.preprocessor, self.line_id))

        # Test expressions with no whitespace around operators
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__>=0', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__==1', self.preprocessor, self.line_id))

    def test_error_handling(self):
        """Test error handling for invalid expressions."""
        # Test with invalid operator
        with self.assertRaises(SystemExit):
            LanguageVersionEvaluator.evaluate_expression(
                '__LANGUAGE_VERSION_MAJOR__ ~= 1', self.preprocessor, self.line_id)

    def test_integration_with_different_isa_models(self):
        """Test evaluator works with different ISA model configurations."""
        # Create a preprocessor without ISA model
        preprocessor_no_isa = Preprocessor()

        # Test that language version symbols don't exist
        with self.assertRaises(SystemExit):
            LanguageVersionEvaluator.evaluate_expression(
                '__LANGUAGE_VERSION_MAJOR__ >= 0', preprocessor_no_isa, self.line_id)

    def test_version_edge_cases(self):
        """Test edge cases with version parsing."""
        # This test uses the eater-sap1-isa.yaml file which should have version 0.0.1
        # and tests various edge cases based on that version

        # Test equality comparisons
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ == 0', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MINOR__ == 0', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__ == 1', self.preprocessor, self.line_id))

        # Test boundary conditions
        self.assertFalse(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_MAJOR__ > 0', self.preprocessor, self.line_id))
        self.assertTrue(LanguageVersionEvaluator.evaluate_expression(
            '__LANGUAGE_VERSION_PATCH__ > 0', self.preprocessor, self.line_id))

    def test_pure_vs_mixed_expression_detection(self):
        """Test detection of pure vs mixed language version expressions."""
        # Test pure language version expressions
        self.assertTrue(LanguageVersionEvaluator.is_pure_language_version_expression(
            '__LANGUAGE_VERSION_MAJOR__ >= 1'))
        self.assertTrue(LanguageVersionEvaluator.is_pure_language_version_expression(
            '__LANGUAGE_NAME__ == eater-sap1'))
        self.assertTrue(LanguageVersionEvaluator.is_pure_language_version_expression(
            '__LANGUAGE_VERSION_PATCH__'))
        self.assertTrue(LanguageVersionEvaluator.is_pure_language_version_expression(
            '__LANGUAGE_VERSION__ != 1.0.0'))

        # Test mixed expressions (should NOT be handled by language version evaluator)
        self.assertFalse(LanguageVersionEvaluator.is_pure_language_version_expression(
            '(SOME_SYMBOL == 4) && (__LANGUAGE_VERSION__ >= 1.0.0)'))
        self.assertFalse(LanguageVersionEvaluator.is_pure_language_version_expression(
            '__LANGUAGE_VERSION_MAJOR__ >= 1 && OTHER_SYMBOL == 2'))
        self.assertFalse(LanguageVersionEvaluator.is_pure_language_version_expression(
            '(__LANGUAGE_NAME__ == test)'))
        self.assertFalse(LanguageVersionEvaluator.is_pure_language_version_expression(
            'SYMBOL1 || __LANGUAGE_VERSION_MAJOR__ > 0'))

        # Test expressions without language version symbols
        self.assertFalse(LanguageVersionEvaluator.is_pure_language_version_expression('SOME_SYMBOL == 4'))
        self.assertFalse(LanguageVersionEvaluator.is_pure_language_version_expression('OTHER_VAR >= 1'))

    def test_mixed_expression_error_handling_integration(self):
        """Test that mixed expressions with language version symbols generate helpful error messages."""
        from bespokeasm.assembler.preprocessor.condition import IfPreprocessorCondition

        fp = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        preprocessor = Preprocessor(isa_model.predefined_symbols, isa_model)

        # Create condition with mixed expression (this should succeed)
        condition = IfPreprocessorCondition(
            '#if SYMBOL == 4 && __LANGUAGE_VERSION_MAJOR__ >= 0', self.line_id)

        # Test that evaluating the condition raises SystemExit
        with self.assertRaises(SystemExit) as cm:
            condition.evaluate(preprocessor)

        # Check that the error message is helpful
        error_message = str(cm.exception)
        self.assertIn(
            'Mixed expressions containing language version symbols are not supported', error_message)
        self.assertIn('Use separate #if blocks for each condition instead', error_message)

        # Test with parentheses as well
        condition2 = IfPreprocessorCondition(
            '#if (SYMBOL == 4) && (__LANGUAGE_VERSION_MAJOR__ >= 0)', self.line_id)
        with self.assertRaises(SystemExit) as cm:
            condition2.evaluate(preprocessor)

        error_message = str(cm.exception)
        self.assertIn(
            'Mixed expressions containing language version symbols are not supported', error_message)


if __name__ == '__main__':
    unittest.main()
