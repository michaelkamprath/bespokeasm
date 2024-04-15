from packaging import version
import operator
import re
import sys

from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel


class RequiredLanguageLine(PreprocessorLine):
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
                log_verbosity: int
            ):
        super().__init__(line_id, instruction, comment, memzone)
        require_match = re.search(RequiredLanguageLine.PATTERN_REQUIRE_LANGUAGE, instruction)
        if require_match is not None:
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
                        f'{require_match.group(3)}". Configurate file declares language "{isa_model.isa_name} '
                        f'{isa_model.isa_version}"'
                    )
            elif log_verbosity > 1:
                print(
                    f'Code file requires language "{require_match.group(1)}". '
                    f'Configurate file declares language "{isa_model.isa_name} v{isa_model.isa_version}"'
                )

    def __repr__(self) -> str:
        return f'RequiredLanguageLine<{self._language} {self._operator_str} {self._version_obj}>'
