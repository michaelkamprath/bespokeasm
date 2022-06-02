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
        if len(instruction_str) > 0:
            # try label
            line_obj = LabelLine.factory(
                line_id,
                instruction_str,
                comment_str,
                model.registers,
                label_scope
            )
            if line_obj is not None:
                line_obj_list = [line_obj]
                # check to see for same line instruction
                same_line_instr = LabelLine.parse_same_line_instruction(line_id, instruction_str)
                if same_line_instr is not None:
                    # try directives
                    line_obj = DirectiveLine.factory(line_id, same_line_instr, '', model)
                    if line_obj is not None:
                        line_obj_list.append(line_obj)
                        return line_obj_list

                    # try instruction
                    line_obj = InstructionLine.factory(line_id, same_line_instr, '', model)
                    if line_obj is not None:
                        line_obj_list.append(line_obj)
                        return line_obj_list

                    # if we got here, it is because there is somethign following a label punctuation colon
                    # that shouldn't be there.
                    sys.exit(f'ERROR: {line_id} - Improperly formatted label')
                return line_obj_list
            # try directives
            line_obj = DirectiveLine.factory(line_id, instruction_str, comment_str, model)
            if line_obj is not None:
                return [line_obj]

            # try instruction
            line_obj = InstructionLine.factory(line_id, instruction_str, comment_str, model)
            if line_obj is not None:
                return [line_obj]

        # if we got here, the line is only a comment
        line_obj = LineObject(line_id, instruction_str, comment_str)
        return [line_obj]
