
from bespokeasm.assembler.memory_zone import MemoryZone

GLOBAL_ZONE_NAME = 'GLOBAL'

class MemoryZoneManager:
    def __init__(self, address_bits: int, default_origin: int, predefined_zones: list[dict] = []) -> None:
        self._address_bits = address_bits

        self._zones: dict[str, MemoryZone] = {
            mz['name']: MemoryZone(address_bits, mz['start'], mz['end'], mz['name'])
            for mz in predefined_zones
        }
        if GLOBAL_ZONE_NAME not in self._zones:
            self._zones[GLOBAL_ZONE_NAME] = MemoryZone(
                address_bits, 0, (2**address_bits)-1, GLOBAL_ZONE_NAME,
            )
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