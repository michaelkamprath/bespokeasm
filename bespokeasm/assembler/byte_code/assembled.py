import math

from bespokeasm.assembler.byte_code.parts import ByteCodePart
from bespokeasm.assembler.byte_code.packed_bits import PackedBits

class AssembledInstruction:
    def __init__(self, line_number: int, parts: list[ByteCodePart]):
        self._parts = parts
        self._line_number = line_number
        # calculate total bytes
        total_bits = 0
        for bcp in self._parts:
            if bcp.byte_align:
                if total_bits%8 != 0:
                    total_bits += 8 - total_bits%8
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
    def line_number(self):
        return self._line_number

    def get_bytes(self, label_dict: dict[str, int]) -> bytearray:
        packed_bits = PackedBits()
        for p in self._parts:
            packed_bits.append_bits(
                p.get_value(self.line_number, label_dict),
                p.value_size,
                p.byte_align,
                p.endian,
            )
        bytes = packed_bits.get_bytes()
        if len(bytes) != self.byte_size:
            # ERROR
            return None
        return bytes
