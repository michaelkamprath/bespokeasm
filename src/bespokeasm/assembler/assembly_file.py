# Assembly File
#
# this class models an assembly file. AN AssemblyFile object is created for each
# assembly file that is loaded. It is responsible for:
#
#    * providing a list of lines
#    * having a single file label scope
from __future__ import annotations

import os
import re
import sys

import click
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine
from bespokeasm.assembler.line_object.directive_line.factory import SetMemoryZoneLine
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line.condition_line import CONDITIONAL_LINE_PREFIX_LIST
from bespokeasm.assembler.line_object.preprocessor_line.condition_line import ConditionLine
from bespokeasm.assembler.line_object.preprocessor_line.create_scope import CreateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.deactivate_scope import DeactivateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.use_scope import UseScopeLine
from bespokeasm.assembler.memory_zone.manager import GLOBAL_ZONE_NAME
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack
from bespokeasm.assembler.warning_reporter import WarningReporter


class AssemblyFile:
    def __init__(
                self,
                filename: str,
                parent_label_scope: LabelScope,
                named_scope_manager: NamedScopeManager,
                warning_reporter: WarningReporter | None = None,
            ) -> None:
        self._filename = filename
        self._named_scope_manager = named_scope_manager
        self._warning_reporter = warning_reporter or named_scope_manager.warning_reporter
        self._used_named_scopes: list[tuple[str, LineIdentifier]] = []
        self._defined_named_scopes: set[str] = set()
        self._label_scope = LabelScope(
                LabelScopeType.FILE,
                parent_label_scope,
                self._filename,
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
            with open(self.filename) as f:
                assembly_files_used.add(self.filename)
                line_num = 0
                current_scope = self.label_scope
                current_memzone = memzone_manager.global_zone
                condition_stack = ConditionStack(self._warning_reporter)
                active_named_scopes = ActiveNamedScopeList(self._named_scope_manager)
                for line in f:
                    line_num += 1
                    line_id = LineIdentifier(line_num, filename=self.filename)
                    line_str = line.strip()
                    if len(line_str) > 0:
                        # check to see if this is a #include line.
                        # this is the one preprocessor directive that is handled
                        # by the assembly file object.
                        if line_str.startswith('#include'):
                            # Only process the #include if the current conditional block is active
                            if condition_stack.currently_active(preprocessor):
                                if condition_stack.is_muted:
                                    self._warning_reporter.warn(
                                        line_id,
                                        '#include does not inherit #mute; included file will emit bytecode',
                                    )
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
                        is_conditional_directive = line_str.startswith(tuple(CONDITIONAL_LINE_PREFIX_LIST))
                        if not condition_stack.currently_active(preprocessor) and not is_conditional_directive:
                            comment_str = ''
                            comment_match = re.search(LineOjectFactory.PATTERN_COMMENTS, line_str)
                            if comment_match is not None:
                                comment_str = comment_match.group(1).strip()
                            instruction_str = ''
                            instruction_match = re.search(LineOjectFactory.PATTERN_INSTRUCTION_CONTENT, line_str)
                            if instruction_match is not None:
                                instruction_str = instruction_match.group(1).strip()
                            line_obj = LineObject(line_id, instruction_str, comment_str, current_memzone)
                            line_obj.compilable = False
                            line_obj.is_muted = condition_stack.is_muted
                            line_objects.append(line_obj)
                            continue
                        # parse the line
                        lobj_list.extend(LineOjectFactory.parse_line(
                            line_id,
                            line_str,
                            isa_model,
                            current_scope,
                            active_named_scopes,
                            current_memzone,
                            memzone_manager,
                            preprocessor,
                            condition_stack,
                            log_verbosity,
                            self._filename,
                        ))
                        for lobj in lobj_list:
                            if not isinstance(lobj, ConditionLine):
                                lobj.compilable = condition_stack.currently_active(preprocessor)
                                lobj.is_muted = condition_stack.is_muted

                            if lobj.compilable:
                                if isinstance(lobj, CreateScopeLine):
                                    self._defined_named_scopes.add(lobj.scope_name)
                                elif isinstance(lobj, UseScopeLine):
                                    if active_named_scopes and active_named_scopes[0] == lobj.scope_name:
                                        self._warning_reporter.warn(
                                            lobj.line_id,
                                            f'Named scope "{lobj.scope_name}" is already active; '
                                            '#use-scope has no effect'
                                        )
                                    self._used_named_scopes.append((lobj.scope_name, lobj.line_id))
                                elif isinstance(lobj, DeactivateScopeLine):
                                    if lobj.scope_name not in active_named_scopes:
                                        self._warning_reporter.warn(
                                            lobj.line_id,
                                            f'Named scope "{lobj.scope_name}" is not active; '
                                            '#deactivate-scope has no effect'
                                        )
                                if isinstance(lobj, LabelLine):
                                    if not lobj.is_constant \
                                            and LabelScopeType.get_label_scope(lobj.get_label()) != LabelScopeType.LOCAL:
                                        current_scope = LabelScope(LabelScopeType.LOCAL, self.label_scope, lobj.get_label())
                                # both .org and .memzone directive should reset label scope to FILE and current memzone
                                elif isinstance(lobj, SetMemoryZoneLine):
                                    if (
                                        isinstance(lobj, AddressOrgLine)
                                        and not lobj.has_explicit_memzone_name
                                        and current_memzone.name != GLOBAL_ZONE_NAME
                                    ):
                                        self._warning_reporter.warn(
                                            lobj.line_id,
                                            f'.org without a memzone name uses an absolute address; '
                                            f'current memzone is "{current_memzone.name}"',
                                        )
                                    current_scope = self.label_scope
                                    current_memzone = lobj.memory_zone
                                elif isinstance(lobj, UseScopeLine) or isinstance(lobj, CreateScopeLine):
                                    active_named_scopes.activate_named_scope(lobj.scope_name)
                                elif isinstance(lobj, DeactivateScopeLine):
                                    active_named_scopes.deactivate_named_scope(lobj.scope_name)
                                lobj.label_scope = current_scope
                                lobj.active_named_scopes = active_named_scopes
                                lobj.warning_reporter = self._warning_reporter
                                # setting constants now so they can be used when evaluating lines later.
                                if isinstance(lobj, LabelLine) and lobj.is_constant:
                                    # first check if label belongs to an active named scope
                                    if not self._named_scope_manager.set_label_value(
                                        lobj.get_label(),
                                        lobj.get_value(),
                                        lobj.line_id,
                                        lobj.active_named_scopes,
                                        is_constant=True
                                    ):
                                        # if not in an active named scope, set to the current scope
                                        lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
                            line_objects.append(lobj)
        except FileNotFoundError:
            sys.exit(f'ERROR: Compilation file "{self.filename}" not found.')

        if log_verbosity > 1:
            click.echo(f'Found {len(line_objects)} lines in source file {self.filename}')

        if condition_stack.is_muted:
            line_id = LineIdentifier(line_num if line_num > 0 else 1, filename=self.filename)
            self._warning_reporter.warn(
                line_id,
                'File ended while muted; bytecode emission remains suppressed',
            )
        self._emit_missing_scope_warnings()
        return line_objects

    PATTERN_INCLUDE_FILE = re.compile(
        r'^\#include\s+(?:\'|\")([\w\.\-_/]+)(?:\'|\")',
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
            include_paths_with_current = [os.path.dirname(self.filename), *include_paths]
            new_filepath = self._locate_filename(
                    label_match.group(1).strip(),
                    include_paths_with_current,
                    line_id
                )
            if new_filepath in assembly_files_used:
                sys.exit(f'ERROR: {line_id} - assembly file included multiple times')
            file_obj = AssemblyFile(
                new_filepath,
                self.label_scope.parent,
                self._named_scope_manager,
                self._warning_reporter,
            )
            include_line_objects = file_obj.load_line_objects(
                isa_model,
                include_paths,
                memzone_manager,
                preprocessor,
                log_verbosity,
                assembly_files_used=assembly_files_used
            )
            self._defined_named_scopes.update(file_obj._defined_named_scopes)
            return include_line_objects
        else:
            sys.exit(f'ERROR: {line_id} - Improperly formatted include directive')

    def _locate_filename(self, filename: str, include_paths: list[str], line_id: LineIdentifier) -> str:
        '''locates the filename in the include paths, and returns the full file path. Errors if file name is ambiguous.'''
        filepath = None
        checked_dirs: set[str] = set()
        for include_dir in include_paths:
            real_include_dir = os.path.realpath(include_dir)
            if real_include_dir in checked_dirs:
                continue
            checked_dirs.add(real_include_dir)
            found_path = os.path.normpath(os.path.join(include_dir, filename))
            if os.path.exists(found_path):
                if filepath is None:
                    filepath = found_path
                else:
                    sys.exit(f'ERROR: {line_id} - include file "{filename}" can be found multiple times in include paths')
        if filepath is None:
            sys.exit(f'ERROR: {line_id} - could not find file "{filename}" to include')
        return filepath

    def _emit_missing_scope_warnings(self) -> None:
        for scope_name, line_id in self._used_named_scopes:
            if scope_name not in self._defined_named_scopes:
                self._warning_reporter.warn(
                    line_id,
                    f'Named scope "{scope_name}" used with #use-scope but not defined in this file or its includes'
                )
