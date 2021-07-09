import re
import sys

from bespokeasm.assembler.line_object import LineWithBytes, LineObject
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.utilities import parse_numeric_string, is_string_numeric

# Directives are lines that tell the assembler to do something. Supported directives are:
#
#   .org X          - (re)sets the current address to X but does not pad. Shou;d be used at top of code.
#   .byte X         - Emits byte or set of bytes
#   .fill X, Y      - Fills X bytes from curent address with (Y&0xFF)
#   .zero X         - shorthand for ".fill X, 0"
#   .zerountil X    - fill with 0 value until and including address X


class DirectiveLine:
    DIRECTIVE_SET = set([
        '.org', 'org', '.fill', 'fill',
        '.zero', 'zero', '.zerountil', 'zerountil',
        '.byte', 'byte', '.2byte', '2byte',
        '.4byte', '4byte',
    ])
    PATTERN_ORG_DIRECTIVE = re.compile(
        r'^(?:\.org)\s+(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_FILL_DIRECTIVE = re.compile(
        r'^(?:\.fill)\s+(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)\s*\,\s*(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_ZERO_DIRECTIVE = re.compile(
        r'^(?:\.zero)\s+(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_ZEROUNTIL_DIRECTIVE = re.compile(
        r'^(?:\.zerountil)\s+(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    def factory(line_num: int, line_str: str, comment: str):
        # for efficiency, if it doesn't start with a period, it is not a directive
        cleaned_line_str = line_str.strip()
        if not cleaned_line_str.startswith('.'):
            return None
        # first, the .org
        line_match = re.search(DirectiveLine.PATTERN_ORG_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            value_str = line_match.group(1)
            if is_string_numeric(value_str):
                return AddressOrgLine(line_num, line_str, comment, parse_numeric_string(value_str))
            else:
                 sys.exit(f'ERROR: line {line_num} - .org directive value is not numeric')

        # .fill
        line_match = re.search(DirectiveLine.PATTERN_FILL_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 2:
            count_str = line_match.group(1)
            value_str = line_match.group(2)
            if is_string_numeric(count_str) and is_string_numeric(value_str):
                return FillDataLine(
                    line_num, line_str, comment,
                    parse_numeric_string(count_str),
                    parse_numeric_string(value_str),
                )
            else:
                sys.exit(f'ERROR: line {line_num} - .fill directive values are not numeric')

        # .zero
        line_match = re.search(DirectiveLine.PATTERN_ZERO_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            count_str = line_match.group(1)
            if is_string_numeric(count_str):
                return FillDataLine(
                    line_num, line_str, comment,
                    parse_numeric_string(count_str),
                    0,
                )
            else:
                sys.exit(f'ERROR: line {line_num} - .zero directive value is not numeric')

        # .zerountil
        line_match = re.search(DirectiveLine.PATTERN_ZEROUNTIL_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            address_str = line_match.group(1)
            if is_string_numeric(address_str):
                return FillUntilDataLine(
                    line_num, line_str, comment,
                    parse_numeric_string(address_str),
                    0,
                )
            else:
                sys.exit(f'ERROR: line {line_num} - .zero directive value is not numeric')

        # nothing was matched here. pass to data directive
        return DataLine.factory(line_num, line_str, comment)

class AddressOrgLine(LineObject):
    def __init__(self, line_num: int, instruction: str, comment: str, address: int):
        super().__init__(line_num, instruction, comment)
        self._address = address


    def set_start_address(self, address: int):
        """A no-op for the .org directive
        """
        return


class FillDataLine(LineWithBytes):
    def __init__(self, line_num: int, instruction: str, comment: str, fill_count: int, fill_value: int):
        super().__init__(line_num, instruction, comment)
        self._bytes.extend([fill_value&0xFF]*fill_count)

    @property
    def byte_size(self) -> int:
        return len(self._bytes)

class FillUntilDataLine(LineWithBytes):
    def __init__(self, line_num: int, instruction: str, comment: str, fill_until_address: int, fill_value: int):
        super().__init__(line_num, instruction, comment)
        self._fill_until_addr = fill_until_address
        self._fill_value = fill_value&0xFF

    @property
    def byte_size(self) -> int:
        if self._fill_until_addr >= self.address:
            return self._fill_until_addr - self.address + 1
        else:
            return 0

    def generate_bytes(self, label_dict: dict[str, int]):
        """Finalize the bytes for this fill until line.
        """
        if self.byte_size > 0 and len(self._bytes) == 0:
            self._bytes.extend([self._fill_value]*self.byte_size)
