from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes

class PredefinedDataLine(LineWithBytes):
    def __init__(self, line_id: LineIdentifier, byte_length: int, byte_value: int, name: str) -> None:
        super().__init__(line_id, f'.predefined_data [{byte_value}]*{byte_length}', name)
        self._byte_length = byte_length
        self._byte_value = byte_value

    def __str__(self):
        return f'PredefinedDataLine<{self.comment}>'

    @property
    def byte_size(self) -> int:
        """Returns the number of bytes this data line will generate"""
        return self._byte_length

    def generate_bytes(self):
        self._bytes.extend([(self._byte_value)&0xFF]*self._byte_length)