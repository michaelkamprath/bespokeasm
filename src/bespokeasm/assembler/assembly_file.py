# Assembly File
#
# this class models an assembly file. AN AssemblyFile object is created for each
# assembly file that is loaded. It is responsible for:
#
#    * providing a list of lines
#    * having a single file symbol scope
from __future__ import annotations

import os
import re

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.counter_coordinate_line import CounterCoordinateLine
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
from bespokeasm.assembler.parsing import split_line_comment
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope import SymbolScopeType
from bespokeasm.assembler.symbol_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.symbol_scope.named_scope_manager import NamedScopeManager


class AssemblyFile:
    def __init__(
                self,
                filename: str,
                parent_symbol_scope: SymbolScope,
                named_scope_manager: NamedScopeManager,
                diagnostic_reporter: DiagnosticReporter,
            ) -> None:
        if diagnostic_reporter is None:
            raise ValueError('DiagnosticReporter is required for AssemblyFile')
        self._filename = filename
        self._named_scope_manager = named_scope_manager
        self._diagnostic_reporter = diagnostic_reporter
        self._used_named_scopes: list[tuple[str, LineIdentifier]] = []
        self._defined_named_scopes: set[str] = set()
        self._symbol_scope = SymbolScope(
                SymbolScopeType.FILE,
                parent_symbol_scope,
                self._filename,
            )

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def symbol_scope(self) -> SymbolScope:
        return self._symbol_scope

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
                current_scope = self.symbol_scope
                current_memzone = memzone_manager.global_zone
                condition_stack = ConditionStack(self._diagnostic_reporter)
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
                                    self._diagnostic_reporter.warn(
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
                            instruction_portion, comment_portion = split_line_comment(line_str)
                            instruction_str = instruction_portion.strip()
                            comment_str = comment_portion.strip()
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
                                        self._diagnostic_reporter.warn(
                                            lobj.line_id,
                                            f'Named scope "{lobj.scope_name}" is already active; '
                                            '#use-scope has no effect'
                                        )
                                    self._used_named_scopes.append((lobj.scope_name, lobj.line_id))
                                elif isinstance(lobj, DeactivateScopeLine):
                                    if lobj.scope_name not in active_named_scopes:
                                        self._diagnostic_reporter.warn(
                                            lobj.line_id,
                                            f'Named scope "{lobj.scope_name}" is not active; '
                                            '#deactivate-scope has no effect'
                                        )
                                if isinstance(lobj, LabelLine):
                                    if not lobj.is_constant \
                                            and SymbolScopeType.get_symbol_scope(lobj.get_label()) != SymbolScopeType.LOCAL:
                                        current_scope = SymbolScope(SymbolScopeType.LOCAL, self.symbol_scope, lobj.get_label())
                                # Both .org and .memzone reset symbol scope to FILE.
                                elif isinstance(lobj, SetMemoryZoneLine):
                                    if (
                                        isinstance(lobj, AddressOrgLine)
                                        and not lobj.has_explicit_memzone_name
                                        and current_memzone.name != GLOBAL_ZONE_NAME
                                    ):
                                        self._diagnostic_reporter.warn(
                                            lobj.line_id,
                                            f'.org without a memzone name uses an absolute address; '
                                            f'current memzone is "{current_memzone.name}"',
                                        )
                                    current_scope = self.symbol_scope
                                    current_memzone = lobj.memory_zone
                                elif isinstance(lobj, UseScopeLine) or isinstance(lobj, CreateScopeLine):
                                    active_named_scopes.activate_named_scope(lobj.scope_name)
                                elif isinstance(lobj, DeactivateScopeLine):
                                    active_named_scopes.deactivate_named_scope(lobj.scope_name)
                                lobj.symbol_scope = current_scope
                                lobj.active_named_scopes = active_named_scopes
                                lobj.diagnostic_reporter = self._diagnostic_reporter
                                if isinstance(lobj, CounterCoordinateLine):
                                    if not isa_model.static_analysis_enabled:
                                        lobj.symbol_scope.record_ignored_counter_coordinate(
                                            lobj.label,
                                            lobj.line_id,
                                        )
                                    elif not isa_model.flow_counters_enabled:
                                        self._diagnostic_reporter.error(
                                            lobj.line_id,
                                            'this instruction set does not enable flow counters',
                                            category='flow',
                                        )
                                elif lobj.flow_expression_nodes:
                                    if not isa_model.static_analysis_enabled:
                                        function_name = lobj.flow_expression_nodes[0].value.rstrip('(')
                                        self._diagnostic_reporter.error(
                                            lobj.line_id,
                                            f'static analysis is disabled; cannot resolve {function_name}()',
                                            category='flow',
                                        )
                                    if not isa_model.flow_counters_enabled:
                                        self._diagnostic_reporter.error(
                                            lobj.line_id,
                                            'this instruction set does not enable flow counters',
                                            category='flow',
                                        )
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
                                        lobj.symbol_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
                            line_objects.append(lobj)
        except FileNotFoundError:
            self._diagnostic_reporter.error(
                None,
                f'Compilation file "{self.filename}" not found.',
            )

        self._diagnostic_reporter.info(
            None,
            f'Found {len(line_objects)} lines in source file {self.filename}',
            min_verbosity=2,
        )

        if condition_stack.is_muted:
            line_id = LineIdentifier(line_num if line_num > 0 else 1, filename=self.filename)
            self._diagnostic_reporter.warn(
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
                self._diagnostic_reporter.error(
                    line_id,
                    'assembly file included multiple times',
                )
            file_obj = AssemblyFile(
                new_filepath,
                self.symbol_scope.parent,
                self._named_scope_manager,
                self._diagnostic_reporter,
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
            self._diagnostic_reporter.error(
                line_id,
                'Improperly formatted include directive',
            )

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
                    self._diagnostic_reporter.error(
                        line_id,
                        f'include file "{filename}" can be found multiple times in include paths',
                    )
        if filepath is None:
            self._diagnostic_reporter.error(
                line_id,
                f'could not find file "{filename}" to include',
            )
        return filepath

    def _emit_missing_scope_warnings(self) -> None:
        for scope_name, line_id in self._used_named_scopes:
            if scope_name not in self._defined_named_scopes:
                self._diagnostic_reporter.warn(
                    line_id,
                    f'Named scope "{scope_name}" used with #use-scope but not defined in this file or its includes'
                )
