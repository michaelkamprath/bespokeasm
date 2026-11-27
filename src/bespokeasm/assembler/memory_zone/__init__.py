from __future__ import annotations

MEMORY_ZONE_NAME_PATTERN = r'[\w_]+'


class MemoryZone:
    def __init__(self, address_bits: int, start: int, end: int, name: str) -> None:
        self._address_bits = address_bits
        self._start = start
        self._end = end
        self._name = name
        self._current_address = start
        # How far the image position is ahead of the current address inside a `.phase`; 0 outside one.
        self.phase_offset = 0
        # validate passed values
        if end > ((2**address_bits)-1):
            raise ValueError(
                f'End value {end} for memory zone "{self.name}" larger than allowed by {address_bits}-bit address space.'
            )
        if start > end:
            raise ValueError(f'Start value {start} for memory zone "{self.name}" larger than end value {end}.')

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'MemoryZone<{self.name}: {self.start}->{self.end}>'

    @property
    def start(self) -> int:
        return self._start

    @property
    def end(self) -> int:
        return self._end

    @property
    def name(self) -> str:
        return self._name

    @property
    def current_address(self) -> int:
        return self._current_address

    @current_address.setter
    def current_address(self, value: int):
        if value < self.start:
            raise ValueError(
                f'address {value} ({hex(value)}) is before the start of memory zone "{self.name}" '
                f'(zone starts at {self.start}, {hex(self.start)})'
            )
        # check against 1 byte past zone end. This allows for the address updates to be
        # right up to the end.
        if value > self.end + 1:
            raise ValueError(
                f'bytecode at this line extends to address {value} ({hex(value)}), past the end of '
                f'memory zone "{self.name}" (zone ends at {self.end}, {hex(self.end)})'
            )
        self._current_address = value
