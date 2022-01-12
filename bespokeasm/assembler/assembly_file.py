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
from packaging import version
import re
import sys

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.directive_line import AddressOrgLine
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.model import AssemblerModel


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
                log_verbosity: int,
                assembly_files_used: set = set()
            ) -> list[LineObject]:
        line_objects = []

        with open(self.filename, 'r') as f:
            assembly_files_used.add(self.filename)
            line_num = 0
            current_scope = self.label_scope
            for line in f:
                line_num += 1
                line_id = LineIdentifier(line_num, filename=self.filename)
                line_str = line.strip()
                if len(line_str) > 0:
                    # check to see if this is a #include line
                    if line_str.startswith('#include'):
                        additional_line_objects = self._handle_include_file(
                            line_str,
                            line_id,
                            isa_model,
                            include_paths,
                            log_verbosity,
                            assembly_files_used
                        )
                        line_objects.extend(additional_line_objects)
                        continue
                    if line_str.startswith('#require'):
                        self._handle_require_language(line_str, line_id, isa_model, log_verbosity)
                        continue

                    lobj = LineOjectFactory.parse_line(line_id, line_str, isa_model)
                    if isinstance(lobj, LabelLine):
                        if not lobj.is_constant and LabelScopeType.get_label_scope(lobj.get_label()) != LabelScopeType.LOCAL:
                            current_scope = LabelScope(LabelScopeType.LOCAL, self.label_scope, lobj.get_label())
                    elif isinstance(lobj, AddressOrgLine):
                        current_scope = self.label_scope
                    lobj.label_scope = current_scope
                    # setting constants now so they can be used when evluating lines later.
                    if isinstance(lobj, LabelLine) and lobj.is_constant:
                        lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
                    line_objects.append(lobj)

        if log_verbosity > 1:
            click.echo(f'Found {len(line_objects)} lines in source file {self.filename}')

        return line_objects

    PATTERN_INCLUDE_FILE = re.compile(
        r'^\#include\s+(?:\'|\")([\w\.]+)(?:\'|\")',
        flags=re.IGNORECASE | re.MULTILINE
    )
    PATTERN_REQUIRE_LANGUAGE = re.compile(
        r'\#require\s+\"([\w\-\_\.]*)(?:\s*(==|>=|<=|>|<)\s*({0}))?\"'.format(version.VERSION_PATTERN),
        flags=re.IGNORECASE | re.VERBOSE
    )

    def _handle_include_file(
                self,
                line_str: int,
                line_id: LineIdentifier,
                isa_model: AssemblerModel,
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
                log_verbosity,
                assembly_files_used=assembly_files_used
            )
        else:
            sys.exit(f'ERROR: {line_id} - Improperly formatted include directive')

    def _handle_require_language(
                self,
                line_str: int,
                line_id: LineIdentifier,
                isa_model: AssemblerModel,
                log_verbosity: int
            ) -> None:
        require_match = re.search(AssemblyFile.PATTERN_REQUIRE_LANGUAGE, line_str)
        if require_match is not None:
            required_language = require_match.group(1).strip()
            if required_language != isa_model.isa_name:
                sys.exit(
                    f'ERROR: {line_id} - language "{required_language}" is required but ISA '
                    f'configuration file declares language "{isa_model.isa_name}"'
                )
            if len(require_match.groups()) >= 3 and require_match.group(2) is not None and require_match.group(3) is not None:
                operator_str = require_match.group(2).strip()
                version_str = require_match.group(3).strip()
                version_obj = version.parse(version_str)
                model_version_obj = version.parse(isa_model.isa_version)
                operator_actions = {
                    '>=': {
                        'check': model_version_obj >= version_obj,
                        'error': f'ERROR: {line_id} - at least language version "{version_str}" is required but '
                                 f'ISA configuration file declares language version "{isa_model.isa_version}"',
                    },
                    '<=': {
                        'check': model_version_obj <= version_obj,
                        'error': f'ERROR: {line_id} - up to language version "{version_str}" is required but '
                                 f'ISA configuration file declares language version "{isa_model.isa_version}"',
                    },
                    '>': {
                        'check': model_version_obj > version_obj,
                        'error': f'ERROR: {line_id} - greater than language version "{version_str}" is required but '
                                 f'ISA configuration file declares language version "{isa_model.isa_version}"',
                    },
                    '<': {
                        'check': model_version_obj < version_obj,
                        'error': f'ERROR: {line_id} - less than language version "{version_str}" is required but '
                                 f'ISA configuration file declares language version "{isa_model.isa_version}"',
                    },
                    '==': {
                        'check': model_version_obj < version_obj,
                        'error': f'ERROR: {line_id} - exactly language version "{version_str}" is required but '
                                 f'ISA configuration file declares language version "{isa_model.isa_version}"',
                    },
                }

                if operator_str in operator_actions:
                    if not operator_actions[operator_str]['check']:
                        sys.exit(operator_actions[operator_str]['error'])
                else:
                    sys.exit(f'ERROR: {line_id} - got a language requirement comparison that is not understood.')
                if log_verbosity > 1:
                    print(
                        f'Code file requires language "{require_match.group(1)} {require_match.group(2)} '
                        f'{require_match.group(3)}". Configurate file declares language "{isa_model.isa_name} '
                        f'{isa_model.isa_version}"'
                    )
            elif log_verbosity > 1:
                print(
                    f'Code file requires language "{require_match.group(1)}". '
                    f'Configurate file declares language "{isa_model.isa_name} v{isa_model.isa_version}"'
                )

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
