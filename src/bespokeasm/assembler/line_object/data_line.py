import math
import re
import sys
from typing import Literal

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import parse_expression


class DataLine(LineWithWords):
    PATTERN_DATA_DIRECTIVE = re.compile(
        r'^(\.byte|\.2byte|\.4byte|\.8byte|\.16byte|\.cstr|\.asciiz)\b\s*(.*)$',
        flags=re.IGNORECASE
    )

    DIRECTIVE_VALUE_BYTE_SIZE = {
        '.byte': 1,
        '.2byte': 2,
        '.4byte': 4,
        '.8byte': 8,
        '.16byte': 16,
        '.cstr': 1,
        '.asciiz': 1,
    }

    DIRECTIVE_VALUE_MASK = {
        '.byte': 0xFF,
        '.2byte': 0xFFFF,
        '.4byte': 0xFFFFFFFF,
        '.8byte': 0xFFFFFFFFFFFFFFFF,
        '.16byte': 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
        '.cstr': 0xFF,
        '.asciiz': 0xFF,
    }

    def factory(
            line_id: LineIdentifier,
            line_str: str,
            comment: str,
            current_memzone: MemoryZone,
            word_size: int,
            word_segment_size: int,
            intra_word_endianness: Literal['little', 'big'],
            multi_word_endianness: Literal['little', 'big'],
            cstr_terminator: int = 0,
            string_byte_packing: bool = False,
            string_byte_packing_fill: int = 0,
            *,
            diagnostic_reporter,
    ) -> LineWithWords:
        """Tries to match the passed line string to the data directive pattern.
        If succcessful, returns a constructed DataLine object. If not, None is
        returned.
        """
        data_match = re.search(DataLine.PATTERN_DATA_DIRECTIVE, line_str.strip())
        if data_match is None:
            return None

        directive_str = data_match.group(1).strip()
        args_str = data_match.group(2).strip()
        if args_str == '':
            return None

        value_items = DataLine._split_data_items(args_str, line_id)
        if len(value_items) == 0:
            return None

        values_list = []
        if directive_str in ('.cstr', '.asciiz'):
            if len(value_items) != 1:
                sys.exit(f'ERROR: {line_id} - {directive_str} data directive used with non-string value')
            string_values = DataLine._extract_string_item(value_items[0], line_id, directive_str)
            values_list.extend(string_values)
            values_list.extend([cstr_terminator])
        else:
            for item in value_items:
                if DataLine._is_quoted_item(item):
                    string_values = DataLine._extract_string_item(item, line_id, directive_str)
                    if directive_str != '.byte':
                        sys.exit(f'ERROR: {line_id} - {directive_str} data directive used with string value')
                    values_list.extend(string_values)
                else:
                    values_list.append(item)

        return DataLine(
            line_id,
            directive_str,
            values_list,
            line_str,
            comment,
            current_memzone,
            word_size,
            word_segment_size,
            intra_word_endianness,
            multi_word_endianness,
            string_byte_packing,
            string_byte_packing_fill,
            diagnostic_reporter=diagnostic_reporter,
        )

    @staticmethod
    def _split_data_items(args_str: str, line_id: LineIdentifier) -> list[str]:
        """Split comma-separated data items while respecting quoted strings."""
        items = []
        token_chars = []
        quote_char = None
        escape_next = False

        for ch in args_str:
            if quote_char is not None:
                token_chars.append(ch)
                if escape_next:
                    escape_next = False
                elif ch == '\\':
                    escape_next = True
                elif ch == quote_char:
                    quote_char = None
                continue

            if ch in ('"', '\''):
                quote_char = ch
                token_chars.append(ch)
            elif ch == ',':
                item = ''.join(token_chars).strip()
                if item != '':
                    items.append(item)
                token_chars = []
            else:
                token_chars.append(ch)

        if quote_char is not None:
            sys.exit(f'ERROR: {line_id} - unterminated string in data directive')

        item = ''.join(token_chars).strip()
        if item != '':
            items.append(item)
        return items

    @staticmethod
    def _is_quoted_item(item_str: str) -> bool:
        if len(item_str) < 2:
            return False
        quote = item_str[0]
        return quote in ('"', '\'') and item_str[-1] == quote

    @staticmethod
    def _extract_string_item(item_str: str, line_id: LineIdentifier, directive_str: str) -> list[int]:
        if not DataLine._is_quoted_item(item_str):
            sys.exit(f'ERROR: {line_id} - {directive_str} data directive used with non-string value')
        converted_str = bytes(item_str[1:-1], 'utf-8').decode('unicode_escape')
        return [ord(x) for x in converted_str]

    def __init__(
            self,
            line_id: LineIdentifier,
            directive_str: str,
            value_list: list,
            instruction: str,
            comment: str,
            current_memzone: MemoryZone,
            word_size: int,
            word_segment_size: int,
            intra_word_endianness: Literal['little', 'big'],
            multi_word_endianness: Literal['little', 'big'],
            string_byte_packing: bool = False,
            string_byte_packing_fill: int = 0,
            *,
            diagnostic_reporter,
    ) -> None:
        super().__init__(
            line_id,
            instruction,
            comment,
            current_memzone,
            word_size,
            word_segment_size,
            intra_word_endianness,
            multi_word_endianness,
        )
        if diagnostic_reporter is None:
            raise ValueError('DiagnosticReporter is required for DataLine')
        self.diagnostic_reporter = diagnostic_reporter
        self._arg_value_list = value_list
        self._directive = directive_str
        self._string_byte_packing = string_byte_packing
        self._string_byte_packing_fill = string_byte_packing_fill

    def __str__(self):
        return f'DataLine<{self._directive}: {self._arg_value_list}>'

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this data line will generate"""
        return len(self._arg_value_list)*DataLine.DIRECTIVE_VALUE_BYTE_SIZE[self._directive]

    @property
    def word_count(self) -> int:
        """Returns the number of words this data line will generate, matching generate_words logic."""
        word_size_bytes = self._word_size // 8
        count = 0
        for arg_item in self._arg_value_list:
            value_size = DataLine.DIRECTIVE_VALUE_BYTE_SIZE[self._directive]
            if value_size <= word_size_bytes:
                count += 1
            else:
                # Value is larger than word size, split across multiple words
                count += math.ceil(value_size / word_size_bytes)
        return count

    def generate_words(self):
        """Finalize the data bytes for this line with the label assignments, matching documentation rules."""
        # If string_byte_packing is enabled and this is a string-based .byte/.cstr/.asciiz, pack bytes into words
        if (
            self._string_byte_packing
            and self._directive in ('.byte', '.cstr', '.asciiz')
            and all(isinstance(x, int) for x in self._arg_value_list)
        ):
            word_bytes = self._word_size // 8
            values = self._arg_value_list[:]
            # Pad to full word if needed, using string_byte_packing_fill
            if len(values) % word_bytes != 0:
                pad_len = word_bytes - (len(values) % word_bytes)
                values += [self._string_byte_packing_fill] * pad_len
            for i in range(0, len(values), word_bytes):
                chunk = values[i:i+word_bytes]
                if self._multi_word_endianness == 'big':
                    word_val = 0
                    for b in chunk:
                        word_val = (word_val << 8) | (b & 0xFF)
                else:
                    word_val = 0
                    for j, b in enumerate(chunk):
                        word_val |= (b & 0xFF) << (8 * j)
                self._words.append(
                    Word(word_val, self._word_size, self._word_segment_size, self._intra_word_endianness)
                )
            return
        # Default behavior
        for arg_item in self._arg_value_list:
            if isinstance(arg_item, int):
                arg_val = arg_item
            elif isinstance(arg_item, str):
                e: ExpressionNode = parse_expression(self.line_id, arg_item)
                arg_val = e.get_value(self.label_scope, self.active_named_scopes, self.line_id)
            else:
                sys.exit(f'ERROR: line {self.line_id} - unknown data item "{arg_item}"')
            value_size = DataLine.DIRECTIVE_VALUE_BYTE_SIZE[self._directive]
            value_mask = DataLine.DIRECTIVE_VALUE_MASK[self._directive]
            masked_val = arg_val & value_mask
            if (
                self._directive in ('.byte', '.2byte', '.4byte', '.8byte', '.16byte')
                and masked_val != arg_val
            ):
                self.diagnostic_reporter.warn(
                    self.line_id,
                    f'Data value {arg_val} truncated to {masked_val} for {self._directive}',
                )
            # If value size <= word size, put in its own word, zero-extended
            if value_size <= self._word_size // 8:
                # Place in least significant bits, zero-extended
                self._words.append(
                    Word(masked_val, self._word_size, self._word_segment_size, self._intra_word_endianness)
                )
            else:
                # Value is larger than word size, split across multiple words
                total_bytes = value_size
                word_bytes = self._word_size // 8
                value_bytes = masked_val.to_bytes(total_bytes, byteorder=self._multi_word_endianness, signed=False)
                # Split into word-sized chunks
                for i in range(0, total_bytes, word_bytes):
                    chunk = value_bytes[i:i+word_bytes]
                    # Pad chunk if not full word
                    if len(chunk) < word_bytes:
                        chunk = (b'\x00' * (word_bytes - len(chunk))) + chunk if self._multi_word_endianness == 'big' \
                            else chunk + (b'\x00' * (word_bytes - len(chunk)))
                    wval = int.from_bytes(chunk, byteorder=self._multi_word_endianness)
                    self._words.append(
                        Word(wval, self._word_size, self._word_segment_size, self._intra_word_endianness)
                    )
