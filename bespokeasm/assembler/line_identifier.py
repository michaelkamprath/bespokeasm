

class LineIdentifier:
    def __init__(self, line_num: int, filename: str  = None ) -> None:
        self._filename = filename
        self._line_num = line_num

    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        return f'file {self._filename if self._filename is not None else "unnown_file"}, line {self._line_num}'

    @property
    def filename(self) -> str:
        return self._filename
    @property
    def line_num(self) -> int:
        return self._line_num