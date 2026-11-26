from bespokeasm.assembler.memory_zone import MemoryZone

GLOBAL_ZONE_NAME = 'GLOBAL'


class MemoryZoneManager:
    def __init__(
        self,
        address_bits: int,
        default_origin: int,
        predefined_zones: list[dict] = [],
        format_scoped_zones: dict[str, list[str]] | None = None,
    ) -> None:
        """``format_scoped_zones`` maps each zone that only output formats define to those
        formats, so a reference to one that is not selected gets a helpful error."""
        self._address_bits = address_bits
        self._default_origin = default_origin
        self._format_scoped_zones = dict(format_scoped_zones or {})

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

    def reset_current_addresses(self) -> None:
        """Move every zone's current address back to where pass 1 starts it, so pass 1 can run
        again after relaxation changes an instruction's size."""
        for zone in self._zones.values():
            zone.current_address = zone.start
        self._zones[GLOBAL_ZONE_NAME].current_address = self._default_origin

    def zone(self, name: str) -> MemoryZone:
        return self._zones.get(name, None)

    def unknown_zone_message(self, name: str) -> str:
        message = f'unknown memory zone "{name}"'
        formats = self._format_scoped_zones.get(name)
        if formats:
            from bespokeasm.assembler.output_format.defined import format_scoped_hint
            message += f'; {format_scoped_hint(formats)}'
        return message

    def create_zone(self, address_bits: int, start: int, end: int, name: str) -> MemoryZone:
        if name in self._zones:
            raise KeyError(f'MemoryZone name {name} already exists.')
        if start < self.global_zone.start:
            raise ValueError(
                f'The start address {start} for memory zone "{name}" is outside the bounds of the GLOBAL zone'
            )
        if end > self.global_zone.end:
            raise ValueError(
                f'The end address {end} for memory zone "{name}" is outside the bounds of the GLOBAL zone'
            )
        new_zone = MemoryZone(address_bits, start, end, name)
        self._zones[name] = new_zone
        return new_zone
