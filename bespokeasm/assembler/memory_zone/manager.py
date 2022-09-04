
from bespokeasm.assembler.memory_zone import MemoryZone

GLOBAL_ZONE_NAME = 'GLOBAL'

class MemoryZoneManager:
    def __init__(self, address_bits: int, default_origin: int) -> None:
        self._address_bits = address_bits
        self._zones: dict[str, MemoryZone] = {
            GLOBAL_ZONE_NAME: MemoryZone(address_bits, 0, (2**address_bits)-1, 'GLOBAL')
        }
        self._zones[GLOBAL_ZONE_NAME].current_address = default_origin

    @property
    def global_zone(self) -> MemoryZone:
        return self._zones[GLOBAL_ZONE_NAME]

    def zone(self, name: str) -> MemoryZone:
        return self._zones.get(name, None)

    def create_zone(self, address_bits: int, start: int, end: int, name: str) -> MemoryZone:
        if name in self._zones:
            raise KeyError(f'MemoryZone name {name} alredy exists.')
        new_zone = MemoryZone(address_bits, start, end, name)
        self._zones[name] = new_zone
        return new_zone