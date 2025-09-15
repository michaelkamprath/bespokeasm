import operator
import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from packaging import version


class RequiredLanguageLine(PreprocessorLine):
    # Legacy string format pattern
    PATTERN_REQUIRE_LANGUAGE = re.compile(
        fr'\#require\s+\"([\w\-\_\.]*)(?:\s*(==|>=|<=|>|<)\s*({version.VERSION_PATTERN}))?\"',
        flags=re.IGNORECASE | re.VERBOSE
    )

    COMPARISON_ACTIONS = {
        '>=': {
            'check': operator.ge,
            'error': 'ERROR: {0} - at least language version "{1}" is required but '
                     'ISA configuration file declares language version "{2}"',
        },
        '<=': {
            'check': operator.le,
            'error': 'ERROR: {0} - up to language version "{1}" is required but '
                     'ISA configuration file declares language version "{2}"',
        },
        '>': {
            'check': operator.gt,
            'error': 'ERROR: {0} - greater than language version "{1}" is required but '
                     'ISA configuration file declares language version "{2}"',
        },
        '<': {
            'check': operator.lt,
            'error': 'ERROR: {0} - less than language version "{1}" is required but '
                     'ISA configuration file declares language version "{2}"',
        },
        '==': {
            'check': operator.eq,
            'error': 'ERROR: {0} - exactly language version "{1}" is required but '
                     'ISA configuration file declares language version "{2}"',
        },
    }

    def __init__(
                self,
                line_id: LineIdentifier,
                instruction: str,
                comment: str,
                memzone: MemoryZone,
                isa_model: AssemblerModel,
                preprocessor: Preprocessor,
                log_verbosity: int
            ):
        super().__init__(line_id, instruction, comment, memzone)

        # First, check if it's legacy string format (has quotes)
        require_match = re.search(RequiredLanguageLine.PATTERN_REQUIRE_LANGUAGE, instruction)
        if require_match is not None:
            # Handle legacy format
            self._handle_legacy_format(require_match, isa_model, line_id, log_verbosity)
        else:
            # Not legacy format - check if it's a symbol-based format
            self._handle_symbol_format(instruction, preprocessor, line_id, log_verbosity)

    def _handle_legacy_format(self, require_match, isa_model: AssemblerModel, line_id: LineIdentifier, log_verbosity: int):
        """Handle the legacy string format for #require directive."""
        self._language = require_match.group(1).strip()
        if self._language != isa_model.isa_name:
            sys.exit(
                f'ERROR: {line_id} - language "{self._language}" is required but ISA '
                f'configuration file declares language "{isa_model.isa_name}"'
            )
        if len(require_match.groups()) >= 3 and require_match.group(2) is not None and require_match.group(3) is not None:
            self._operator_str = require_match.group(2).strip()
            version_str = require_match.group(3).strip()
            self._version_obj = version.parse(version_str)
            model_version_obj = version.parse(isa_model.isa_version)

            if self._operator_str in RequiredLanguageLine.COMPARISON_ACTIONS:
                if not RequiredLanguageLine.COMPARISON_ACTIONS[self._operator_str]['check'](
                            model_version_obj, self._version_obj
                        ):
                    sys.exit(
                        RequiredLanguageLine.COMPARISON_ACTIONS[self._operator_str]['error'].format(
                            line_id, version_str, isa_model.isa_version
                        )
                    )
            else:
                sys.exit(f'ERROR: {line_id} - got a language requirement comparison that is not understood.')
            if log_verbosity > 1:
                print(
                    f'Code file requires language "{require_match.group(1)} {require_match.group(2)} '
                    f'{require_match.group(3)}". Configuration file declares language "{isa_model.isa_name} '
                    f'{isa_model.isa_version}"'
                )
        elif log_verbosity > 1:
            print(
                f'Code file requires language "{require_match.group(1)}". '
                f'Configuration file declares language "{isa_model.isa_name} v{isa_model.isa_version}"'
            )

    def _handle_symbol_format(self, instruction: str, preprocessor: 'Preprocessor',
                              line_id: LineIdentifier, log_verbosity: int):
        """Handle symbol-based format using the shared language version evaluator."""
        from bespokeasm.assembler.preprocessor.language_version_evaluator import LanguageVersionEvaluator

        # Extract the expression part (everything after "#require ")
        expression = instruction.replace('#require', '', 1).strip()

        # Check if this expression contains language version symbols
        if not LanguageVersionEvaluator.contains_language_version_symbols(expression):
            sys.exit(
                f'ERROR: {line_id} - #require directive with non-quoted expression must use language version symbols. '
                f'Use legacy format: #require "language-name >= version" or '
                f'use language version symbols: #require __LANGUAGE_VERSION_MAJOR__ >= 1'
            )

        # Evaluate the language version expression
        try:
            result = LanguageVersionEvaluator.evaluate_expression(expression, preprocessor, line_id)

            # If requirement not met, exit with error
            if not result:
                sys.exit(f'ERROR: {line_id} - Language version requirement not met: {expression}')

            if log_verbosity > 1:
                print(f'Language version requirement satisfied: {expression}')

        except SystemExit:
            # Re-raise SystemExit (from evaluator or our own)
            raise
        except Exception as e:
            sys.exit(f'ERROR: {line_id} - Invalid #require expression: {expression} - {e}')

    def __repr__(self) -> str:
        return f'RequiredLanguageLine<{self._line_id}>'
