from importlib.abc import Loader
import importlib.resources as pkg_resources
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import yaml
from zipfile import ZipFile

from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.configgen import LanguageConfigGenerator
import bespokeasm.configgen.sublime.resources as resources
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET, BYTECODE_DIRECTIVES_SET, PREPROCESSOR_DIRECTIVES_SET

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
        super().__init__(config_file_path, is_verbose)
        self._save_config_dir = save_config_dir
        self._language_name = self.model.isa_name if language_name is None else language_name
        self._language_version = self.model.isa_version if language_version is None else language_version
        self._code_extension = code_extension

    @property
    def save_config_dir(self) -> str:
        return self._save_config_dir
    @property
    def language_name(self) -> str:
        return self._language_name
    @property
    def language_version(self) -> str:
        return self._language_version
    @property
    def code_extension(self) -> str:
        return self._code_extension

    def generate(self) -> None:
        if self.verbose >= 1:
            print(f'Generating Sublime text editor package for language "{self.language_name}" into: {self.save_config_dir}')
        #create a temp directory to building things in
        tmp_dir = tempfile.mkdtemp()
        self._generate_files_in_dir(tmp_dir)

        archive_fp = os.path.join(self.save_config_dir, self.language_name + '.sublime-package')
        archive_file = ZipFile(archive_fp, 'w')
        for f in os.listdir(tmp_dir):
            archive_file.write(os.path.join(tmp_dir, f), f)
        archive_file.close()

        shutil.rmtree(tmp_dir)

    def _generate_files_in_dir(self, destination_dir: str) -> None:
        if self.verbose >= 3:
            print(f'  Constructing files into temp dir: {destination_dir}')

        #generate syntax file
        with pkg_resources.path(resources, 'sublime-syntax.yaml') as fp:
            with open(fp, 'r') as syntax_file:
                try:
                    syntax_dict = yaml.safe_load(syntax_file)
                except yaml.YAMLError as exc:
                    sys.exit(f'ERROR: {exc}')
        syntax_dict['file_extensions'] = [self.code_extension]
        instructions_str: str = syntax_dict['contexts']['instructions'][0]['match']
        instructions_regex = '|'.join(self.model.instruction_mnemonics)
        syntax_dict['contexts']['instructions'][0]['match'] = instructions_str.replace('##INSTRUCTIONS##', instructions_regex)
        if len(self.model.registers) > 0:
            # update the registers syntax
            registers_str: str = syntax_dict['contexts']['registers'][0]['match']
            registers_regex = '|'.join(self.model.registers)
            syntax_dict['contexts']['registers'][0]['match'] = registers_str.replace('##REGISTERS##', registers_regex)
        else:
            # remove the registers syntax
            del syntax_dict['contexts']['registers']
        directives_regex = '|'.join(['\.'+d for d in COMPILER_DIRECTIVES_SET])
        directives_str = syntax_dict['contexts']['compiler_directives'][0]['match']
        syntax_dict['contexts']['compiler_directives'][0]['match'] =  directives_str.replace('##DIRECTIVES##', directives_regex)
        datatypes_regex = '|'.join(['\.'+d for d in BYTECODE_DIRECTIVES_SET])
        datatypes_str = syntax_dict['contexts']['data_types_directives'][0]['match']
        syntax_dict['contexts']['data_types_directives'][0]['match'] =  datatypes_str.replace('##DATATYPES##', datatypes_regex)
        preprocessor_regex = '|'.join(PREPROCESSOR_DIRECTIVES_SET)
        updated = False
        for rule in syntax_dict['contexts']['preprocessor_directives'][0]['push']:
            if 'match' in rule and '##PREPROCESSOR##' in rule['match']:
                preprocesspr_str = rule['match']
                rule['match'] = preprocesspr_str.replace('##PREPROCESSOR##', preprocessor_regex)
                updated = True
                break
        if not updated:
            sys.exit('ERROR - INTERNAL - did not find correct preprocessor rule for Sublime systax file.')

        syntax_fp = os.path.join(destination_dir, self.language_name + '.sublime-syntax')
        with open(syntax_fp, 'w', encoding='utf-8') as f:
            yaml.dump(syntax_dict, f)
        # now reinsert the YAML prefix. This is required due to an odditity in Sublime's package loading.
        # I don't know a better way to do this.
        with open(syntax_fp, "r") as f:
            file_txt = f.read()
        updated_file_txt = '%YAML 1.2\n---\n' + file_txt
        with open(syntax_fp, "w") as f:
            f.write(updated_file_txt)
            if self.verbose > 2:
                print(f'  generated {os.path.basename(syntax_fp)}')

        # copy color files over
        color_scheme_fp = os.path.join(destination_dir, self.language_name + '.sublime-color-scheme')
        with pkg_resources.path(resources, 'sublime-color-scheme.json') as fp:
            shutil.copy(str(fp), color_scheme_fp)
            if self.verbose > 2:
                print(f'  generated {os.path.basename(color_scheme_fp)}')

        # copy all snippet files
        for filename in pkg_resources.contents(resources):
            if filename.endswith('.sublime-snippet.xml'):
                file_obj = pkg_resources.files(resources).joinpath(filename)
                with pkg_resources.as_file(file_obj) as fp:
                    snippet_name = filename.partition('.')[0]
                    snippet_fp = os.path.join(destination_dir, self.language_name + '__' + snippet_name + '.sublime-snippet')
                    shutil.copy(fp, snippet_fp)
                    if self.verbose > 2:
                        print(f'  generated {os.path.basename(snippet_fp)}')
