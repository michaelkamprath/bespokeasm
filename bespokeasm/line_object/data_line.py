import re
import sys

from bespokeasm.utilities import parse_numeric_string, is_string_numeric
from bespokeasm.line_object import LineWithBytes

class DataLine(LineWithBytes):
    PATTERN_DATA_DIRECTIVE = re.compile(
        r'^(\.byte)\s*([\w,$\s]+)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    DIRECTIVE_BYTE_SIZE = {
        '.byte': 1,
    }

    DIRECTIVE_VALUE_MASK = {
        '.byte': 0xFF,
    }
    def factory(line_num: int, line_str: str, comment: str):
        """Tries to match the passed line string to the data directive pattern.
        If succcessful, returns a constructed DataLine object. If not, None is
        returned.
        """
        data_match = re.search(DataLine.PATTERN_DATA_DIRECTIVE, line_str.strip())
        if data_match is not None and len(data_match.groups()) == 2:
            return DataLine(
                line_num,
                data_match.group(1).strip(),
                data_match.group(2).strip(),
                line_str,
                comment,
            )
        else:
            return None

    def __init__(self, line_num: int, directive_str: str, arguments_str: str, instruction: str, comment: str):
        super().__init__(line_num, instruction, comment)
        self._arg_str_list = [x.strip() for x in arguments_str.split(',') if x.strip() != '']
        self._directive = directive_str

    def byte_size(self) -> int:
        """Returns the number of bytes this data line will generate"""
        return len(self._arg_str_list)*DataLine.DIRECTIVE_BYTE_SIZE[self._directive]

    def generate_bytes(self, label_dict: dict[str, int]):
        """Finalize the data bytes for this line with the label assignemnts"""
        for arg_str in self._arg_str_list:
            if is_string_numeric(arg_str):
                arg_val = parse_numeric_string(arg_str)
            elif arg_str in label_dict:
                arg_val = label_dict[arg_str]
            else:
                sys.exit(f'ERROR: line {self.line_number()} - unknown label "{arg_str}"')
            self._append_byte(arg_val)

