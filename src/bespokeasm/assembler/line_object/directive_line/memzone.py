import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.memory_zone.manager import GLOBAL_ZONE_NAME
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


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
