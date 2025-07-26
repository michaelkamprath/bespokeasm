# The page align directive allows the user to align the current memory address to the next page boundary.
# This is useful when it is important that the byte code to be generated is placed at the start of a page boundary,
# but it is not important that the code is at a sopecific address. If the byte code needs to be at a specific address,
# one would use the .org directive.
#
# The page align directive is used as follows:
#
#   .page [page_size]
#
# Where the optional page_size is the size of the page in bytes. If page_size is not specified, the default page size
# configured in configuration file is used. The specific configuration is general->page_size. If the page_size is
# note spcified, a default value of 1 is used efficiently making the page align directive a no-op.
#
# Error cases:
# - If the page directive would generate an address that is beyond the currently active memory zone, an error is
#   generated.
import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import INSTRUCTION_EXPRESSION_PATTERN
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import parse_expression


class PageAlignLine(LineObject):
    PATTERN_PAGE_ALIGN = re.compile(
            f'^\\.align(?:\\s+({INSTRUCTION_EXPRESSION_PATTERN}))?',
        )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        default_page_size: int,
    ):
        super().__init__(line_id, instruction, comment, memzone)
        define_symbol_match = re.search(PageAlignLine.PATTERN_PAGE_ALIGN, instruction)
        if define_symbol_match is not None:
            if define_symbol_match.group(1) is not None:
                self._page_size = parse_expression(line_id, define_symbol_match.group(1))
            else:
                self._page_size = default_page_size
        else:
            raise ValueError(f'Invalid page align directive "{instruction}"')

    def __repr__(self) -> str:
        return f'PageAlignLine<page_size={self._page_size}>'

    def set_start_address(self, address: int):
        """Sets the finalized address to the next page boundary.
        """
        if isinstance(self._page_size, ExpressionNode):
            self._page_size = self._page_size.get_value(self.label_scope, self.line_id)

        if self._page_size == 1:
            self._address = address
        else:
            self._address = address + (self._page_size - (address % self._page_size))
