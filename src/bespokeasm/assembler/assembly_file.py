# Assembly File
#
# this class models an assembly file. AN AssemblyFile object is created for each
# assembly file that is loaded. It is responsible for:
#
#    * providing a list of lines
#    * having a single file label scope
from __future__ import annotations
import click
import os
import re
import sys

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.directive_line import SetMemoryZoneLine
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack
from bespokeasm.assembler.line_object.preprocessor_line.condition_line import ConditionLine


class AssemblyFile:
    def __init__(self, filename: str, parent_label_scope: LabelScope) -> None:
        self._filename = filename
        self._label_scope = LabelScope(
                LabelScopeType.FILE,
                parent_label_scope,
                self._filename
            )

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def label_scope(self) -> LabelScope:
        return self._label_scope

    def load_line_objects(
                self,
                isa_model: AssemblerModel,
                include_paths: set[str],
                memzone_manager: MemoryZoneManager,
                preprocessor: Preprocessor,
                log_verbosity: int,
                assembly_files_used: set = set()
            ) -> list[LineObject]:
        line_objects = []

        try:
            with open(self.filename, 'r') as f:
                assembly_files_used.add(self.filename)
                line_num = 0
                current_scope = self.label_scope
                current_memzone = memzone_manager.global_zone
                condition_stack = ConditionStack()
                for line in f:
                    line_num += 1
                    line_id = LineIdentifier(line_num, filename=self.filename)
                    line_str = line.strip()
                    if len(line_str) > 0:
                        # check to see if this is a #include line.
                        # this is the one preprocessor directive that is handled
                        # by the assembly file object.
                        if line_str.startswith('#include'):
                            additional_line_objects = self._handle_include_file(
                                line_str,
                                line_id,
                                isa_model,
                                memzone_manager,
                                preprocessor,
                                include_paths,
                                log_verbosity,
                                assembly_files_used
                            )
                            line_objects.extend(additional_line_objects)
                            continue

                        lobj_list: list[LineObject] = []
                        # parse the line
                        lobj_list.extend(LineOjectFactory.parse_line(
                            line_id,
                            line_str,
                            isa_model,
                            current_scope,
                            current_memzone,
                            memzone_manager,
                            preprocessor,
                            condition_stack,
                            log_verbosity,
                        ))
                        for lobj in lobj_list:
                            if not isinstance(lobj, ConditionLine):
                                lobj.compilable = condition_stack.currently_active(preprocessor)

                            if lobj.compilable:
                                if isinstance(lobj, LabelLine):
                                    if not lobj.is_constant \
                                            and LabelScopeType.get_label_scope(lobj.get_label()) != LabelScopeType.LOCAL:
                                        current_scope = LabelScope(LabelScopeType.LOCAL, self.label_scope, lobj.get_label())
                                # both .org and .memzone directive should reset label scope to FILE and current memzone
                                elif isinstance(lobj, SetMemoryZoneLine):
                                    current_scope = self.label_scope
                                    current_memzone = lobj.memory_zone
                                lobj.label_scope = current_scope
                                # setting constants now so they can be used when evaluating lines later.
                                if isinstance(lobj, LabelLine) and lobj.is_constant:
                                    lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
                            line_objects.append(lobj)
        except FileNotFoundError:
            sys.exit(f'ERROR: Compilation file "{self.filename}" not found.')

        if log_verbosity > 1:
            click.echo(f'Found {len(line_objects)} lines in source file {self.filename}')

        return line_objects

    PATTERN_INCLUDE_FILE = re.compile(
        r'^\#include\s+(?:\'|\")([\w\.\-\_]+)(?:\'|\")',
        flags=re.IGNORECASE | re.MULTILINE
    )

    def _handle_include_file(
                self,
                line_str: int,
                line_id: LineIdentifier,
                isa_model: AssemblerModel,
                memzone_manager: MemoryZoneManager,
                preprocessor: Preprocessor,
                include_paths: set[str],
                log_verbosity: int,
                assembly_files_used: set
            ) -> list[LineObject]:
        label_match = re.search(AssemblyFile.PATTERN_INCLUDE_FILE, line_str)
        if label_match is not None:
            new_filepath = self._locate_filename(
                    label_match.group(1).strip(),
                    include_paths,
                    line_id
                )
            if new_filepath in assembly_files_used:
                sys.exit(f'ERROR: {line_id} - assembly file included multiple times')
            file_obj = AssemblyFile(new_filepath, self.label_scope.parent)
            return file_obj.load_line_objects(
                isa_model,
                include_paths,
                memzone_manager,
                preprocessor,
                log_verbosity,
                assembly_files_used=assembly_files_used
            )
        else:
            sys.exit(f'ERROR: {line_id} - Improperly formatted include directive')

    def _locate_filename(self, filename: str, include_paths: set[str], line_id: LineIdentifier) -> str:
        '''locates the filename in the include paths, and returns the full file path. Errors if file name is ambiguous.'''
        filepath = None
        for include_dir in include_paths:
            found_path = os.path.join(include_dir, filename)
            if os.path.exists(found_path):
                if filepath is None:
                    filepath = found_path
                else:
                    sys.exit(f'ERROR: {line_id} - include file "{filename}" can be found multiple times in include paths')
        if filepath is None:
            sys.exit(f'ERROR: {line_id} - could not find file "{filename}" to include')
        return filepath
