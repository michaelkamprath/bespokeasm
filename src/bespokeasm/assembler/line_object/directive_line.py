import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes, LineObject, INSTRUCTION_EXPRESSION_PATTERN
from bespokeasm.assembler.line_object.data_line import DataLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager, GLOBAL_ZONE_NAME
from bespokeasm.expression import parse_expression, ExpressionNode
from bespokeasm.assembler.memory_zone import MEMORY_ZONE_NAME_PATTERN, MemoryZone

# Directives are lines that tell the assembler to do something. Supported directives are:
#
#   .org X          - (re)sets the current address to X but does not pad. Shou;d be used at top of code.
#   .byte X         - Emits byte or set of bytes
#   .fill X, Y      - Fills X bytes from curent address with (Y&0xFF)
#   .zero X         - shorthand for ".fill X, 0"
#   .zerountil X    - fill with 0 value until and including address X


class DirectiveLine:

    PATTERN_ORG_DIRECTIVE = re.compile(
        r'^(?:\.org)\s+({0})(?:\s*\"({1})\")?'.format(
            INSTRUCTION_EXPRESSION_PATTERN,
            MEMORY_ZONE_NAME_PATTERN,
        ),
        flags=re.IGNORECASE | re.MULTILINE
    )

    PATTERN_SET_MEMZONE_DIRECTIVE = re.compile(
        r'^(?:\.memzone)\s+({0})'.format(MEMORY_ZONE_NAME_PATTERN),
        flags=re.IGNORECASE | re.MULTILINE
    )

    PATTERN_FILL_DIRECTIVE = re.compile(
        r'^(?:\.fill)\s+({0})\s*\,\s*({1})'.format(
            INSTRUCTION_EXPRESSION_PATTERN, INSTRUCTION_EXPRESSION_PATTERN
        ),
        flags=re.IGNORECASE | re.MULTILINE
    )

    PATTERN_ZERO_DIRECTIVE = re.compile(
        r'^(?:\.zero)\s+({0})'.format(INSTRUCTION_EXPRESSION_PATTERN),
        flags=re.IGNORECASE | re.MULTILINE
    )

    PATTERN_ZEROUNTIL_DIRECTIVE = re.compile(
        r'^(?:\.zerountil)\s+({0})'.format(INSTRUCTION_EXPRESSION_PATTERN),
        flags=re.IGNORECASE | re.MULTILINE
    )

    def factory(
        line_id: LineIdentifier,
        line_str: str,
        comment: str,
        endian: str,
        current_memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        cstr_terminator: int = 0,
    ) -> LineObject:
        # for efficiency, if it doesn't start with a period, it is not a directive
        cleaned_line_str = line_str.strip()
        if not cleaned_line_str.startswith('.'):
            return None
        # first, the .org
        line_match = re.search(DirectiveLine.PATTERN_ORG_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) >= 1:
            value_str = line_match.group(1)
            memzone_name = line_match.group(2)
            return AddressOrgLine(line_id, line_match.group(0), comment, value_str, memzone_name, memzone_manager)

        # .memzone
        line_match = re.search(DirectiveLine.PATTERN_SET_MEMZONE_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            name_str = line_match.group(1)
            return SetMemoryZoneLine(line_id, line_match.group(0), comment, name_str, memzone_manager)

        # .fill
        line_match = re.search(DirectiveLine.PATTERN_FILL_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 2:
            count_str = line_match.group(1)
            value_str = line_match.group(2)
            return FillDataLine(
                line_id,
                line_match.group(0),
                comment,
                count_str,
                value_str,
                current_memzone,
            )

        # .zero
        line_match = re.search(DirectiveLine.PATTERN_ZERO_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            count_str = line_match.group(1)
            if len(count_str) == 0:
                sys.exit(f'ERROR: {line_id} - .zero directive missing length argument')
            return FillDataLine(
                line_id,
                line_match.group(0),
                comment,
                count_str,
                '0',
                current_memzone,
            )

        # .zerountil
        line_match = re.search(DirectiveLine.PATTERN_ZEROUNTIL_DIRECTIVE, cleaned_line_str)
        if line_match is not None and len(line_match.groups()) == 1:
            address_str = line_match.group(1)
            return FillUntilDataLine(
                line_id,
                line_match.group(0),
                comment,
                address_str,
                '0',
                current_memzone,
            )

        # nothing was matched here. pass to data directive
        return DataLine.factory(line_id, line_str, comment, endian, current_memzone, cstr_terminator)


class SetMemoryZoneLine(LineObject):
    def __init__(
            self,
            line_id: LineIdentifier,
            instruction: str,
            comment: str,
            name_str: str,
            memzone_manager: MemoryZoneManager,
    ) -> None:
        self._memzone_manager = memzone_manager
        if name_str is None:
            self._name = GLOBAL_ZONE_NAME
        else:
            self._name = name_str
        memzone = memzone_manager.zone(self._name)
        if memzone is None:
            sys.exit(f'ERROR: {line_id} - unknown memory zone "{name_str}"')
        super().__init__(line_id, instruction, comment, memzone)

    @property
    def memzone_manager(self) -> MemoryZoneManager:
        return self._memzone_manager

    @property
    def memory_zone_name(self) -> int:
        """Returns the name of the memory zone set by .memzone.
        """
        return self._name


class AddressOrgLine(SetMemoryZoneLine):
    def __init__(
            self,
            line_id:
            LineIdentifier,
            instruction: str,
            comment: str,
            address_expression: str,
            memzone_name: str,
            memzone_manager: MemoryZoneManager,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone_name, memzone_manager)
        self._parsed_memzone_name = memzone_name
        self._address_expr = parse_expression(line_id, address_expression)

    @property
    def address(self) -> int:
        """Returns the adjusted address value set by the .org directive.
        """
        offset_value = self._address_expr.get_value(self.label_scope, self.line_id)
        if self._parsed_memzone_name is None:
            value = offset_value
        else:
            value = self.memory_zone.start + offset_value
        if value < self.memzone_manager.global_zone.start:
            sys.exit(
                f'ERROR: {self.line_id} - .org address value of {value} is less than the minimum '
                f'address of {self.memzone_manager.global_zone.start} in memory zone {self._memzone.name}'
            )
        if value > self.memzone_manager.global_zone.end:
            sys.exit(
                f'ERROR: {self.line_id} - .org address value of {value} is greater than the maximum '
                f'address of {self.memzone_manager.global_zone.end} in memory zone {self._memzone.name}'
            )
        return value

    def set_start_address(self, address: int):
        """A no-op for the .org directive
        """
        return


class FillDataLine(LineWithBytes):
    _count_expr: ExpressionNode
    _value_expr: ExpressionNode

    def __init__(
            self,
            line_id: LineIdentifier,
            instruction: str,
            comment: str,
            fill_count_expression: str,
            fill_value_expression: str,
            current_memzone: MemoryZone,
    ) -> None:
        super().__init__(line_id, instruction, comment, current_memzone)
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
        self._bytes.extend([(self._value) & 0xFF]*self._count)


class FillUntilDataLine(LineWithBytes):
    _fill_until_addr_expr: ExpressionNode
    _fill_value_expr: ExpressionNode
    _fill_until_addr: int
    _fill_value: int

    def __init__(
            self,
            line_id: LineIdentifier,
            instruction: str,
            comment: str,
            fill_until_address_expresion: str,
            fill_value_expression: str,
            current_memzone: MemoryZone,
    ) -> None:
        super().__init__(line_id, instruction, comment, current_memzone)
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
            self._bytes.extend([self._fill_value & 0xFF]*self.byte_size)
