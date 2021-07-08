import re
import sys

from bespokeasm.utilities import parse_numeric_string, is_string_numeric
from bespokeasm.assembler.line_object import LineWithBytes

class DataLine(LineWithBytes):
    PATTERN_DATA_DIRECTIVE = re.compile(
        r'^(\.byte)\s*(?:([\w,$\s]+)|(?P<quote>[\"\']{1})((?:\\(?P=quote)|.)*)(?P=quote))',
        flags=re.IGNORECASE|re.MULTILINE
    )

    DIRECTIVE_VALUE_BYTE_SIZE = {
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
        # deterine if this is a string or numeric list
        if data_match is not None and len(data_match.groups()) == 4:
            if data_match.group(4) is None and data_match.group(2) is not None:
                # it's numeric
                values_list = [x.strip() for x in data_match.group(2).strip().split(',') if x.strip() != '']
            elif data_match.group(4) is not None:
                # its a string.
                values_list = [ord(x) for x in data_match.group(4).strip()]
                # Add a 0-value at the end of the string values.
                values_list.extend([0])
            else:
                # don't know what this is
                return None

            return DataLine(
                line_num,
                data_match.group(1).strip(),
                values_list,
                line_str,
                comment,
            )
        else:
            return None

    def __init__(self, line_num: int, directive_str: str, value_list: list, instruction: str, comment: str, is_string = False):
        super().__init__(line_num, instruction, comment)
        self._arg_value_list = value_list
        self._directive = directive_str

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this data line will generate"""
        return len(self._arg_value_list)*DataLine.DIRECTIVE_VALUE_BYTE_SIZE[self._directive]

    def generate_bytes(self, label_dict: dict[str, int]):
        """Finalize the data bytes for this line with the label assignemnts"""
        for arg_item in self._arg_value_list:
            if isinstance(arg_item, int):
                arg_val = arg_item
            elif isinstance(arg_item, str):
                if is_string_numeric(arg_item):
                    arg_val = parse_numeric_string(arg_item)
                elif arg_item in label_dict:
                    arg_val = label_dict[arg_item]
                else:
                    sys.exit(f'ERROR: line {self.line_number()} - unknown label "{arg_item}"')
            else:
                sys.exit(f'ERROR: line {self.line_number()} - unknown data item "{arg_item}"')
            self._append_byte(arg_val&DataLine.DIRECTIVE_VALUE_MASK[self._directive])

