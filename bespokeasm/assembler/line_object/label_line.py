import re
import sys

from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject, INSTRUCTION_EXPRESSION_PATTERN
from bespokeasm.assembler.line_object.utility import is_valid_label
from bespokeasm.utilities import is_string_numeric, parse_numeric_string, PATTERN_NUMERIC
from bespokeasm.expression import parse_expression, ExpresionType

class LabelLine(LineObject):
    PATTERN_LABEL = re.compile(
        r'^\s*((\.?\w+):)(?:\s*([^;]*))?\;?',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_CONSTANT = re.compile(
        f'^\s*(\w+)(?:\s*)?\=(?:\s*)?({INSTRUCTION_EXPRESSION_PATTERN}|)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    @classmethod
    def factory(
                cls,
                line_id: LineIdentifier,
                line_str: str,
                comment: str,
                registers: set[str],
                label_scope: LabelScope,
            ) -> LineObject:
        """Tries to match the passed line string to the Label or Constant directive patterns.
        If succcessful, returns a constructed LabelLine object. If not, None is
        returned.
        """
        # first determine if there is a label
        label_match = re.search(LabelLine.PATTERN_LABEL, line_str)
        if label_match is not None:
            # set this line up as a label
            label_val = label_match.group(2).strip()
            if is_valid_label(label_val):
                if label_val in registers:
                    sys.exit(f'ERROR: {line_id} - used the register label "{label_val}" as a non-register label')
                return LabelLine(line_id, label_val, None, label_match.group(1).strip(), comment)

        # Now determine is the line is a constant
        constant_match = re.search(LabelLine.PATTERN_CONSTANT, line_str)
        if constant_match is not None and len(constant_match.groups()) == 2:
            value_expr = parse_expression(line_id, constant_match.group(2).strip())
            if value_expr.contains_register_labels(registers):
                sys.exit(f'ERROR: {line_id} - Expression contains register label')
            constant_label = constant_match.group(1).strip()
            if not is_valid_label(constant_label):
                sys.exit(f'ERROR: {line_id} - invalid format for constant label: {constant_label}')
            if constant_label in registers:
                sys.exit(f'ERROR: {line_id} - used the register label "{constant_label}" as a non-register label')
            try:
                line_obj = LabelLine(
                    line_id,
                    constant_label,
                    value_expr.get_value(label_scope, line_id),
                    line_str,
                    comment,
                )
            except ValueError as e:
                sys.exit(f'ERROR: {line_id} - Constant assigned nonnumeric value because {e}')
            return line_obj
        #if we got here it was neither a Label or a Constant
        return None

    @classmethod
    def parse_same_line_instruction(cls, line_id: LineIdentifier, line_str: str) -> str:
        '''Parses a instruction string that has already been identified as a label line to see
           if there is a second instruction on the line. If so, return that string, otherwise None.
        '''
        label_match = re.search(LabelLine.PATTERN_LABEL, line_str)
        if label_match is not None:
            instr_str = label_match.group(3)
            if instr_str is not None and len(instr_str.strip()) > 0:
                return instr_str.strip()
        return None

    def __init__(self, line_id: LineIdentifier, label: str, value: int, instruction: str, comment: str):
        super().__init__(line_id, instruction, comment)
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
