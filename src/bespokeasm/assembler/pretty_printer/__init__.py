from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.model import AssemblerModel


class PrettyPrinterBase:
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel) -> None:
        self._line_objs = line_objs
        self._model = model

    @property
    def line_objects(self) -> list[LineObject]:
        return self._line_objs

    @property
    def model(self) -> AssemblerModel:
        return self._model

    def pretty_print(self, max_instruction_text_size: int) -> str:
        raise NotImplementedError
