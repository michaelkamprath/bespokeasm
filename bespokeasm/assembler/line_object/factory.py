import re
import sys

from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.directive_line import DirectiveLine
from bespokeasm.assembler.line_object.instruction_line import InstructionLine

class LineOjectFactory:
    PATTERN_COMMENTS = re.compile(
        r'((?<=\;).*)$',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_INSTRUCTION_CONTENT = re.compile(
        r'^([^\;\n]*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    @classmethod
    def parse_line(
                cls,
                line_id: LineIdentifier,
                line_str: str,
                model: AssemblerModel,
                label_scope: LabelScope,
            ) -> list[LineObject]:
        # find comments
        comment_str = ''
        comment_match = re.search(LineOjectFactory.PATTERN_COMMENTS, line_str)
        if comment_match is not None:
            comment_str = comment_match.group(1).strip()

        # find instruction
        instruction_str = ''
        instruction_match = re.search(LineOjectFactory.PATTERN_INSTRUCTION_CONTENT, line_str)
        if instruction_match is not None:
            instruction_str = instruction_match.group(1).strip()

        # parse instruction
        line_obj_list: list[LineObject] = []
        while len(instruction_str) > 0:
            #print(f'Parsing instruction string = "{instruction_str}"')
            # try label
            line_obj = LabelLine.factory(
                line_id,
                instruction_str,
                comment_str,
                model.registers,
                label_scope
            )
            if line_obj is not None:
                line_obj_list.append(line_obj)
                instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                continue

            # try directives
            line_obj = DirectiveLine.factory(line_id, instruction_str, comment_str, model.endian)
            if line_obj is not None:
                line_obj_list.append(line_obj)
                instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                continue

            # try instruction
            line_obj = InstructionLine.factory(line_id, instruction_str, comment_str, model)
            if line_obj is not None:
                line_obj_list.append(line_obj)
                #print(f'    found instruction with text = "{line_obj.instruction}"')
                instruction_str = instruction_str.replace(line_obj.instruction, '', 1).strip()
                continue

            # if we are here, that means nothing was matched. Shouldn't happen, but we will break none the less
            break

        if len(line_obj_list) == 0:
            if instruction_str != '':
                sys.exit(f'ERROR: {line_id} - unknown instruction "{instruction_str.strip()}"')
            # if we got here, the line is only a comment
            line_obj = LineObject(line_id, instruction_str, comment_str)
            return [line_obj]
        return line_obj_list
