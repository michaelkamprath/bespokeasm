import re
import sys

from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone import MEMORY_ZONE_NAME_PATTERN
from bespokeasm.utilities import PATTERN_NUMERIC, parse_numeric_string


class CreateMemzoneLine(PreprocessorLine):
    PATTERN_CREATE_MEMORY_ZONE = re.compile(
        r'#create_memzone\s+({})\s+({})\s+({})'.format(
            MEMORY_ZONE_NAME_PATTERN,
            PATTERN_NUMERIC,
            PATTERN_NUMERIC,
        ),
    )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        memzone_manager: MemoryZoneManager,
        isa_model: AssemblerModel,
        log_verbosity: int
    ) -> None:
        '''Creates a new memory zone based on the #create_memzone line'''
        super().__init__(line_id, instruction, comment, memzone)
        memzone_match = re.search(CreateMemzoneLine.PATTERN_CREATE_MEMORY_ZONE, instruction)
        if memzone_match is not None and len(memzone_match.groups()) == 3:
            self._name = memzone_match.group(1).strip()
            self._start_addr = parse_numeric_string(memzone_match.group(2))
            self._end_addr = parse_numeric_string(memzone_match.group(3))
            if log_verbosity > 2:
                print(
                    f'Creating memory zone "{self._name}" with start address {self._start_addr} '
                    f'and end address {self._end_addr}'
                )
            try:
                memzone_manager.create_zone(
                    isa_model.address_size,
                    self._start_addr,
                    self._end_addr,
                    self._name,
                )
            except KeyError:
                sys.exit(f'ERROR: {line_id} - Memory zone "{self._name}" defined multiple times')
            except ValueError as v_err:
                sys.exit(f'ERROR: {line_id} - {v_err}')
        else:
            sys.exit(f'ERROR: {line_id} - Syntax error when creating memory zone')

    def __repr__(self) -> str:
        return f'CreateMemzoneLine<{self._name}: {self._start_addr} -> {self._end_addr}>'
