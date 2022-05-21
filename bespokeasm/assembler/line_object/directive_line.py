import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes, LineObject, INSTRUCTION_EXPRESSION_PATTERN
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.expression import parse_expression, ExpresionType


# Directives are lines that tell the assembler to do something. Supported directives are:
#
#   .org X          - (re)sets the current address to X but does not pad. Shou;d be used at top of code.
#   .byte X         - Emits byte or set of bytes
#   .fill X, Y      - Fills X bytes from curent address with (Y&0xFF)
#   .zero X         - shorthand for ".fill X, 0"
#   .zerountil X    - fill with 0 value until and including address X


class DirectiveLine:

    PATTERN_ORG_DIRECTIVE = re.compile(
        f'^(?:\.org)\s+({INSTRUCTION_EXPRESSION_PATTERN})',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_FILL_DIRECTIVE = re.compile(
        f'^(?:\.fill)\s+({INSTRUCTION_EXPRESSION_PATTERN})\s*\,\s*({INSTRUCTION_EXPRESSION_PATTERN})',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_ZERO_DIRECTIVE = re.compile(
        f'^(?:\.zero)\s+({INSTRUCTION_EXPRESSION_PATTERN})',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_ZEROUNTIL_DIRECTIVE = re.compile(
        f'^(?:\.zerountil)\s+({INSTRUCTION_EXPRESSION_PATTERN})',
        flags=re.IGNORECASE|re.MULTILINE
    )

    def factory(line_id: LineIdentifier, line_str: str, comment: str, isa_model: AssemblerModel) -> LineObject:
        endian = isa_model.endian
        # for efficiency, if it doesn't start with a period, it is not a directive
        cleaned_line_str = line_str.strip()
        if not cleaned_line_str.startswith('.'):
            return None
        # first, the .org
        line_match = re.search(DirectiveLine.PATTERN_ORG_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            value_str = line_match.group(1)
            return AddressOrgLine(line_id, line_str, comment, value_str)

        # .fill
        line_match = re.search(DirectiveLine.PATTERN_FILL_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 2:
            count_str = line_match.group(1)
            value_str = line_match.group(2)
            return FillDataLine(
                line_id, line_str, comment,
                count_str,
                value_str,
            )

        # .zero
        line_match = re.search(DirectiveLine.PATTERN_ZERO_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            count_str = line_match.group(1)
            if len(count_str) == 0:
                sys.exit(f'ERROR: {line_id} - .zero directive missing length argument')
            return FillDataLine(
                line_id, line_str, comment,
                count_str,
                '0',
            )

        # .zerountil
        line_match = re.search(DirectiveLine.PATTERN_ZEROUNTIL_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            address_str = line_match.group(1)
            return FillUntilDataLine(
                line_id, line_str, comment,
                address_str,
                '0',
            )

        # nothing was matched here. pass to data directive
        return DataLine.factory(line_id, line_str, comment, endian)


class AddressOrgLine(LineObject):
    def __init__(self, line_id: LineIdentifier, instruction: str, comment: str, address_expression: str):
        super().__init__(line_id, instruction, comment)
        self._address_expr = parse_expression(line_id, address_expression)

    @property
    def address(self) -> int:
        """Returns the adjusted address value set by the .org directive.
        """
        return self._address_expr.get_value(self.label_scope, self.line_id)

    def set_start_address(self, address: int):
        """A no-op for the .org directive
        """
        return


class FillDataLine(LineWithBytes):
    _count_expr: ExpresionType
    _value_expr: ExpresionType

    def __init__(self, line_id: LineIdentifier, instruction: str, comment: str, fill_count_expression: str, fill_value_expression: str):
        super().__init__(line_id, instruction, comment)
        self._count_expr = parse_expression(line_id, fill_count_expression)
        self._value_expr = parse_expression(line_id, fill_value_expression)
        self._count = None
        self._value = None

    @property
    def byte_size(self) -> int:
        if self._count is None:
            self._count = self._count_expr.get_value(self.label_scope, self.line_id)
        return self._count

    def generate_bytes(self):
        if self._count is None:
            self._count = self._count_expr.get_value(self.label_scope, self.line_id)
        if self._value is None:
            self._value = self._value_expr.get_value(self.label_scope, self.line_id)
        self._bytes.extend([(self._value)&0xFF]*self._count)

class FillUntilDataLine(LineWithBytes):
    _fill_until_addr_expr: ExpresionType
    _fill_value_expr: ExpresionType
    _fill_until_addr: int
    _fill_value: int

    def __init__(self, line_id: LineIdentifier, instruction: str, comment: str, fill_until_address_expresion: str, fill_value_expression: str):
        super().__init__(line_id, instruction, comment)
        self._fill_until_addr_expr = parse_expression(line_id, fill_until_address_expresion)
        self._fill_value_expr = parse_expression(line_id, fill_value_expression)
        self._fill_until_addr = None
        self._fill_value = None

    @property
    def byte_size(self) -> int:
        if self._fill_until_addr is None:
            self._fill_until_addr = self._fill_until_addr_expr.get_value(self.label_scope, self.line_id)
        if self._fill_until_addr >= self.address:
            return self._fill_until_addr - self.address + 1
        else:
            return 0

    def generate_bytes(self):
        """Finalize the bytes for this fill until line.
        """
        if self._fill_until_addr is None:
            self._fill_until_addr = self._fill_until_addr_expr.get_value(self.label_scope, self.line_id)
        if self._fill_value is None:
            self._fill_value = self._fill_value_expr.get_value(self.label_scope, self.line_id)
        if self.byte_size > 0 and len(self._bytes) == 0:
            self._bytes.extend([self._fill_value&0xFF]*self.byte_size)
