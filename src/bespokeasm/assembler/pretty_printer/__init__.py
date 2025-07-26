from bespokeasm.assembler.line_object import LineObject, LineWithWords
from bespokeasm.assembler.model import AssemblerModel


class PrettyPrinterBase:
    def __init__(
                self,
                line_objs: list[LineObject],
                model: AssemblerModel,
                instruction_indent: int = 0,
            ) -> None:
        self._line_objs = line_objs
        self._model = model
        # scan though the line objects to get max widths
        line_num_max = 0
        instruction_max_width = 0
        self._max_byte_count = 0
        self._max_comment_width = 0
        for lo in line_objs:
            if lo.line_id.line_num > line_num_max:
                line_num_max = lo.line_id.line_num
            if len(lo.instruction) + instruction_indent > instruction_max_width:
                instruction_max_width = len(lo.instruction) + instruction_indent
            if len(lo.comment) > self._max_comment_width:
                self._max_comment_width = len(lo.comment)
            if isinstance(lo, LineWithWords):
                if len(lo.get_words()) > self._max_byte_count:
                    self._max_byte_count = len(lo.get_words())
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
        return max(self._max_line_num_width, 4)

    @property
    def max_instruction_width(self) -> int:
        return self._max_instruction_width

    @property
    def max_byte_count(self) -> int:
        return self._max_byte_count

    @property
    def max_comment_width(self) -> int:
        return self._max_comment_width

    def pretty_print(self) -> str:
        raise NotImplementedError
