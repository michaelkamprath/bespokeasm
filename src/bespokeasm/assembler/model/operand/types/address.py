# The address operand type is a `NumericExpressionOperand` that enforces some conditions
# are the argument pertaining to addresses. The features this operand supports:
# - The argument value must be a valid address in a given memory zone (defaults to the global zone)
# - The bytecode of the argument value (the address) can be sliced into the least significant byte(s),
#   to enable "fast jumps" in the assembler.
#   * The expected significant bytes can either be configured to a specific value (e.g., "zero page")
#     or to the same as the current instruction's address. If the operand's value has a signficant byte(s)
#     that is not what is expected, the assembler will raise an error.
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.operand.types.numeric_expression import NumericExpressionOperand
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager, GLOBAL_ZONE_NAME
from bespokeasm.assembler.model.operand import OperandType, ParsedOperand
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart, ExpressionByteCodePartInMemoryZone
from bespokeasm.assembler.label_scope import LabelScope


class AddressByteCodePart(ExpressionByteCodePartInMemoryZone):
    def __init__(
        self,
        value_expression: str,
        value_size: int,
        byte_align: bool,
        endian: str,
        line_id: LineIdentifier,
        memzone: MemoryZone,
        is_lsb_bytes: bool,
        match_address_msb: bool,
    ) -> None:
        """Creates a new address bytecode part that is bound to a memory zone.
           The address value is sliced into the least significant bit(s) if `is_lsb_bytes` is true,
           ensuring that the MSBs match the current instruction's address MSBs."""
        super().__init__(memzone, value_expression, value_size, byte_align, endian, line_id)
        self._is_lsb_bytes = is_lsb_bytes
        self._match_address_msb = match_address_msb

    def __str__(self) -> str:
        return f'AddressByteCodePart<expression="{self._expression}",zone={self._memzone},' \
               f'slice_lab={self._is_lsb_bytes},match_msb={self._match_address_msb}>'

    def get_value(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> int:
        if instruction_address is None:
            raise ValueError('AddressByteCodePart.get_value had no instruction_address passed')
        value = super().get_value(label_scope, instruction_address, instruction_size)

        if self._is_lsb_bytes and self._match_address_msb:
            # mask out the MSBs of the address value. The`value_size` is interpreted as the number of LSB bytes
            mask = (1 << self.value_size) - 1
            final_value = value & mask
            # check if the MSBs of the value match the MSBs of the instruction address
            shifted_address = instruction_address >> self.value_size
            shifted_value = value >> self.value_size
            if shifted_address != shifted_value:
                raise ValueError(
                    f'Operand address value 0x{value:x} does not have the same MSBs '
                    f'as the instruction address 0x{instruction_address:x}'
                )
        else:
            final_value = value
        return final_value


class AddressOperand(NumericExpressionOperand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, require_arg: bool = True) -> None:
        super().__init__(operand_id, arg_config_dict, default_endian, require_arg)

    def __str__(self):
        return f'AddressOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.ADDRESS

    @property
    def match_pattern(self) -> str:
        return r'(?:[\$\%\w\(\)\+\-\s]*[\w\)])'

    @property
    def enforce_argument_valid_address(self) -> bool:
        return True

    def valid_memory_zone(self, memzone_manager: MemoryZoneManager) -> MemoryZone:
        """Returns the memory zone that the operand's argument must be a valid address in. Defaults
           to the global zone. Raises a `ValueError` if the configured zone is not found."""
        zone_name = self.config['argument'].get('memory_zone', GLOBAL_ZONE_NAME)
        zone = memzone_manager.zone(zone_name)
        if zone is None:
            raise ValueError(f'Invalid memory zone name "{zone_name}" for operand {self}')
        return zone

    @property
    def does_lsb_slice(self) -> bool:
        """Returns true if the argument value should be sliced into the least significant byte(s) of
           the bytecode. Defaults to false. If trues, the argument size should reflect the number of
           bits to slice."""
        return self.config['argument'].get('slice_lsb', False)

    @property
    def match_address_msb(self) -> bool:
        """Returns true if the argument value's MSBs should match the MSBs of the current instruction's
           address. Can only be true if `does_lsb_slice` is also true. Defaults to false."""
        if self.does_lsb_slice:
            return self.config['argument'].get('match_address_msb', False)
        return False

    def _parse_bytecode_parts(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        """Overrides `NumericExpressionOperand._parse_bytecode_parts` to add support for slicing ]
           the least significant bytes of the argument value."""
        bytecode_part = NumericByteCodePart(
            self.bytecode_value,
            self.bytecode_size,
            False,
            'big',
            line_id
        ) if self.bytecode_value is not None else None
        arg_part = AddressByteCodePart(
            operand,
            self.argument_size,
            self.argument_byte_align,
            self.argument_endian,
            line_id,
            self.valid_memory_zone(memzone_manager),
            self.does_lsb_slice,
            self.match_address_msb,
        )
        if arg_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, arg_part, operand)
