import io
import math

from bespokeasm.assembler.line_object import LineWithBytes, LineObject
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase


class SourceDetailsPrettyPrinter(PrettyPrinterBase):
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel) -> None:
        super().__init__(line_objs, model)

    def pretty_print(self) -> str:
        output = io.StringIO()

        address_size = math.ceil(self.model.address_size/4)
        address_format_str = f'0x{{0:0{address_size}x}}'
        COL_WIDTH_LINE = 7
        COL_WIDTH_ADDRESS = max(address_size + 3, 7)
        COL_WIDTH_BYTE = 4
        COL_WIDTH_BINARY = 8
        INSTRUCTION_INDENT = 4
        blank_line_num = ''.join([' '*COL_WIDTH_LINE])
        blank_instruction_text = ''.join([' '*(self.max_instruction_width + INSTRUCTION_INDENT)])
        blank_address_text = ''.join([' '*COL_WIDTH_ADDRESS])
        blank_byte_text = ''.join([' '*COL_WIDTH_BYTE])
        blank_binary_text = ''.join([' '*COL_WIDTH_BINARY])

        header_text = ' {} | {} | {} | {} | {} | Comment '.format(
            'Line'.center(COL_WIDTH_LINE),
            'Code'.ljust(self.max_instruction_width + INSTRUCTION_INDENT),
            'Address'.center(COL_WIDTH_ADDRESS),
            'Byte'.center(COL_WIDTH_BYTE),
            'Binary'.center(COL_WIDTH_BINARY),
        )
        header_line_text = '-{}-+-{}-+-{}-+-{}-+-{}-+---------------'.format(
            ''.join('-'*(COL_WIDTH_LINE)),
            ''.join('-'*(self.max_instruction_width)),
            ''.join('-'*(COL_WIDTH_ADDRESS)),
            ''.join('-'*(COL_WIDTH_BYTE)),
            ''.join('-'*(COL_WIDTH_BINARY)),
        )
        output.write(f'\n{header_text}\n{header_line_text}\n')
        for lobj in self.line_objects:
            line_str = f'{lobj.line_id.line_num}'.rjust(7)
            address_value = lobj.address
            address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
            instruction_str = lobj.instruction
            if not isinstance(lobj, LabelLine):
                instruction_str = ' '*INSTRUCTION_INDENT + instruction_str
            instruction_str = instruction_str.ljust(self.max_instruction_width + INSTRUCTION_INDENT)

            if isinstance(lobj, LineWithBytes):
                line_bytes = lobj.get_bytes()
            else:
                line_bytes = None
            if line_bytes is not None:
                bytes_list = list(line_bytes)
                # print first line
                output.write(
                    f' {line_str} | {instruction_str} | {address_str} | 0x{bytes_list[0]:02x} | '
                    f'{bytes_list[0]:08b} | {lobj.comment}\n'
                )
                for b in bytes_list[1:]:
                    address_value += 1
                    address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
                    output.write(
                        f' {blank_line_num} | {blank_instruction_text} | {address_str} | 0x{b:02x} | {b:08b} |\n'
                    )
            else:
                output.write(
                    f' {line_str} | {instruction_str} | {blank_address_text} | {blank_byte_text} | '
                    f'{blank_binary_text} | {lobj.comment}\n'
                )
        return output.getvalue()
