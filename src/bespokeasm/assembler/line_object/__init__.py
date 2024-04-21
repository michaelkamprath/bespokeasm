from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.expression import EXPRESSION_PARTS_PATTERN

PATTERN_LABEL_DEFINITION = r'\s*(?:\.?\w+:)'
INSTRUCTION_EXPRESSION_PATTERN = r'(?:{}|(?:[ \t]*)(?!(?:[ \t]*\;|[ \t]*\v)|{}))+'.format(
    EXPRESSION_PARTS_PATTERN,
    PATTERN_LABEL_DEFINITION,
)


class LineObject:
    def __init__(self, line_id: LineIdentifier, instruction: str, comment: str, memzone: MemoryZone):
        self._line_id = line_id
        self._instruction = instruction.strip()
        self._comment = comment.strip()
        self._address = None
        self._label_scope = None
        self._memzone = memzone
        self._compilable = True
        self._is_muted = False

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'LineObject<{self.instruction}>'

    @property
    def line_id(self) -> LineIdentifier:
        """Returns the line identifier that his object was parsed from"""
        return self._line_id

    def set_start_address(self, address: int):
        """Sets the initial address for this line object.

        If this object consists of multiple bytes, address pertains to first byte.

        The finalized address reported in the `address` property might be different from this value.
        """
        self._address = address

    @property
    def address(self) -> int:
        """Returns the finalized address for this line object.

        If this object consists of multiple bytes, address pertains to first byte.
        """
        return self._address

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this line will generate"""
        return 0

    @property
    def instruction(self) -> str:
        """returns the original instruction text that generated this line object"""
        return self._instruction

    @property
    def comment(self) -> str:
        """returns the code comment associated with this line object"""
        return self._comment

    @property
    def label_scope(self) -> LabelScope:
        return self._label_scope

    @label_scope.setter
    def label_scope(self, value):
        self._label_scope = value

    @property
    def memory_zone(self) -> MemoryZone:
        return self._memzone

    @property
    def compilable(self) -> bool:
        """Returns True if this line object can be compiled to bytecode"""
        return self._compilable

    @compilable.setter
    def compilable(self, value: bool):
        self._compilable = value

    @property
    def is_muted(self) -> bool:
        """
        Returns True if this line object should be ignored during
        emission of bytecode or certain types of pretty printing
        """
        return self._is_muted

    @is_muted.setter
    def is_muted(self, value: bool):
        """Sets the muted state of this line object"""
        self._is_muted = value


class LineWithBytes(LineObject):
    def __init__(self, line_id: LineIdentifier, instruction: str, comment: str, memzone: MemoryZone):
        super().__init__(line_id, instruction, comment, memzone)
        self._bytes = bytearray()

    def generate_bytes(self) -> None:
        """Finalize the bytes for this line with the label assignemnts

        Must be overriden by subclass to extend the self._bytes instance variable or
        use the self._append_byte() method.
        """
        raise NotImplementedError

    def get_bytes(self) -> bytearray:
        """Returns current state of constructed bytes"""
        return self._bytes

    def _append_byte(self, byte_value: int):
        """appends the passed byte value to this objects bytes"""
        self._bytes.append(byte_value & 0xFF)
