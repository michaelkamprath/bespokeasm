import importlib.resources as pkg_resources
import json
import os
import pathlib as pl
import re
import shutil
import tempfile
import unittest

from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
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
                'create-scope', 'use-scope', 'deactivate-scope',
            ],
            'preprocessor directives'
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
                'create-scope', 'use-scope', 'deactivate-scope',
            ],
            'preprocessor directives'
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

    def test_vim_instruction_with_periods(self):
        # Ensure Vim generator escapes instruction mnemonics with periods (e.g., AN.z)
        import tempfile
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instructions_with_periods.yaml')
        from bespokeasm.configgen.vim import VimConfigGenerator
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        configgen.generate()
        vim_ft = (configgen.language_id.replace('-', '').lower())
        syntax_fp = os.path.join(str(test_dir), 'syntax', f'{vim_ft}.vim')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as f:
            syn = f.read()
        # The instruction match should contain an escaped version of 'ma.hl' from the test config
        # and also support word boundary around it.
        self.assertRegex(
            syn,
            r'syn\s+match\s+\w+Instruction\s+/.+ma\\\.hl.+/',
            'Vim: instruction with period should be escaped and matched',
        )
        # String punctuation should be a separate matchgroup from the string body
        self.assertIn('matchgroup=' + vim_ft + 'StringPunc', syn)
        shutil.rmtree(test_dir)

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
        expected = {
            '\\bjsr\\b', '\\bcall\\b', '\\bjsr2\\b', '\\bcall2\\b',
            '\\bjump_to_subroutine\\b', '\\bnop\\b'
        }
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
            self.assertRegex(
                syntax,
                rf'\\b{re.escape(mnemonic)}\\b',
                f'Sublime: {mnemonic} should be present',
            )

    def test_vim_configgen_no_registers(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_line_creation_little_endian.yaml')
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        self.assertEqual(configgen.model.isa_name, 'bespokeasm-test', 'name should be in ISA config')
        configgen.generate()
        # Compute Vim filetype (sanitized)
        vim_ft = (configgen.language_id.replace('-', '').lower())
        syntax_fp = os.path.join(str(test_dir), 'syntax', f'{vim_ft}.vim')
        ftdetect_fp = os.path.join(str(test_dir), 'ftdetect', f'{vim_ft}.vim')
        self.assertIsFile(syntax_fp)
        self.assertIsFile(ftdetect_fp)
        with open(syntax_fp) as f:
            syn = f.read()
        # Instructions present (syn match alternation with word boundaries)
        m = re.search(rf'^syn\s+match\s+{re.escape(vim_ft)}Instruction\s+/(.+)/$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'Instruction match line should exist')
        pat = m.group(1)
        # Extract the alternation group between \%( ... ) without using nested-regex
        start = pat.find(r'\%(')
        end = pat.rfind(r'\)')
        self.assertTrue(start >= 0 and end > start, 'Instruction pattern should contain alternation group')
        group = pat[start+3:end]
        for mnemonic in ['lda', 'add', 'set', 'big', 'hlt']:
            self.assertRegex(group, rf'(?:^|\\\|){re.escape(mnemonic)}(?:\\\||$)')
        # No macros
        self.assertIsNone(re.search(rf'^syn\s+keyword\s+{re.escape(vim_ft)}Macro\b', syn, re.MULTILINE), 'No macros expected')
        # No registers
        self.assertIsNone(
            re.search(rf'^syn\s+keyword\s+{re.escape(vim_ft)}Register\b', syn, re.MULTILINE),
            'No registers expected',
        )
        # Directives
        self.assertRegex(syn, rf'syn\s+match\s+{re.escape(vim_ft)}Directive\s+/.+\\.org\\>/', 'directive .org present')
        self.assertRegex(syn, rf'syn\s+match\s+{re.escape(vim_ft)}Directive\s+/.+\\.memzone\\>/', 'directive .memzone present')
        self.assertRegex(syn, rf'syn\s+match\s+{re.escape(vim_ft)}Directive\s+/.+\\.align\\>/', 'directive .align present')
        # Data types
        for dt in ['fill', 'zero', 'zerountil', 'byte', '2byte', '4byte', '8byte', 'cstr', 'asciiz']:
            self.assertRegex(
                syn,
                rf'syn\s+match\s+{re.escape(vim_ft)}DataType\s+/.+\\.{re.escape(dt)}\\>/',
                f'datatype .{dt} present',
            )
        # Preprocessor
        # Punctuation hash is highlighted separately and chains to macro group
        m = re.search(rf'^syn\s+match\s+{re.escape(vim_ft)}PreProcPunc\s+/(.+)$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'PreProcPunc match line should exist')
        self.assertIn('^#/', m.group(1))
        self.assertIn(f'nextgroup={vim_ft}PreProc', m.group(1))
        for pp in [
            'include', 'require',
            'create_memzone', 'print',
            'define', 'if', 'elif', 'else', 'endif',
            'ifdef', 'ifndef', 'mute', 'unmute', 'emit',
        ]:
            self.assertRegex(
                syn,
                rf'syn\s+match\s+{re.escape(vim_ft)}PreProc\s+/\\<{re.escape(pp)}\\>/',
                f'preprocessor {pp} present',
            )
        # ftdetect
        with open(ftdetect_fp) as f:
            ft = f.read()
        self.assertIn(f'autocmd BufRead,BufNewFile *.asmtest setfiletype {vim_ft}', ft)
        shutil.rmtree(test_dir)

    def test_vim_configgen_with_registers(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_indirect_indexed_register_operands.yaml')
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        self.assertEqual(configgen.model.isa_name, 'tester-assembly', 'name should be in ISA config')
        configgen.generate()
        vim_ft = (configgen.language_id.replace('-', '').lower())
        syntax_fp = os.path.join(str(test_dir), 'syntax', f'{vim_ft}.vim')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as f:
            syn = f.read()
        # Registers present
        m = re.search(rf'^syn\s+keyword\s+{re.escape(vim_ft)}Register\s+(.+)$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'Register keyword line should exist')
        regs = set(m.group(1).split())
        self.assertTrue({'a', 'j', 'i', 'h', 'l', 'hl', 'sp', 'mar'}.issubset(regs))
        # Instructions present
        m = re.search(rf'^syn\s+match\s+{re.escape(vim_ft)}Instruction\s+/(.+)/$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'Instruction match line should exist')
        pat = m.group(1)
        start = pat.find(r'\%(')
        end = pat.rfind(r'\)')
        self.assertTrue(start >= 0 and end > start, 'Instruction pattern should contain alternation group')
        group = pat[start+3:end]
        for mnemonic in ['nop', 'mov', 'cmp', 'jmp']:
            self.assertRegex(group, rf'(?:^|\\\|){re.escape(mnemonic)}(?:\\\||$)')
        shutil.rmtree(test_dir)

    def test_vim_include_aliases(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_aliases.yaml')
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        configgen.generate()
        vim_ft = (configgen.language_id.replace('-', '').lower())
        syntax_fp = os.path.join(str(test_dir), 'syntax', f'{vim_ft}.vim')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as f:
            syn = f.read()
        m = re.search(rf'^syn\s+match\s+{re.escape(vim_ft)}Instruction\s+/(.+)/$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'Instruction match line should exist')
        pat = m.group(1)
        start = pat.find(r'\%(')
        end = pat.rfind(r'\)')
        self.assertTrue(start >= 0 and end > start, 'Instruction pattern should contain alternation group')
        group = pat[start+3:end]
        for mnemonic in ['jsr', 'call', 'jsr2', 'call2', 'jump_to_subroutine', 'nop']:
            self.assertRegex(group, rf'(?:^|\\\|){re.escape(mnemonic)}(?:\\\||$)')
        shutil.rmtree(test_dir)

    def test_vim_background_foreground_colors(self):
        """Test that VIM syntax generator includes background and foreground colors."""
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_line_creation_little_endian.yaml')
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        configgen.generate()
        vim_ft = (configgen.language_id.replace('-', '').lower())
        syntax_fp = os.path.join(str(test_dir), 'syntax', f'{vim_ft}.vim')
        self.assertIsFile(syntax_fp)

        with open(syntax_fp) as f:
            syn = f.read()

        # Test Normal highlight group with background and foreground
        self.assertRegex(
            syn,
            r'hi\s+Normal\s+guifg=#EEEEEE\s+guibg=#222222\s+ctermfg=\d+\s+ctermbg=\d+',
            'Normal highlight should set both foreground and background colors'
        )

        # Test Visual selection background
        self.assertRegex(
            syn,
            r'hi\s+Visual\s+guibg=#294f7a\s+ctermbg=\d+',
            'Visual highlight should set selection background color'
        )

        # Test CursorLine highlighting
        self.assertRegex(
            syn,
            r'hi\s+CursorLine\s+guibg=#444444\s+ctermbg=\d+\s+cterm=NONE\s+gui=NONE',
            'CursorLine highlight should set line highlight background color'
        )

        # Test that syntax elements inherit background (use NONE)
        self.assertRegex(
            syn,
            rf'hi\s+{re.escape(vim_ft)}String\s+guifg=#17d75a\s+guibg=NONE\s+ctermfg=\d+\s+ctermbg=NONE',
            'String highlight should use NONE for background to inherit from Normal'
        )

        # Test that hex numbers have proper color formatting
        self.assertRegex(
            syn,
            rf'hi\s+{re.escape(vim_ft)}HexNumber\s+guifg=#ffe80b\s+guibg=NONE\s+ctermfg=\d+\s+ctermbg=NONE',
            'HexNumber highlight should have proper foreground color and inherit background'
        )

        # Test that brackets maintain their bold styling with color inheritance
        self.assertRegex(
            syn,
            rf'hi\s+{re.escape(vim_ft)}Bracket\s+guifg=#b72dd2\s+guibg=NONE\s+ctermfg=\d+\s+'
            r'ctermbg=NONE\s+gui=bold\s+cterm=bold',
            'Bracket highlight should maintain bold styling while inheriting background'
        )

        shutil.rmtree(test_dir)

    def test_builtin_constants_in_sublime_syntax(self):
        """Test that built-in language version constants are included in Sublime syntax highlighting."""
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            'test-lang',
            '1.0.0',
            'testasm',
        )

        configgen.generate()

        # Extract the generated package and check content
        import zipfile
        package_file = os.path.join(test_dir, 'test-lang.sublime-package')
        self.assertIsFile(package_file)

        extract_dir = os.path.join(test_dir, 'extracted')
        with zipfile.ZipFile(package_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        syntax_fp = os.path.join(extract_dir, 'test-lang.sublime-syntax')
        self.assertIsFile(syntax_fp)

        with open(syntax_fp) as yaml_file:
            yaml_loader = YAML()
            syntax_dict = yaml_loader.load(yaml_file)

        # Check that compiler_labels context exists and contains language version symbols
        self.assertIn('compiler_labels', syntax_dict['contexts'], 'compiler_labels context should exist')
        compiler_labels_match = syntax_dict['contexts']['compiler_labels'][0]['match']

        # Verify all built-in constants are in the match pattern
        from bespokeasm.assembler.keywords import BUILTIN_CONSTANTS_SET
        for constant in BUILTIN_CONSTANTS_SET:
            self.assertIn(constant, compiler_labels_match, f'{constant} should be in compiler labels match pattern')

        # Verify the scope is constant.language
        self.assertEqual(
            syntax_dict['contexts']['compiler_labels'][0]['scope'],
            'constant.language',
            'Built-in constants should have constant.language scope'
        )

        shutil.rmtree(test_dir)

    def test_builtin_constants_in_vscode_syntax(self):
        """Test that built-in language version constants are included in VSCode syntax highlighting."""
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        configgen = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            'test-lang',
            '1.0.0',
            'testasm',
        )

        configgen.generate()

        extension_dirpath = os.path.join(str(test_dir), 'extensions')
        grammar_fp = os.path.join(extension_dirpath, 'test-lang', 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)

        with open(grammar_fp) as json_file:
            grammar_dict = json.load(json_file)

        # Check that compiler_labels exists in repository
        self.assertIn('compiler_labels', grammar_dict['repository'], 'compiler_labels should exist in repository')
        compiler_labels_match = grammar_dict['repository']['compiler_labels']['match']

        # Verify all built-in constants are in the match pattern
        from bespokeasm.assembler.keywords import BUILTIN_CONSTANTS_SET
        for constant in BUILTIN_CONSTANTS_SET:
            self.assertIn(constant, compiler_labels_match, f'{constant} should be in compiler labels match pattern')

        # Verify the name/scope
        self.assertEqual(
            grammar_dict['repository']['compiler_labels']['name'],
            'constant.language',
            'Built-in constants should have constant.language name'
        )

        shutil.rmtree(test_dir)

    def test_builtin_constants_in_vim_syntax(self):
        """Test that built-in language version constants are included in Vim syntax highlighting."""
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('eater-sap1-isa.yaml')
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            'test-lang',
            '1.0.0',
            'testasm',
        )

        configgen.generate()

        vim_ft = (configgen.language_id.replace('-', '').lower())
        syntax_fp = os.path.join(str(test_dir), 'syntax', f'{vim_ft}.vim')
        self.assertIsFile(syntax_fp)

        with open(syntax_fp) as f:
            syn = f.read()

        # Check for CompilerLabel syntax match that includes built-in constants
        m = re.search(rf'^syn\s+match\s+{re.escape(vim_ft)}CompilerLabel\s+/(.+)/$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'CompilerLabel match line should exist')
        compiler_labels_pattern = m.group(1)

        # Verify all built-in constants are in the pattern
        from bespokeasm.assembler.keywords import BUILTIN_CONSTANTS_SET
        for constant in BUILTIN_CONSTANTS_SET:
            # Vim doesn't escape underscores in this context
            self.assertIn(constant, compiler_labels_pattern, f'{constant} should be in Vim compiler labels pattern')

        shutil.rmtree(test_dir)
