"""
Language Version Expression Evaluator

This module provides functionality to evaluate language version expressions that use
built-in preprocessor symbols like __LANGUAGE_NAME__, __LANGUAGE_VERSION_MAJOR__, etc.

The evaluator is used by #if, #elif, and #require preprocessor directives when they
encounter language version symbols.
"""
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier


class LanguageVersionEvaluator:
    """Evaluates language version expressions to boolean values."""

    # Built-in language version symbols
    LANGUAGE_VERSION_SYMBOLS = {
        '__LANGUAGE_NAME__',
        '__LANGUAGE_VERSION__',
        '__LANGUAGE_VERSION_MAJOR__',
        '__LANGUAGE_VERSION_MINOR__',
        '__LANGUAGE_VERSION_PATCH__'
    }

    @classmethod
    def contains_language_version_symbols(cls, expression: str) -> bool:
        """Check if the expression contains any language version symbols."""
        return any(symbol in expression for symbol in cls.LANGUAGE_VERSION_SYMBOLS)

    @classmethod
    def is_pure_language_version_expression(cls, expression: str) -> bool:
        """
        Check if the expression is purely a language version expression.

        Pure expressions only contain:
        - Language version symbols
        - Comparison operators (==, !=, >=, <=, >, <)
        - Numeric literals
        - String literals
        - Whitespace

        Mixed expressions contain other symbols, boolean operators (&& ||), parentheses, etc.
        """
        # If it doesn't contain language version symbols, it's not a language version expression
        if not cls.contains_language_version_symbols(expression):
            return False

        # Check for complex boolean operators that indicate mixed expressions
        complex_operators = ['&&', '||', '&', '|', '^']
        if any(op in expression for op in complex_operators):
            return False

        # Check for parentheses which indicate complex grouping
        if '(' in expression or ')' in expression:
            return False

        # Split on comparison operators to get LHS and RHS
        operators = ['>=', '<=', '==', '!=', '>', '<']
        lhs_expr = None
        rhs_expr = None

        for op in operators:
            if op in expression:
                parts = expression.split(op, 1)
                if len(parts) == 2:
                    lhs_expr = parts[0].strip()
                    rhs_expr = parts[1].strip()
                    break

        if lhs_expr is None:
            # No comparison operator found - check if it's just a single language version symbol
            cleaned = expression.strip()
            return cleaned in cls.LANGUAGE_VERSION_SYMBOLS

        # Check that LHS and RHS only contain valid tokens
        return cls._is_valid_language_version_token(lhs_expr) and cls._is_valid_language_version_token(rhs_expr)

    @classmethod
    def _is_valid_language_version_token(cls, token: str) -> bool:
        """Check if a token is valid in a pure language version expression."""
        token = token.strip()

        # Language version symbol
        if token in cls.LANGUAGE_VERSION_SYMBOLS:
            return True

        # Numeric literal (integer or float)
        if token.replace('.', '').replace('-', '').isdigit():
            return True

        # String literal (simple identifier without spaces or special chars)
        # This allows things like "eater-sap1" or version strings like "1.0.0"
        if token.replace('-', '').replace('.', '').replace('_', '').isalnum():
            return True

        return False

    @classmethod
    def evaluate_expression(cls, expression: str, preprocessor, line_id: LineIdentifier) -> bool:
        """
        Evaluate a language version expression to a boolean result.

        Args:
            expression: The expression string (e.g., "__LANGUAGE_VERSION_MAJOR__ >= 1")
            preprocessor: The Preprocessor instance for symbol resolution
            line_id: LineIdentifier for error reporting

        Returns:
            bool: True if the expression evaluates to true, False otherwise

        Raises:
            SystemExit: If the expression is invalid or evaluation fails
        """
        try:
            # Always try comparison expression first since that's the most common case
            return cls._evaluate_comparison_expression(expression, preprocessor, line_id)

        except Exception as e:
            sys.exit(f'ERROR: {line_id} - Failed to evaluate language version expression "{expression}": {e}')

    @classmethod
    def _evaluate_comparison_expression(cls, expression: str, preprocessor, line_id: LineIdentifier) -> bool:
        """
        Evaluate a comparison expression (e.g., "symbol >= value").

        This handles expressions that contain comparison operators.
        """
        # Import locally to avoid circular imports
        from bespokeasm.expression import parse_expression

        # Simple approach: split on comparison operators
        operators = ['>=', '<=', '==', '!=', '>', '<']
        lhs_expr = None
        operator = None
        rhs_expr = None

        for op in operators:
            if op in expression:
                parts = expression.split(op, 1)
                if len(parts) == 2:
                    lhs_expr = parts[0].strip()
                    operator = op
                    rhs_expr = parts[1].strip()
                    break

        if lhs_expr is None:
            # No operator found - treat as implied != 0
            # But first check if there are invalid operators
            invalid_ops = ['~=', '=~', '&', '|', '^', '%']
            for invalid_op in invalid_ops:
                if invalid_op in expression:
                    sys.exit(f'ERROR: {line_id} - Invalid operator {invalid_op} in language version expression')

            resolved = preprocessor.resolve_symbols(line_id, expression)

            # Check if language version symbols were not resolved
            for symbol in cls.LANGUAGE_VERSION_SYMBOLS:
                if symbol in resolved:
                    sys.exit(f'ERROR: {line_id} - Language version symbol {symbol} is not defined (ISA model may be missing)')

            try:
                expr_node = parse_expression(line_id, resolved)
                if len(expr_node.contained_labels()) == 0:
                    result = expr_node.get_value(None, line_id)
                    return bool(result)
                else:
                    # String expression - check if it's non-empty
                    return bool(resolved.strip())
            except Exception:
                # If parsing fails, check if it's a non-empty string after resolving
                return bool(resolved.strip())

        # Resolve symbols in both expressions
        lhs_resolved = preprocessor.resolve_symbols(line_id, lhs_expr)
        rhs_resolved = preprocessor.resolve_symbols(line_id, rhs_expr)

        # Check if language version symbols were not resolved (still contain the symbol name)
        for symbol in cls.LANGUAGE_VERSION_SYMBOLS:
            if symbol in lhs_resolved or symbol in rhs_resolved:
                # Symbol was not resolved, meaning it doesn't exist
                sys.exit(f'ERROR: {line_id} - Language version symbol {symbol} is not defined (ISA model may be missing)')

        # Try to parse both sides as expressions
        try:
            lhs_expression = parse_expression(line_id, lhs_resolved)
            rhs_expression = parse_expression(line_id, rhs_resolved)

            # Determine if we should do string or numeric comparison
            if len(lhs_expression.contained_labels()) > 0 or len(rhs_expression.contained_labels()) > 0:
                # String comparison
                lhs_value = lhs_resolved
                rhs_value = rhs_resolved
            else:
                # Numeric comparison
                lhs_value = lhs_expression.get_value(None, line_id)
                rhs_value = rhs_expression.get_value(None, line_id)
        except Exception:
            # If parsing fails, do string comparison
            lhs_value = lhs_resolved
            rhs_value = rhs_resolved

        # Perform the comparison
        if operator == '==':
            return lhs_value == rhs_value
        elif operator == '!=':
            return lhs_value != rhs_value
        elif operator == '>':
            return lhs_value > rhs_value
        elif operator == '>=':
            return lhs_value >= rhs_value
        elif operator == '<':
            return lhs_value < rhs_value
        elif operator == '<=':
            return lhs_value <= rhs_value
        else:
            sys.exit(f'ERROR: {line_id} - Unknown operator {operator} in language version expression')
