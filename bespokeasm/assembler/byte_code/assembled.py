import math
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart
from bespokeasm.assembler.byte_code.packed_bits import PackedBits
from bespokeasm.assembler.label_scope import LabelScope


class AssembledInstruction:
    def __init__(self, line_id: LineIdentifier, parts: list[ByteCodePart]):
        self._parts = parts
        self._line_id = line_id
        # calculate total bytes
        total_bits = 0
        for bcp in self._parts:
            if bcp.byte_align:
                if total_bits % 8 != 0:
                    total_bits += 8 - total_bits % 8
            total_bits += bcp.value_size
        self._byte_size = math.ceil(total_bits/8)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'AssembledInstruction{self._parts}'

    @property
    def byte_size(self):
        return self._byte_size

    @property
    def line_id(self):
        return self._line_id

    @property
    def parts(self):
        return self._parts

    def get_bytes(self, label_scope: LabelScope, instruction_address: int, instruction_size: int) -> bytearray:
        packed_bits = PackedBits()
        for p in self._parts:
            value = p.get_value(label_scope, instruction_address, instruction_size)
            if isinstance(value, str):
                sys.exit(f'ERROR - assembled instruction "{self}" had a part {p} that did not resolve to an int, got: {value}')
            elif value is None:
                sys.exit(f'ERROR - assembled instruction "{self}" had a part {p} that produced None for a value')

            packed_bits.append_bits(
                value,
                p.value_size,
                p.byte_align,
                p.endian,
            )
        bytes = packed_bits.get_bytes()
        if len(bytes) != self.byte_size:
            # ERROR
            return None
        return bytes

class CompositeAssembledInstruction(AssembledInstruction):
    def __init__(self, line_id: LineIdentifier, instructions: list[AssembledInstruction]):
        # turn instruction list into byte code parts list
        parts: list[ByteCodePart] = [
            p  for instr in instructions for p in instr.parts
        ]
        super().__init__(line_id, parts)
        self._instructions = instructions

    @property
    def instructions(self):
        return self._instructions
