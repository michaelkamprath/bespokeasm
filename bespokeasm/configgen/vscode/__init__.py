import importlib.resources as pkg_resources
import json
import os
from pathlib import Path
import shutil

from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.configgen import LanguageConfigGenerator
import bespokeasm.configgen.vscode.resources as resources

class VSCodeConfigGenerator(LanguageConfigGenerator):
    def __init__(
            self,
            config_file_path: str,
            is_verbose: int,
            vscode_config_dir: str,
            language_name: str,
            language_version: str,
            code_extension: str,
        ) -> None:
        super().__init__(config_file_path, is_verbose)
        self._vscode_config_dir = vscode_config_dir
        self._language_name = self.model.isa_name
        self._language_version = self.model.isa_version
        self._code_extension = code_extension

    @property
    def vscode_config_dir(self) -> str:
        return self._vscode_config_dir
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
        extension_name = self.language_name
        extension_dir_path = os.path.join(self.vscode_config_dir, 'extensions', extension_name)
        language_id = self.language_name + '-assembly'

        if self.verbose >= 1:
            print(f'Generating Visual Studio Code extension for language "{language_id}" at: {extension_dir_path}')

        # create the extensions directory if it doesn't exist
        Path(extension_dir_path).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(extension_dir_path, 'syntaxes')).mkdir(parents=True, exist_ok=True)
        # generate package.json
        with pkg_resources.path(resources, 'package.json') as fp:
            with open(fp, 'r') as json_file:
                package_json = json.load(json_file)

        package_json['name'] = self.language_name
        package_json['version'] = self.language_version
        package_json['contributes']['languages'][0]['id'] = language_id
        package_json['contributes']['languages'][0]['extensions'] = ['.'+self.code_extension]
        package_json['contributes']['grammars'][0]['language'] = language_id
        package_json['contributes']['snippets'][0]['language'] = language_id
        package_fp = os.path.join(extension_dir_path, 'package.json')
        with open(package_fp, 'w', encoding='utf-8') as f:
            json.dump(package_json, f, ensure_ascii=False, indent=4)
        if self.verbose > 2:
            print(f'package.json = {json.dumps(package_json, indent=4)}')

        # generate tmGrammar.json
        with pkg_resources.path(resources, 'tmGrammar.json') as fp:
            with open(fp, 'r') as json_file:
                grammar_json = json.load(json_file)

        instructions_str: str = grammar_json['repository']['instructions']['match']
        instructions_regex = '|'.join(self.model.instruction_mnemonics)
        grammar_json['repository']['instructions']['match'] = instructions_str.replace('##INSTRUCTIONS##', instructions_regex)
        if len(self.model.registers) > 0:
            # update the registers syntax
            registers_str: str = grammar_json['repository']['registers']['match']
            registers_regex = '|'.join(self.model.registers)
            grammar_json['repository']['registers']['match'] = registers_str.replace('##REGISTERS##', registers_regex)
        else:
            # remove the registers syntax
            del grammar_json['repository']['registers']
        tmGrammar_fp = os.path.join(extension_dir_path, 'syntaxes', 'tmGrammar.json')
        with open(tmGrammar_fp, 'w', encoding='utf-8') as f:
            json.dump(grammar_json, f, ensure_ascii=False, indent=4)
        if self.verbose > 2:
            print(f'\ntmGrammar.json = {json.dumps(grammar_json, indent=4)}')

        # copy snippets.json and lanaguage-configuration.json, nothing to modify
        with pkg_resources.path(resources, 'snippets.json') as fp:
            shutil.copy(str(fp), extension_dir_path)
            if self.verbose > 2:
                with open(fp, 'r') as json_file:
                    json_obj = json.load(json_file)
                    print(f'\nsnippets.json = {json.dumps(json_obj, indent=4)}')

        with pkg_resources.path(resources, 'language-configuration.json') as fp:
            shutil.copy(str(fp), extension_dir_path)
            if self.verbose > 2:
                with open(fp, 'r') as json_file:
                    json_obj = json.load(json_file)
                    print(f'\nlanguage-configuration.json = {json.dumps(json_obj, indent=4)}')


