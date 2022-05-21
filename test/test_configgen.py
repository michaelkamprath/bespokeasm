import json
import importlib.resources as pkg_resources
import os
import pathlib as pl
import re
import shutil
import tempfile
import unittest
import yaml

from test import config_files

from bespokeasm.configgen.vscode import VSCodeConfigGenerator
from bespokeasm.configgen.sublime import SublimeConfigGenerator

class TestConfigurationGeneration(unittest.TestCase):

    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))

    def _assert_grouped_item_list(self, item_str: str, target_list: list[str], test_name: str) -> None:
        match = re.search(r'^.*(?<=[\w\)])\((?:\?\:)?(.*)\)', item_str, re.IGNORECASE)
        self.assertIsNotNone(match, f'{test_name} match should be found')
        match_list = set(match.group(1).split('|'))
        self.assertSetEqual(match_list, set(target_list), f'all items from "{test_name}" should be found')

    def test_vscode_configgen_no_registers(self):
        test_dir = tempfile.mkdtemp()
        with pkg_resources.path(config_files, 'test_instruction_line_creation_little_endian.yaml') as config_file:
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
        with open(package_fp, 'r') as json_file:
            package_json = json.load(json_file)
        self.assertEqual(package_json['name'], 'bespokeasm-test', 'package name should be modified ISA name')
        self.assertEqual(package_json['displayName'], 'Little Endian Line Creation', 'display name should be correct')
        self.assertEqual(package_json['contributes']['languages'][0]['id'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['languages'][0]['extensions'], ['.asmtest'], 'file extension list should match')
        self.assertEqual(package_json['contributes']['grammars'][0]['language'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['snippets'][0]['language'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['snippets'][0]['language'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')

        grammar_fp = os.path.join(extension_dirpath, 'bespokeasm-test', 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp, 'r') as json_file:
            grammar_json = json.load(json_file)
        self._assert_grouped_item_list(
            grammar_json['repository']['instructions']['begin'],
            ['lda', 'add', 'set', 'big', 'hlt'],
            'instructions'
        )
        self.assertFalse(('registers' in grammar_json['repository']), 'no registers should be found')

        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'snippets.json'))
        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'language-configuration.json'))

        shutil.rmtree(test_dir)

    def test_vscode_configgen_with_registers(self):
        test_dir = tempfile.mkdtemp()
        with pkg_resources.path(config_files, 'test_indirect_indexed_register_operands.yaml') as config_file:
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
        with open(package_fp, 'r') as json_file:
            package_json = json.load(json_file)
        self.assertEqual(package_json['name'], 'tester-assembly', 'package name should be modified ISA name')
        self.assertEqual(package_json['contributes']['languages'][0]['id'], 'tester-assembly-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['languages'][0]['extensions'], ['.asmtest'], 'file extension list should match')
        self.assertEqual(package_json['contributes']['grammars'][0]['language'], 'tester-assembly-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['snippets'][0]['language'], 'tester-assembly-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['snippets'][0]['language'], 'tester-assembly-assembly', 'language ID should be modified ISA name')

        grammar_fp = os.path.join(extension_dirpath, 'tester-assembly', 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp, 'r') as json_file:
            grammar_json = json.load(json_file)
        self._assert_grouped_item_list(
            grammar_json['repository']['instructions']['begin'],
            ['nop', 'mov', 'cmp'],
            'instructions'
        )
        self._assert_grouped_item_list(
            grammar_json['repository']['registers']['match'],
            ['a', 'j', 'i', 'h', 'l', 'hl', 'sp', 'mar'],
            'registers'
        )

        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'snippets.json'))
        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'language-configuration.json'))

        shutil.rmtree(test_dir)

    def test_sublime_configgen_no_registers(self):
        test_destination_dir = tempfile.mkdtemp()
        test_tmp_dir = tempfile.mkdtemp()
        with pkg_resources.path(config_files, 'test_instruction_line_creation_little_endian.yaml') as config_file:
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
        with open(syntax_fp, 'r') as yaml_file:
            syntax_dict = yaml.safe_load(yaml_file)

        self.assertListEqual(syntax_dict['file_extensions'], ['asmtest'], 'file extension should be as assigned')
        self._assert_grouped_item_list(
            syntax_dict['contexts']['instructions'][0]['match'],
            ['lda', 'add', 'set', 'big', 'hlt'],
            'instructions'
        )
        self.assertFalse(('registers' in syntax_dict['contexts']), 'no registers should be found')
        self._assert_grouped_item_list(
            syntax_dict['contexts']['compiler_directives'][0]['match'],
            ['\\.org'],
            'compiler directives'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['data_types_directives'][0]['match'],
            ['\\.fill', '\\.zero', '\\.zerountil', '\\.byte', '\\.2byte', '\\.4byte', '\\.8byte', '\\.cstr'],
            'data type directives'
        )
        item_match_str = 'fail'
        for item in syntax_dict['contexts']['preprocessor_directives'][0]['push']:
            if 'scope' in item and item['scope'] == 'keyword.control.preprocessor':
                item_match_str = item['match']
        self._assert_grouped_item_list(
            item_match_str,
            ['include', 'require'],
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
        with pkg_resources.path(config_files, 'test_indirect_indexed_register_operands.yaml') as config_file:
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
        with open(syntax_fp, 'r') as yaml_file:
            syntax_dict = yaml.safe_load(yaml_file)

        self.assertListEqual(syntax_dict['file_extensions'], ['asmtest'], 'file extension should be as assigned')
        self._assert_grouped_item_list(
            syntax_dict['contexts']['instructions'][0]['match'],
            ['nop', 'mov', 'cmp'],
            'instructions'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['registers'][0]['match'],
            ['a', 'j', 'i', 'h', 'l', 'hl', 'sp', 'mar'],
            'registers'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['compiler_directives'][0]['match'],
            ['\\.org'],
            'compiler directives'
        )
        self._assert_grouped_item_list(
            syntax_dict['contexts']['data_types_directives'][0]['match'],
            [
                '\\.fill', '\\.zero', '\\.zerountil',
                '\\.byte', '\\.2byte', '\\.4byte', '\\.8byte',
                '\\.cstr'
            ],
            'data type directives'
        )
        item_match_str = 'fail'
        for item in syntax_dict['contexts']['preprocessor_directives'][0]['push']:
            if 'scope' in item and item['scope'] == 'keyword.control.preprocessor':
                item_match_str = item['match']
        self._assert_grouped_item_list(
            item_match_str,
            ['include', 'require'],
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
