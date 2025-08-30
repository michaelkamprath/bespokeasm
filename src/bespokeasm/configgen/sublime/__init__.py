import importlib.resources as pkg_resources
import os
import shutil
import sys
import tempfile
from zipfile import ZipFile

import bespokeasm.configgen.sublime.resources as resources
from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import EXPRESSION_FUNCTIONS_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.configgen import LanguageConfigGenerator
from ruamel.yaml import YAML


class SublimeConfigGenerator(LanguageConfigGenerator):
    def __init__(
                self,
                config_file_path: str,
                is_verbose: int,
                save_config_dir: str,
                language_name: str,
                language_version: str,
                code_extension: str,
            ) -> None:
        super().__init__(config_file_path, is_verbose, save_config_dir, language_name, language_version, code_extension)

    def generate(self) -> None:
        if self.verbose >= 1:
            print(f'Generating Sublime text editor package for language "{self.language_name}" into: {self.export_dir}')
        # create a temp directory to building things in
        tmp_dir = tempfile.mkdtemp()
        self._generate_files_in_dir(tmp_dir)

        archive_fp = os.path.join(self.export_dir, self.language_name + '.sublime-package')
        archive_file = ZipFile(archive_fp, 'w')
        for f in os.listdir(tmp_dir):
            archive_file.write(os.path.join(tmp_dir, f), f)
        archive_file.close()

        shutil.rmtree(tmp_dir)

    def _generate_files_in_dir(self, destination_dir: str) -> None:
        if self.verbose >= 3:
            print(f'  Constructing files into temp dir: {destination_dir}')

        # generate syntax file
        fp = pkg_resources.files(resources).joinpath('sublime-syntax.yaml')
        yaml_loader = YAML()
        try:
            syntax_dict = yaml_loader.load(fp)
        except Exception as exc:
            sys.exit(f'ERROR: {exc}')

        # handle instructions
        update_instructions = False
        update_macros = False
        syntax_dict['file_extensions'] = [self.code_extension]
        syntax_dict['scope'] = f'source.bespokeasm.{self.code_extension}'
        for idx, instr_dict in enumerate(syntax_dict['contexts']['instructions']):
            if instr_dict['scope'] == 'variable.function.instruction':
                instr_dict['match'] = self._replace_token_with_regex_list(
                    instr_dict['match'],
                    '##INSTRUCTIONS##',
                    self.model.instruction_mnemonics
                )
                update_instructions = True
            elif instr_dict['scope'] == 'variable.function.macro':
                if len(self.model.macro_mnemonics) > 0:
                    instr_dict['match'] = self._replace_token_with_regex_list(
                        instr_dict['match'],
                        '##MACROS##',
                        self.model.macro_mnemonics
                    )
                else:
                    syntax_dict['contexts']['instructions'].remove(instr_dict)
                update_macros = True
        if not update_instructions:
            sys.exit(
                'ERROR - INTERNAL - Could not find "variable.function.instruction" '
                'configuration in instructions for Sulime syntax'
            )
        if not update_macros:
            sys.exit(
                'ERROR - INTERNAL - Could not find "variable.function.macro" configuration '
                'in instructions for Sulime syntax'
            )

        for idx, config_dict in enumerate(syntax_dict['contexts']['pop_instruction_end']):
            if config_dict['name'] == 'instructions':
                index = idx
                break
        if index is None:
            sys.exit('ERROR - INTERNAL - Could not find "instruction" configuration in pop_instruction_end for Sulime syntax')
        syntax_dict['contexts']['pop_instruction_end'][index]['match'] = self._replace_token_with_regex_list(
            syntax_dict['contexts']['pop_instruction_end'][index]['match'],
            '##INSTRUCTIONS##',
            self.model.operation_mnemonics
        )

        # handle registers
        if len(self.model.registers) > 0:
            if self.verbose > 2:
                print(f'  adding syntax for a total of {len(self.model.registers)} registers')
            # update the registers syntax
            syntax_dict['contexts']['registers'][0]['match'] = self._replace_token_with_regex_list(
                syntax_dict['contexts']['registers'][0]['match'],
                '##REGISTERS##',
                self.model.registers
            )
        else:
            # remove the registers syntax
            del syntax_dict['contexts']['registers']

        # handle compiler predefined labels
        predefined_labels = self.model.predefined_labels
        if len(predefined_labels) > 0:
            if self.verbose > 2:
                print(f'  adding syntax for a total of {len(predefined_labels)} predefined labels')
            # update the registers syntax
            syntax_dict['contexts']['compiler_labels'][0]['match'] = self._replace_token_with_regex_list(
                syntax_dict['contexts']['compiler_labels'][0]['match'],
                '##COMPILERCONSTANTS##',
                predefined_labels,
            )
        else:
            # remove the registers syntax
            del syntax_dict['contexts']['compiler_labels']

        # compiler directives
        directives_regex = '|'.join(['\\.'+d for d in COMPILER_DIRECTIVES_SET])
        directives_str = syntax_dict['contexts']['compiler_directives'][0]['match']
        syntax_dict['contexts']['compiler_directives'][0]['match'] = \
            directives_str.replace('##DIRECTIVES##', directives_regex)

        # data types
        datatypes_regex = '|'.join(['\\.'+d for d in BYTECODE_DIRECTIVES_SET])
        datatypes_str = syntax_dict['contexts']['data_types_directives'][0]['match']
        syntax_dict['contexts']['data_types_directives'][0]['match'] = datatypes_str.replace('##DATATYPES##', datatypes_regex)

        # preprocessor directives
        # Sort by length (desc) to avoid prefix matches like 'if' matching 'ifdef'
        preprocessor_regex = '|'.join(sorted(PREPROCESSOR_DIRECTIVES_SET, key=len, reverse=True))
        updated = False
        for rule in syntax_dict['contexts']['preprocessor_directives'][0]['push']:
            if 'match' in rule and '##PREPROCESSOR##' in rule['match']:
                preprocesspr_str = rule['match']
                rule['match'] = preprocesspr_str.replace('##PREPROCESSOR##', preprocessor_regex)
                updated = True
                break
        if not updated:
            sys.exit('ERROR - INTERNAL - did not find correct preprocessor rule for Sublime systax file.')

        # expression functions
        func_regex = '|'.join([d for d in EXPRESSION_FUNCTIONS_SET])
        updated = False
        for rule in syntax_dict['contexts']['numerical_expressions']:
            if 'scope' in rule and rule['scope'] == 'keyword.operator.word':
                func_str = rule['match']
                rule['match'] = func_str.replace('##EXPRESSION_FUNCTIONS##', func_regex)
                updated = True
                break
        if not updated:
            sys.exit('ERROR - INTERNAL - did not find correct expression function rule for Sublime systax file.')

        # save syntax file
        syntax_fp = os.path.join(destination_dir, self.language_name + '.sublime-syntax')
        yaml_dumper = YAML()
        with open(syntax_fp, 'w', encoding='utf-8') as f:
            yaml_dumper.dump(syntax_dict, f)
        # now reinsert the YAML prefix. This is required due to an odditity in Sublime's package loading.
        # I don't know a better way to do this.
        with open(syntax_fp) as f:
            file_txt = f.read()
        updated_file_txt = '%YAML 1.2\n---\n' + file_txt
        with open(syntax_fp, 'w') as f:
            f.write(updated_file_txt)
            if self.verbose > 1:
                print(f'  generated {os.path.basename(syntax_fp)}')

        # copy color files over
        color_scheme_fp = os.path.join(destination_dir, self.language_name + '.sublime-color-scheme')
        fp = pkg_resources.files(resources).joinpath('sublime-color-scheme.json')
        shutil.copy(str(fp), color_scheme_fp)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(color_scheme_fp)}')

        # copy keymap files over
        keymap_fp = os.path.join(destination_dir, 'Default.sublime-keymap')
        fp = pkg_resources.files(resources).joinpath('sublime-keymap.json')
        shutil.copy(str(fp), keymap_fp)
        # replace the file extension name in the keymap file
        self._replace_token_in_file(keymap_fp, '##FILEEXTENSION##', self.code_extension)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(keymap_fp)}')

        # copy all snippet, macro, and preference files
        for filename in [path.name for path in pkg_resources.files(resources).iterdir()]:
            if filename.endswith('.sublime-snippet.xml'):
                file_obj = pkg_resources.files(resources).joinpath(filename)
                with pkg_resources.as_file(file_obj) as fp:
                    snippet_name = filename.partition('.')[0]
                    snippet_fp = os.path.join(destination_dir, self.language_name + '__' + snippet_name + '.sublime-snippet')
                    shutil.copy(fp, snippet_fp)
                    # replace the file extension name in the snippet file
                    self._replace_token_in_file(snippet_fp, '##FILEEXTENSION##', self.code_extension)
                    if self.verbose > 1:
                        print(f'  generated {os.path.basename(snippet_fp)}')
            elif filename.endswith('.sublime-macro.json'):
                file_obj = pkg_resources.files(resources).joinpath(filename)
                with pkg_resources.as_file(file_obj) as fp:
                    macro_filename = filename.partition('.')[0] + '.sublime-macro'
                    macro_fp = os.path.join(destination_dir, macro_filename)
                    shutil.copy(fp, macro_fp)
                    if self.verbose > 1:
                        print(f'  generated {os.path.basename(macro_fp)}')
            elif filename.endswith('.tmPreferences.xml'):
                file_obj = pkg_resources.files(resources).joinpath(filename)
                with pkg_resources.as_file(file_obj) as fp:
                    pref_filename = filename.partition('.')[0] + '.tmPreferences'
                    pref_fp = os.path.join(destination_dir, pref_filename)
                    shutil.copy(fp, pref_fp)
                    # replace the file extension name in the preference file
                    self._replace_token_in_file(pref_fp, '##FILEEXTENSION##', self.code_extension)
                    if self.verbose > 1:
                        print(f'  generated {os.path.basename(pref_fp)}')
