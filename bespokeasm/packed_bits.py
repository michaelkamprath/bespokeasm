class PackedBits:
    def __init__(self):
        self._bytes = bytearray(1)
        self._cur_byte_idx = 0
        self._cur_bit_idx = 7
        self._bytes[0] = 0

    def append_bits(self, value, bit_size, byte_aligned):
        # there is probably a more efficient way to do this, but for now this works
        if byte_aligned and self._cur_bit_idx < 7:
                self._cur_bit_idx = 7
                self._bytes.append(0)
                self._cur_byte_idx += 1
        for bit_idx in range(bit_size-1,-1,-1):
            if self._cur_bit_idx < 0:
                self._cur_bit_idx = 7
                self._bytes.append(0)
                self._cur_byte_idx += 1
            mask = (1 << bit_idx)
            bit_value = ((value&mask) >> bit_idx)
            self._bytes[self._cur_byte_idx] |= (bit_value << self._cur_bit_idx)
            self._cur_bit_idx -= 1

    def get_bytes(self):
        return self._bytes