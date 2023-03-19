from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.model import AssemblerModel


class PrettyPrinterBase:
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel) -> None:
        self._line_objs = line_objs
        self._model = model
        # scan though the line objects to get max widths
        line_num_max = 0
        instruction_max_width = 0
        for lo in line_objs:
            if lo.line_id.line_num > line_num_max:
                line_num_max = lo.line_id.line_num
            if len(lo.instruction) > instruction_max_width:
                instruction_max_width = len(lo.instruction)
        self._max_line_num_width = len(str(line_num_max))
        self._max_instruction_width = instruction_max_width

    @property
    def line_objects(self) -> list[LineObject]:
        return self._line_objs

    @property
    def model(self) -> AssemblerModel:
        return self._model

    @property
    def max_line_num_width(self) -> int:
        return self._max_line_num_width

    @property
    def max_instruction_width(self) -> int:
        return self._max_instruction_width

    def pretty_print(self) -> str:
        raise NotImplementedError
