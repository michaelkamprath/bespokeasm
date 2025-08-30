import importlib.resources as pkg_resources
import json
import os
import pathlib as pl
import re
import shutil
import tempfile
import unittest

from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator
from ruamel.yaml import YAML

from test import config_files


class TestConfigurationGeneration(unittest.TestCase):

    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError('File does not exist: %s' % str(path))

    def _assert_grouped_item_list(self, item_str: str, target_list: list[str], test_name: str) -> None:
        match = re.search(r'^.*(?<=[\w\)])?\((?:\?\:)?(.*)\)', item_str, re.IGNORECASE)
        self.assertIsNotNone(match, f'{test_name} match should be found')
        match_list = set(match.group(1).split('|'))
        self.assertSetEqual(match_list, set(target_list), f'all items from "{test_name}" should be found')

    def test_vscode_configgen_no_registers(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_line_creation_little_endian.yaml')
        configgen = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )

        self.assertEqual(configgen.model.isa_name, 'bespokeasm-test', 'name should be in ISA config')

        configgen.generate()

        extension_dirpath = os.path.join(str(test_dir), 'extensions')

        package_fp = os.path.join(extension_dirpath, 'bespokeasm-test', 'package.json')
        self.assertIsFile(package_fp)
        with open(package_fp) as json_file:
            package_json = json.load(json_file)
        self.assertEqual(
            package_json['name'],
            'bespokeasm-test',
            'package name should be modified ISA name'
        )
        self.assertEqual(
            package_json['displayName'],
            'Little Endian Line Creation',
            'display name should be correct'
        )
        self.assertEqual(
            package_json['contributes']['languages'][0]['id'],
            'bespokeasm-test-assembly',
            'language ID should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['languages'][0]['extensions'],
            ['.asmtest'],
            'file extension list should match'
        )
        self.assertEqual(
            package_json['contributes']['grammars'][0]['language'],
            'bespokeasm-test-assembly',
            'language ID should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['snippets'][0]['language'],
            'bespokeasm-test-assembly',
            'language ID should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['snippets'][0]['language'],
            'bespokeasm-test-assembly',
            'language ID should be modified ISA name'
        )

        grammar_fp = os.path.join(extension_dirpath, 'bespokeasm-test', 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp) as json_file:
            grammar_json = json.load(json_file)
        self._assert_grouped_item_list(
            grammar_json['repository']['instructions']['begin'],
            ['\\blda\\b', '\\badd\\b', '\\bset\\b', '\\bbig\\b', '\\bhlt\\b'],
            'instructions'
        )
        # there should be no macros for this ISA
        self.assertFalse(
            'macros' in grammar_json['repository'],
            'there should be no macros for this ISA'
        )
        for pattern in grammar_json['repository']['main']['patterns']:
            self.assertFalse(
                pattern['include'] == '#macros',
                'there should be no macros for this ISA'
            )

        self.assertFalse(('registers' in grammar_json['repository']), 'no registers should be found')

        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'snippets.json'))
        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'language-configuration.json'))

        shutil.rmtree(test_dir)

    def test_vscode_configgen_with_registers(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_indirect_indexed_register_operands.yaml')
        configgen = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )

        self.assertEqual(configgen.model.isa_name, 'tester-assembly', 'name should be in ISA config')

        configgen.generate()

        extension_dirpath = os.path.join(str(test_dir), 'extensions')

        package_fp = os.path.join(extension_dirpath, 'tester-assembly', 'package.json')
        self.assertIsFile(package_fp)
        with open(package_fp) as json_file:
            package_json = json.load(json_file)
        self.assertEqual(
            package_json['name'],
            'tester-assembly',
            'package name should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['languages'][0]['id'],
            'tester-assembly-assembly',
            'language ID should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['languages'][0]['extensions'],
            ['.asmtest'],
            'file extension list should match'
        )
        self.assertEqual(
            package_json['contributes']['grammars'][0]['language'],
            'tester-assembly-assembly',
            'language ID should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['snippets'][0]['language'],
            'tester-assembly-assembly',
            'language ID should be modified ISA name'
        )
        self.assertEqual(
            package_json['contributes']['snippets'][0]['language'],
            'tester-assembly-assembly',
            'language ID should be modified ISA name'
        )

        grammar_fp = os.path.join(extension_dirpath, 'tester-assembly', 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp) as json_file:
            grammar_json = json.load(json_file)
        self._assert_grouped_item_list(
            grammar_json['repository']['instructions']['begin'],
            ['\\bnop\\b', '\\bmov\\b', '\\bcmp\\b', '\\bjmp\\b'],
            'instructions'
        )
        self._assert_grouped_item_list(
            grammar_json['repository']['registers']['match'],
            ['\\ba\\b', '\\bj\\b', '\\bi\\b', '\\bh\\b', '\\bl\\b', '\\bhl\\b', '\\bsp\\b', '\\bmar\\b'],
            'registers'
        )

        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'snippets.json'))
        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'language-configuration.json'))

        shutil.rmtree(test_dir)

    def test_sublime_configgen_no_registers(self):
        test_destination_dir = tempfile.mkdtemp()
        test_tmp_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_line_creation_little_endian.yaml')
        configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_destination_dir),
            None,
            None,
            'asmtest',
        )

        self.assertEqual(configgen.model.isa_name, 'bespokeasm-test', 'name should be in ISA config')
        # generate the files to inspect their content
        configgen._generate_files_in_dir(test_tmp_dir)

        syntax_fp = os.path.join(test_tmp_dir, 'bespokeasm-test.sublime-syntax')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as yaml_file:
            yaml_loader = YAML()
            syntax_dict = yaml_loader.load(yaml_file)

        self.assertListEqual(syntax_dict['file_extensions'], ['asmtest'], 'file extension should be as assigned')
        for instr_dict in syntax_dict['contexts']['instructions']:
            if instr_dict['scope'] == 'variable.function.instruction':
                self._assert_grouped_item_list(
                    instr_dict['match'],
                    ['\\blda\\b', '\\badd\\b', '\\bset\\b', '\\bbig\\b', '\\bhlt\\b'],
                    'instructions'
                )
            elif instr_dict['scope'] == 'variable.function.macro':
                self.fail('There should be no macros defined in this list')

        for config_dict in syntax_dict['contexts']['pop_instruction_end']:
            if config_dict['name'] == 'instructions':
                self._assert_grouped_item_list(
                    instr_dict['match'],
                    ['\\blda\\b', '\\badd\\b', '\\bset\\b', '\\bbig\\b', '\\bhlt\\b'],
                    'instructions'
                )

        self.assertFalse(('registers' in syntax_dict['contexts']), 'no registers should be found')
        self._assert_grouped_item_list(
            syntax_dict['contexts']['compiler_directives'][0]['match'],
            ['\\.org', '\\.memzone', '\\.align',],
            'compiler directives'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['data_types_directives'][0]['match'],
            [
                '\\.fill', '\\.zero', '\\.zerountil', '\\.byte', '\\.2byte',
                '\\.4byte', '\\.8byte', '\\.cstr', '\\.asciiz',
            ],
            'data type directives'
        )
        item_match_str = 'fail'
        for item in syntax_dict['contexts']['preprocessor_directives'][0]['push']:
            if 'scope' in item and item['scope'] == 'keyword.control.preprocessor':
                item_match_str = item['match']
        self._assert_grouped_item_list(
            item_match_str,
            [
                'include', 'require', 'create_memzone', 'print', 'define', 'if',
                'elif', 'else', 'endif', 'ifdef', 'ifndef',
                'mute', 'unmute', 'emit',
            ],
            'data type directives'
        )
        self.assertIsFile(os.path.join(test_tmp_dir, 'bespokeasm-test.sublime-color-scheme'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'bespokeasm-test__cstr.sublime-snippet'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'bespokeasm-test__include.sublime-snippet'))
        shutil.rmtree(test_tmp_dir)

        # now test generating the zip file
        configgen.generate()
        package_fp = os.path.join(test_destination_dir, 'bespokeasm-test.sublime-package')
        self.assertIsFile(package_fp)

        shutil.rmtree(test_destination_dir)

    def test_sublime_configgen_with_registers(self):
        test_destination_dir = tempfile.mkdtemp()
        test_tmp_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_indirect_indexed_register_operands.yaml')
        configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_destination_dir),
            None,
            None,
            'asmtest',
        )

        self.assertEqual(configgen.model.isa_name, 'tester-assembly', 'name should be in ISA config')
        # generate the files to inspect their content
        configgen._generate_files_in_dir(test_tmp_dir)

        syntax_fp = os.path.join(test_tmp_dir, 'tester-assembly.sublime-syntax')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as yaml_file:
            yaml_loader = YAML()
            syntax_dict = yaml_loader.load(yaml_file)

        self.assertListEqual(syntax_dict['file_extensions'], ['asmtest'], 'file extension should be as assigned')
        for instr_dict in syntax_dict['contexts']['instructions']:
            if instr_dict['scope'] == 'variable.function.instruction':
                self._assert_grouped_item_list(
                    instr_dict['match'],
                    ['\\bnop\\b', '\\bmov\\b', '\\bcmp\\b', '\\bjmp\\b'],
                    'instructions'
                )
            elif instr_dict['scope'] == 'variable.function.macro':
                self.fail('There should be no macros defined in this list')

        for config_dict in syntax_dict['contexts']['pop_instruction_end']:
            if config_dict['name'] == 'instructions':
                self._assert_grouped_item_list(
                    instr_dict['match'],
                    ['\\bnop\\b', '\\bmov\\b', '\\bcmp\\b', '\\bjmp\\b'],
                    'instructions'
                )

        self._assert_grouped_item_list(
            syntax_dict['contexts']['registers'][0]['match'],
            ['\\ba\\b', '\\bj\\b', '\\bi\\b', '\\bh\\b', '\\bl\\b', '\\bhl\\b', '\\bsp\\b', '\\bmar\\b'],
            'registers'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['compiler_directives'][0]['match'],
            ['\\.org', '\\.memzone', '\\.align',],
            'compiler directives'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['data_types_directives'][0]['match'],
            [
                '\\.fill', '\\.zero', '\\.zerountil',
                '\\.byte', '\\.2byte', '\\.4byte', '\\.8byte',
                '\\.cstr', '\\.asciiz',
            ],
            'data type directives'
        )
        item_match_str = 'fail'
        for item in syntax_dict['contexts']['preprocessor_directives'][0]['push']:
            if 'scope' in item and item['scope'] == 'keyword.control.preprocessor':
                item_match_str = item['match']
        self._assert_grouped_item_list(
            item_match_str,
            [
                'include', 'require', 'create_memzone', 'print', 'define',
                'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
                'mute', 'unmute', 'emit',
            ],
            'data type directives'
        )
        self.assertIsFile(os.path.join(test_tmp_dir, 'tester-assembly.sublime-color-scheme'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'tester-assembly__cstr.sublime-snippet'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'tester-assembly__include.sublime-snippet'))
        shutil.rmtree(test_tmp_dir)

        # now test generating the zip file
        configgen.generate()
        package_fp = os.path.join(test_destination_dir, 'tester-assembly.sublime-package')
        self.assertIsFile(package_fp)

        shutil.rmtree(test_destination_dir)

    def test_sublime_escaping_of_names(self):
        # goal of this test is to ensure that entity names sourced from the ISA config are properly escaped
        # in the generated language configuration files, notablye the syntax highlighting configuration file.
        # for example, if an instruction mnemonic is 'ad.r', the generated regex should be '\\bad\\.r\\b'
        # where the '.' is escaped to '\.' and the whole string is wrapped in '\\b' to ensure it is a word boundary.
        test_destination_dir = tempfile.mkdtemp()
        test_tmp_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instructions_with_periods.yaml')
        configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_destination_dir),
            None,
            None,
            'asmtest',
        )
        self.assertEqual(configgen.model.isa_name, 'test_instructions_with_periods', 'name should be in ISA config')
        # generate the files to inspect their content
        configgen._generate_files_in_dir(test_tmp_dir)

        syntax_fp = os.path.join(test_tmp_dir, 'test_instructions_with_periods.sublime-syntax')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as yaml_file:
            yaml_loader = YAML()
            syntax_dict = yaml_loader.load(yaml_file)

        for instr_dict in syntax_dict['contexts']['instructions']:
            if instr_dict['scope'] == 'variable.function.instruction':
                self._assert_grouped_item_list(
                    instr_dict['match'],
                    [
                        '\\bnop\\b',
                        '\\bma\\.hl\\b',    # note the escaped '.'
                    ],
                    'instructions'
                )
            elif instr_dict['scope'] == 'variable.function.macro':
                self.fail('There should be no macros defined in this list')

        # clean up
        shutil.rmtree(test_tmp_dir)

    def test_vscode_and_sublime_include_aliases(self):
        # Use the instruction alias config
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_aliases.yaml')
        # VSCode
        configgen_vscode = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        configgen_vscode.generate()
        extension_dirpath = os.path.join(str(test_dir), 'extensions')
        # Dynamically find the generated extension directory
        ext_subdirs = [d for d in os.listdir(extension_dirpath) if os.path.isdir(os.path.join(extension_dirpath, d))]
        self.assertTrue(ext_subdirs, 'No extension subdirectory found')
        ext_dir = os.path.join(extension_dirpath, ext_subdirs[0])
        grammar_fp = os.path.join(ext_dir, 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp) as json_file:
            grammar_json = json.load(json_file)
        # All mnemonics and aliases should be present
        regex_str = grammar_json['repository']['instructions']['begin']
        # Remove leading (?i)( and trailing ) if present
        if regex_str.startswith('(?i)(') and regex_str.endswith(')'):
            regex_str = regex_str[5:-1]
        actual = set(regex_str.split('|'))
        expected = {'\\bjsr\\b', '\\bcall\\b', '\\bjsr2\\b', '\\bcall2\\b', '\\bjump_to_subroutine\\b', '\\bnop\\b'}
        self.assertSetEqual(actual, expected, 'VSCode: all mnemonics and aliases should be present')
        # Sublime
        configgen_sublime = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            'bespokeasm-test-instruction-aliases',
            '0.1.0',
            'asmtest',
        )
        configgen_sublime.generate()
        # Find the .sublime-package file in test_dir
        sublime_pkg_fp = None
        for file in os.listdir(test_dir):
            if file.endswith('.sublime-package'):
                sublime_pkg_fp = os.path.join(test_dir, file)
                break
        self.assertIsNotNone(sublime_pkg_fp, 'No .sublime-package file found')
        import zipfile
        with zipfile.ZipFile(sublime_pkg_fp, 'r') as zf:
            syntax_files = [f for f in zf.namelist() if f.endswith('.sublime-syntax')]
            self.assertTrue(syntax_files, 'No .sublime-syntax file in package')
            with zf.open(syntax_files[0]) as f:
                syntax = f.read().decode('utf-8')
        # All mnemonics and aliases should be present in the regex
        for mnemonic in ['jsr', 'call', 'jsr2', 'call2', 'jump_to_subroutine', 'nop']:
            self.assertRegex(syntax, rf'\\b{re.escape(mnemonic)}\\b', f'Sublime: {mnemonic} should be present')
