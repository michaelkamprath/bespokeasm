import re
import sys

from bespokeasm.assembler.line_object import LineObject
from bespokeasm.utilities import is_string_numeric, parse_numeric_string

PATTERN_ALLOWED_LABELS = re.compile(
        r'^(?!__|\.\.)(?:(?:\.|_|[a-zA-Z])[a-zA-Z0-9_]*)$',
        flags=re.IGNORECASE|re.MULTILINE
    )

def is_valid_label(s: str):
    res = re.search(PATTERN_ALLOWED_LABELS, s)
    return (res is not None)


class LabelLine(LineObject):
    PATTERN_LABEL = re.compile(
        r'^\s*(\.?\w*):',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_CONSTANT = re.compile(
        r'^\s*(\w*)(?:\s*)?\=(?:\s*)?(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    def factory(line_num: int, line_str: str, comment: str, registers: set[str]):
        """Tries to match the passed line string to the Label or Constant directive patterns.
        If succcessful, returns a constructed LabelLine object. If not, None is
        returned.
        """
        # first determine if there is a label
        label_match = re.search(LabelLine.PATTERN_LABEL, line_str)
        if label_match is not None:
            # set this line up as a label
            label_val = label_match.group(1).strip()
            if is_valid_label(label_val):
                if label_val in registers:
                    sys.exit(f'ERROR: line {line_num} - used the register label "{label_val}" as a non-register label')
                return LabelLine(line_num, label_val, None, line_str, comment)

        # Now determine is the line is a constant
        constant_match = re.search(LabelLine.PATTERN_CONSTANT, line_str)
        if constant_match is not None and len(constant_match.groups()) == 2:
            numeric_str = constant_match.group(2).strip()
            if not is_string_numeric(numeric_str):
                sys.exit(f'ERROR: line {line_num} - constant assigned nonnumeric value')
            constant_label = constant_match.group(1).strip()
            if not is_valid_label(constant_label):
                sys.exit(f'ERROR: line {line_num} - invalid format for constant label: {constant_label}')
            if constant_label in registers:
                sys.exit(f'ERROR: line {line_num} - used the register label "{constant_label}" as a non-register label')
            return LabelLine(
                line_num,
                constant_label,
                parse_numeric_string(numeric_str),
                line_str,
                comment,
            )
        #if we got here it was neither a Label or a Constant
        return None

    def __init__(self, line_num: int, label: str, value: int, instruction: str, comment: str):
        super().__init__(line_num, instruction, comment)
        self._label = label
        self._value = value
    def __str__(self):
        return f'LabelLine<{self.get_label()} -> {self.get_value()}>'

    @property
    def is_constant(self):
        return self._value is not None

    def get_label(self) -> str:
        """Returns the label string"""
        return self._label

    def get_value(self) -> int:
        """Returns the assigned value for this label.

        If and address label, the address will be returned. If a constant label, the assigned value is returned
        """
        if self._value is None:
            # this is a Label, return the address for value
            return self.address
        else:
            return self._value
