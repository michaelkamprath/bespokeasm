import json
import importlib.resources as pkg_resources
import os
import pathlib as pl
import re
import shutil
import tempfile
import unittest

from test import config_files

from bespokeasm.configgen.vscode import VSCodeConfigGenerator

class TestConfigurationGeneration(unittest.TestCase):

    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))

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
        self.assertEqual(package_json['contributes']['languages'][0]['id'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['languages'][0]['extensions'], ['.asmtest'], 'file extension list should match')
        self.assertEqual(package_json['contributes']['grammars'][0]['language'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['snippets'][0]['language'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')
        self.assertEqual(package_json['contributes']['snippets'][0]['language'], 'bespokeasm-test-assembly', 'language ID should be modified ISA name')

        grammar_fp = os.path.join(extension_dirpath, 'bespokeasm-test', 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp, 'r') as json_file:
            grammar_json = json.load(json_file)
        instruction_str = grammar_json['repository']['instructions']['match']
        instruction_match = re.search(r'\(\?\:(.*)\)', instruction_str, re.IGNORECASE)
        self.assertIsNotNone(instruction_match, 'instruction match should be found')
        instruction_list = set(instruction_match.group(1).split('|'))
        self.assertSetEqual(instruction_list, set(['lda', 'add', 'set', 'big', 'hlt']), 'all instructions should be found')
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
        instruction_str = grammar_json['repository']['instructions']['match']
        instruction_match = re.search(r'\(\?\:(.*)\)', instruction_str, re.IGNORECASE)
        self.assertIsNotNone(instruction_match, 'instruction match should be found')
        instruction_list = set(instruction_match.group(1).split('|'))
        self.assertSetEqual(instruction_list, set(['nop', 'mov']), 'all instructions should be found')
        registers_str = grammar_json['repository']['registers']['match']
        regsiters_match = re.search(r'\(\?\:(.*)\)', registers_str, re.IGNORECASE)
        self.assertIsNotNone(regsiters_match, 'registers match should be found')
        registers_list = set(regsiters_match.group(1).split('|'))
        self.assertSetEqual(registers_list, set(['a', 'i', 'h', 'l', 'hl', 'sp', 'mar']), 'all registers should be found')

        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'snippets.json'))
        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'language-configuration.json'))

        shutil.rmtree(test_dir)
