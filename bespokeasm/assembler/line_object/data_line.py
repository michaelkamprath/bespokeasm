import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes
from bespokeasm.utilities import parse_numeric_string, is_string_numeric

class DataLine(LineWithBytes):
    PATTERN_DATA_DIRECTIVE = re.compile(
        r'^(\.byte|\.2byte|\.4byte|\.cstr)\s*(?:([\w,$\%\s]+)|(?P<quote>[\"\']{1})((?:\\(?P=quote)|.)*)(?P=quote))',
        flags=re.IGNORECASE|re.MULTILINE
    )

    DIRECTIVE_VALUE_BYTE_SIZE = {
        '.byte': 1,
        '.2byte': 2,
        '.4byte': 4,
        '.cstr': 1,
    }

    DIRECTIVE_VALUE_MASK = {
        '.byte': 0xFF,
        '.2byte': 0xFFFF,
        '.4byte': 0xFFFFFFFF,
        '.cstr': 0xFF,
    }
    def factory(line_id: LineIdentifier, line_str: str, comment: str, endian: str) -> LineWithBytes:
        """Tries to match the passed line string to the data directive pattern.
        If succcessful, returns a constructed DataLine object. If not, None is
        returned.
        """
        data_match = re.search(DataLine.PATTERN_DATA_DIRECTIVE, line_str.strip())
        # deterine if this is a string or numeric list
        if data_match is not None and len(data_match.groups()) == 4:
            directive_str = data_match.group(1).strip()
            if data_match.group(4) is None and data_match.group(2) is not None:
                # it's numeric
                values_list = [x.strip() for x in data_match.group(2).strip().split(',') if x.strip() != '']
            elif data_match.group(4) is not None:
                # its a string.
                values_list = [ord(x) for x in data_match.group(4)]
                if directive_str == '.cstr':
                    # Add a 0-value at the end of the string values.
                    values_list.extend([0])
            else:
                # don't know what this is
                return None

            return DataLine(
                line_id,
                directive_str,
                values_list,
                line_str,
                comment,
                endian,
            )
        else:
            return None

    def __init__(self, line_id: LineIdentifier, directive_str: str, value_list: list, instruction: str, comment: str, endian: str):
        super().__init__(line_id, instruction, comment)
        self._arg_value_list = value_list
        self._directive = directive_str
        self._endian = endian

    def __str__(self):
        return f'DataLine<{self._directive}: {self._arg_value_list}>'

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this data line will generate"""
        return len(self._arg_value_list)*DataLine.DIRECTIVE_VALUE_BYTE_SIZE[self._directive]

    def generate_bytes(self):
        """Finalize the data bytes for this line with the label assignemnts"""
        for arg_item in self._arg_value_list:
            if isinstance(arg_item, int):
                arg_val = arg_item
            elif isinstance(arg_item, str):
                if is_string_numeric(arg_item):
                    arg_val = parse_numeric_string(arg_item)
                else:
                    label_val = self.label_scope.get_label_value(arg_item, self.line_id)
                    if label_val is not None:
                        arg_val = label_val
                    else:
                        sys.exit(f'ERROR: line {self.line_id} - unknown label "{arg_item}" in current scope "{self.label_scope}"')
            else:
                sys.exit(f'ERROR: line {self.line_id} - unknown data item "{arg_item}"')
            value_bytes = (arg_val&DataLine.DIRECTIVE_VALUE_MASK[self._directive]).to_bytes(
                DataLine.DIRECTIVE_VALUE_BYTE_SIZE[self._directive],
                byteorder=self._endian,
                signed=(arg_val < 0)
            )
            for b in value_bytes:
                self._append_byte(b)

