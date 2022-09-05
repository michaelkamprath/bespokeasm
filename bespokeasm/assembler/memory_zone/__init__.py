from __future__ import annotations

MEMORY_ZONE_NAME_PATTERN = r'[\w_]+'


class MemoryZone:
    def __init__(self, address_bits: int, start: int, end: int, name: str) -> None:
        self._address_bits = address_bits
        self._start = start
        self._end = end
        self._name = name
        self._current_address = start
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
        if value > self.end:
            raise ValueError(
                f'Setting current address of memory zone "{self.name}" to {value} exceed maximum zone address {self.end}.'
            )
        self._current_address = value
