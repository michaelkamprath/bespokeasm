import importlib.resources as pkg_resources
import json
import os
import pathlib as pl
import re
import shutil
import tempfile
import unittest

from bespokeasm.configgen.color_scheme import build_hover_color_map
from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
from bespokeasm.configgen.color_scheme import SyntaxElement
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator
from ruamel.yaml import YAML

from test import config_files


class TestConfigurationGeneration(unittest.TestCase):

    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError('File does not exist: %s' % str(path))

    def _assert_constant_definition_pattern(self, pattern: str, source_name: str) -> None:
        compiled = re.compile(pattern)
        cases = {
            'FOO EQU 1': 'FOO',
            '_FOO EQU 1': '_FOO',
            '.foo EQU 1': '.foo',
            'FOO = 1': 'FOO',
            '_FOO = 1': '_FOO',
            '.foo = 1': '.foo',
        }
        for line, expected in cases.items():
            match = compiled.match(line)
            self.assertIsNotNone(match, f'{source_name} should match {line!r}')
            self.assertEqual(match.group(1), expected, f'{source_name} should capture {expected!r}')

        invalid_cases = ['__bad EQU 1', '..bad = 1', '1bad = 1']
        for line in invalid_cases:
            self.assertIsNone(compiled.match(line), f'{source_name} should reject {line!r}')

    def _assert_grouped_item_list(self, item_str: str, target_list: list[str], test_name: str) -> None:
        match = re.search(r'^.*(?<=[\w\)])?\((?:\?\:)?(.*)\)', item_str, re.IGNORECASE)
        self.assertIsNotNone(match, f'{test_name} match should be found')
        match_list = set(match.group(1).split('|'))
        self.assertSetEqual(match_list, set(target_list), f'all items from "{test_name}" should be found')

    def _assert_vim_contextual_syntax(self, syn: str, vim_ft: str) -> None:
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}Instruction\b')
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}Macro\b')
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}Directive\b')
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}DataType\b')
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}Bracket\s+/\\\[')
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}DoubleBracket\b')
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}Paren\b')
        self.assertNotRegex(syn, r'(?m)^hi\s+Normal\b')
        self.assertNotRegex(syn, r'(?m)^hi\s+Visual\b')
        self.assertNotRegex(syn, r'(?m)^hi\s+CursorLine\b')
        self.assertNotIn(f'hi def link {vim_ft}AssignOp', syn)

        self.assertIn(f'syn match {vim_ft}Separator /,/ contained', syn)
        self.assertRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}Param\s+/.*contained$')
        self.assertIn(f'syn region {vim_ft}BracketExpr matchgroup={vim_ft}Bracket', syn)
        self.assertIn(f'syn region {vim_ft}DoubleBracketExpr matchgroup={vim_ft}DoubleBracket', syn)
        self.assertIn(f'syn region {vim_ft}ParenExpr matchgroup={vim_ft}Paren', syn)
        instr_line = next(
            line for line in syn.splitlines()
            if line.startswith(f'syn region {vim_ft}InstrLine ')
        )
        bracket_line = next(
            line for line in syn.splitlines()
            if line.startswith(f'syn region {vim_ft}BracketExpr ')
        )
        self.assertIn(f'{vim_ft}LabelUsage', instr_line)
        self.assertIn(f'{vim_ft}LabelUsage', bracket_line)
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}LabelUsage\b')
        self.assertIn(r'start=/\[\(\[\)\@!/', syn)
        self.assertIn(r'end=/\s*\ze;\|$/ oneline', syn)
        for region_name in ('InstrLine', 'MacroLine'):
            region_line = next(
                (line for line in syn.splitlines() if line.startswith(f'syn region {vim_ft}{region_name} ')),
                None,
            )
            if region_line is not None:
                self.assertIn(r'end=/\s*\ze\<', region_line)
                self.assertIn(r'\|\s*\ze;\|$/ oneline', region_line)
        self.assertIn(f'hi def link {vim_ft}CompilerLabel Constant', syn)
        self.assertIn(f'hi def link {vim_ft}LabelUsage Identifier', syn)
        self.assertIn(f'hi def link {vim_ft}Param Identifier', syn)
        self.assertIn(f'hi def link {vim_ft}Separator Delimiter', syn)
        self.assertIn(f'hi {vim_ft}LabelUsage ', syn)
        self.assertIn(f'hi {vim_ft}AssignOp ', syn)

        param_index = syn.find(f'syn match {vim_ft}Param')
        compiler_label_index = syn.find(f'syn match {vim_ft}CompilerLabel')
        self.assertGreaterEqual(param_index, 0, 'Param match should exist')
        self.assertGreaterEqual(compiler_label_index, 0, 'CompilerLabel match should exist')
        self.assertLess(param_index, compiler_label_index, 'Param must be defined before CompilerLabel')

    def test_operand_label_configgen_scopes_and_colors(self):
        self.assertIn(SyntaxElement.OPERAND_LABEL_AT, DEFAULT_COLOR_SCHEME.colors)
        self.assertIn(SyntaxElement.OPERAND_LABEL_NAME, DEFAULT_COLOR_SCHEME.colors)
        self.assertIn(SyntaxElement.OPERAND_LABEL_COLON, DEFAULT_COLOR_SCHEME.colors)

        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_operand_labels.yaml')

        vscode = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        vscode.generate()
        vscode_ext_dir = os.path.join(test_dir, 'extensions', vscode.language_name)
        grammar_fp = os.path.join(vscode_ext_dir, 'syntaxes', 'tmGrammar.json')
        self.assertIsFile(grammar_fp)
        with open(grammar_fp) as json_file:
            grammar_json = json.load(json_file)
        operand_label_patterns = grammar_json['repository']['operand_label_definitions']['patterns']
        self.assertTrue(operand_label_patterns)
        self.assertNotIn('##LABEL_PATTERN##', operand_label_patterns[0]['match'])
        self.assertIn('(@)', operand_label_patterns[0]['match'])
        self.assertIn('(\\s*)', operand_label_patterns[0]['match'])
        self.assertNotIn(')\\s*(:)', operand_label_patterns[0]['match'])
        self.assertIn(
            '#operand_label_definitions',
            [entry['include'] for entry in grammar_json['repository']['instructions']['patterns'] if 'include' in entry],
        )

        package_fp = os.path.join(vscode_ext_dir, 'package.json')
        with open(package_fp) as json_file:
            package_json = json.load(json_file)
        theme_relpath = package_json['contributes']['themes'][0]['path'].lstrip('./')
        theme_fp = os.path.join(vscode_ext_dir, theme_relpath)
        self.assertIsFile(theme_fp)
        with open(theme_fp) as json_file:
            theme_json = json.load(json_file)
        theme_scopes = {entry['scope'] for entry in theme_json['tokenColors']}
        self.assertIn('punctuation.definition.variable.at.operand-label', theme_scopes)
        self.assertIn('variable.other.label.definition.operand-label', theme_scopes)
        self.assertIn('punctuation.definition.variable.colon.operand-label', theme_scopes)

        sublime_tmp_dir = tempfile.mkdtemp()
        sublime = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        sublime._generate_files_in_dir(sublime_tmp_dir)
        syntax_fp = os.path.join(sublime_tmp_dir, f'{sublime.language_name}.sublime-syntax')
        self.assertIsFile(syntax_fp)
        with open(syntax_fp) as yaml_file:
            syntax_dict = YAML().load(yaml_file)
        operand_ctx = syntax_dict['contexts']['operand_label_definitions'][0]
        self.assertNotIn('##LABEL_PATTERN##', operand_ctx['match'])
        self.assertIn('(@)', operand_ctx['match'])
        self.assertIn(r'(\s*)', operand_ctx['match'])
        self.assertNotIn(r')\s*(:)', operand_ctx['match'])
        self.assertEqual(
            operand_ctx['captures'][1],
            'punctuation.definition.variable.at.operand-label',
        )
        self.assertEqual(
            operand_ctx['captures'][2],
            'variable.other.label.definition variable.other.label.definition.operand-label',
        )
        self.assertEqual(
            operand_ctx['captures'][3],
            'punctuation.definition.variable.colon.operand-label',
        )
        color_fp = os.path.join(sublime_tmp_dir, f'{sublime.language_name}.sublime-color-scheme')
        with open(color_fp) as json_file:
            color_json = json.load(json_file)
        sublime_scopes = {entry['scope'] for entry in color_json['rules']}
        self.assertIn('punctuation.definition.variable.at.operand-label', sublime_scopes)
        self.assertIn('variable.other.label.definition.operand-label', sublime_scopes)
        self.assertIn('punctuation.definition.variable.colon.operand-label', sublime_scopes)

        vim = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        vim.generate()
        vim_ft = vim.language_id.replace('-', '').lower()
        vim_syntax_fp = os.path.join(test_dir, 'syntax', f'{vim_ft}.vim')
        with open(vim_syntax_fp) as file:
            vim_text = file.read()
        self.assertIn(f'syn match {vim_ft}OperandLabelAt', vim_text)
        self.assertIn(f'syn match {vim_ft}OperandLabelName', vim_text)
        self.assertIn(f'syn match {vim_ft}OperandLabelColon', vim_text)
        self.assertRegex(vim_text, rf'hi\s+{re.escape(vim_ft)}OperandLabelAt\s+')
        self.assertRegex(vim_text, rf'hi\s+{re.escape(vim_ft)}OperandLabelName\s+')
        self.assertRegex(vim_text, rf'hi\s+{re.escape(vim_ft)}OperandLabelColon\s+')

        shutil.rmtree(sublime_tmp_dir)
        shutil.rmtree(test_dir)

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
            'bespokeasm-test-assembly',
            'package name should be based on language ID'
        )
        self.assertEqual(
            package_json['displayName'],
            f'{configgen.language_name} (BespokeASM)',
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
            package_json['main'],
            './extension.js',
            'extension entry point should be set'
        )
        hover_config = package_json['contributes']['configuration']['properties']
        hover_prefix = f'bespokeasm.{package_json["contributes"]["languages"][0]["id"]}.hover'
        self.assertIn(f'{hover_prefix}.mnemonics', hover_config)
        self.assertIn(f'{hover_prefix}.labels', hover_config)
        self.assertIn(f'{hover_prefix}.constants', hover_config)
        self.assertTrue(hover_config[f'{hover_prefix}.mnemonics']['default'])
        self.assertTrue(hover_config[f'{hover_prefix}.labels']['default'])
        self.assertTrue(hover_config[f'{hover_prefix}.constants']['default'])
        self.assertEqual(
            package_json['activationEvents'],
            ['onLanguage:bespokeasm-test-assembly'],
            'activation event should target the language'
        )
        self.assertIn('semanticTokenScopes', package_json['contributes'])
        self.assertEqual(
            package_json['contributes']['semanticTokenScopes'][0]['language'],
            'bespokeasm-test-assembly',
            'semantic token language should be updated'
        )
        token_scopes = package_json['contributes']['semanticTokenScopes'][0]['scopes']
        self.assertIn('constant', token_scopes)
        self.assertIn('constant.definition', token_scopes)
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
        instructions_patterns = grammar_json['repository']['instructions']['patterns']
        pattern_includes = [
            entry['include']
            for entry in instructions_patterns
            if isinstance(entry, dict) and 'include' in entry
        ]
        self.assertNotIn('#constant_usages', pattern_includes)
        self.assertNotIn('constant_usages', grammar_json['repository'])
        self.assertNotIn('#operands_variables', pattern_includes)

        # TODO: Remove label usage from TextMate grammar once semantic tokens handle constants.
        # This currently fails because label usage rules match constants in usage positions.
        self.assertNotIn('#label_usages', pattern_includes)
        self.assertEqual(
            grammar_json['repository']['operands_variables']['match'],
            '(?<!\\w)([A-Za-z][\\w\\d_]*)\\b',
            'operand variables should not match dot/underscore-prefixed labels'
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
        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'extension.js'))
        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'include_files.js'))
        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'label_hover.js'))
        self.assertIsFile(os.path.join(extension_dirpath, 'bespokeasm-test', 'constants_hover.js'))
        with open(os.path.join(extension_dirpath, 'bespokeasm-test', 'extension.js')) as js_file:
            js_content = js_file.read()
        self.assertIn('bespokeasm.openLabelDefinition', js_content)
        self.assertIn('bespokeasm.openConstantDefinition', js_content)
        self.assertIn('editor.action.goToLocations', js_content)
        self.assertIn('buildDefinitionHover', js_content)
        self.assertIn('1 << tokenModifiers.get(\'definition\')', js_content)
        self.assertIn('function getSemanticSearchRanges', js_content)
        self.assertIn('function isOffsetInCodeRegion', js_content)
        self.assertIn("if (ch === ';')", js_content)
        self.assertIn('if (!isOffsetInCodeRegion(lineText, range.start.character))', js_content)

        docs_fp = os.path.join(extension_dirpath, 'bespokeasm-test', 'instruction-docs.json')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as json_file:
            docs_json = json.load(json_file)
        self.assertIn('instructions', docs_json)
        self.assertIn('macros', docs_json)
        self.assertIn('predefined', docs_json)
        self.assertIn('constants', docs_json['predefined'])
        self.assertIn('data', docs_json['predefined'])
        self.assertIn('memory_zones', docs_json['predefined'])
        self.assertEqual({}, docs_json['predefined']['constants'])
        self.assertEqual({}, docs_json['predefined']['data'])
        self.assertEqual({}, docs_json['predefined']['memory_zones'])
        self.assertIn('LDA', docs_json['instructions'])
        self.assertIn('### `LDA`', docs_json['instructions']['LDA'])
        self.assertIn('Documentation not provided.', docs_json['instructions']['LDA'])

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
            'tester-assembly-assembly',
            'package name should be based on language ID'
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
            package_json['main'],
            './extension.js',
            'extension entry point should be set'
        )
        self.assertEqual(
            package_json['activationEvents'],
            ['onLanguage:tester-assembly-assembly'],
            'activation event should target the language'
        )
        self.assertIn('semanticTokenScopes', package_json['contributes'])
        self.assertEqual(
            package_json['contributes']['semanticTokenScopes'][0]['language'],
            'tester-assembly-assembly',
            'semantic token language should be updated'
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
        self.assertIsFile(os.path.join(extension_dirpath, 'tester-assembly', 'extension.js'))

        docs_fp = os.path.join(extension_dirpath, 'tester-assembly', 'instruction-docs.json')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as json_file:
            docs_json = json.load(json_file)
        self.assertIn('instructions', docs_json)
        self.assertIn('macros', docs_json)
        self.assertIn('predefined', docs_json)
        self.assertIn('constants', docs_json['predefined'])
        self.assertIn('data', docs_json['predefined'])
        self.assertIn('memory_zones', docs_json['predefined'])
        self.assertEqual({}, docs_json['predefined']['constants'])
        self.assertEqual({}, docs_json['predefined']['data'])
        self.assertEqual({}, docs_json['predefined']['memory_zones'])
        self.assertIn('NOP', docs_json['instructions'])
        self.assertIn('### `NOP`', docs_json['instructions']['NOP'])
        self.assertIn('Documentation not provided.', docs_json['instructions']['NOP'])

    def test_vscode_configgen_with_macros(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_macros.yaml')
        configgen = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )

        configgen.generate()

        extension_dirpath = os.path.join(str(test_dir), 'extensions')
        docs_fp = os.path.join(extension_dirpath, 'bespokeasm-test', 'instruction-docs.json')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as json_file:
            docs_json = json.load(json_file)

        self.assertIn('instructions', docs_json)
        self.assertIn('macros', docs_json)
        self.assertIn('predefined', docs_json)
        self.assertIn('constants', docs_json['predefined'])
        self.assertIn('data', docs_json['predefined'])
        self.assertIn('memory_zones', docs_json['predefined'])
        self.assertIn('PUSH2', docs_json['macros'])
        self.assertIn('### `PUSH2`', docs_json['macros']['PUSH2'])
        self.assertNotIn('Documentation not provided.', docs_json['macros']['PUSH2'])
        self.assertEqual({}, docs_json['predefined']['constants'])
        self.assertEqual({}, docs_json['predefined']['data'])
        self.assertEqual({}, docs_json['predefined']['memory_zones'])

        shutil.rmtree(test_dir)

    def test_configgen_predefined_hover_docs(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_predefined_hover_docs.yaml')

        vscode_configgen = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        vscode_configgen.generate()

        extension_dirpath = os.path.join(str(test_dir), 'extensions')
        docs_fp = os.path.join(extension_dirpath, 'predefined-hover-test', 'instruction-docs.json')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as json_file:
            docs_json = json.load(json_file)

        self.assertIn('predefined', docs_json)
        self.assertIn('VAR_BUF', docs_json['predefined']['constants'])
        self.assertIn('SCREEN', docs_json['predefined']['data'])
        self.assertIn('USER_RAM', docs_json['predefined']['memory_zones'])
        self.assertIn('### `VAR_BUF` : Predefined Constant', docs_json['predefined']['constants']['VAR_BUF'])
        self.assertIn('| **Size** | 2 words |', docs_json['predefined']['constants']['VAR_BUF'])
        self.assertIn('| **Size** | 4 words |', docs_json['predefined']['data']['SCREEN'])
        self.assertIn('### `USER_RAM` : User RAM', docs_json['predefined']['memory_zones']['USER_RAM'])

        sublime_tmp_dir = tempfile.mkdtemp()
        sublime_configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        sublime_configgen._generate_files_in_dir(sublime_tmp_dir)

        sublime_docs_fp = os.path.join(sublime_tmp_dir, 'instruction-docs.json')
        self.assertIsFile(sublime_docs_fp)
        with open(sublime_docs_fp) as json_file:
            sublime_docs_json = json.load(json_file)

        self.assertIn('VAR_BUF', sublime_docs_json['predefined']['constants'])
        self.assertIn('| **Size** | 2 words |', sublime_docs_json['predefined']['constants']['VAR_BUF'])
        self.assertIn('SCREEN', sublime_docs_json['predefined']['data'])
        self.assertIn('USER_RAM', sublime_docs_json['predefined']['memory_zones'])

        shutil.rmtree(sublime_tmp_dir)
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
                '\\.4byte', '\\.8byte', '\\.16byte', '\\.cstr', '\\.asciiz',
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
                'include', 'require', 'error', 'create_memzone', 'print', 'define', 'if',
                'elif', 'else', 'endif', 'ifdef', 'ifndef',
                'mute', 'unmute', 'emit',
                'create-scope', 'use-scope', 'deactivate-scope',
            ],
            'preprocessor directives'
        )
        self.assertIsFile(os.path.join(test_tmp_dir, 'bespokeasm-test.sublime-color-scheme'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'bespokeasm-test__cstr.sublime-snippet'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'bespokeasm-test__include.sublime-snippet'))
        hover_plugin = f"bespokeasm_hover_{re.sub(r'[^0-9A-Za-z_]', '_', 'bespokeasm-test')}.py"
        self.assertIsFile(os.path.join(test_tmp_dir, hover_plugin))
        settings_fp = os.path.join(test_tmp_dir, 'bespokeasm-test.sublime-settings')
        self.assertIsFile(settings_fp)
        with open(settings_fp) as settings_file:
            settings_json = json.load(settings_file)
        self.assertTrue(settings_json['hover']['mnemonics'])
        self.assertTrue(settings_json['hover']['labels'])
        self.assertTrue(settings_json['hover']['constants'])
        self.assertTrue(settings_json['semantic_highlighting'])
        expected_hover_colors = build_hover_color_map(DEFAULT_COLOR_SCHEME)
        hover_colors_fp = os.path.join(test_tmp_dir, 'hover-colors.json')
        self.assertIsFile(hover_colors_fp)
        with open(hover_colors_fp) as colors_file:
            colors_json = json.load(colors_file)
        self.assertDictEqual(expected_hover_colors, colors_json)
        hover_plugin_fp = os.path.join(test_tmp_dir, hover_plugin)
        with open(hover_plugin_fp) as hover_plugin_file:
            hover_plugin_content = hover_plugin_file.read()
        self.assertNotIn('##HOVER_COLOR_', hover_plugin_content)
        self.assertIn(expected_hover_colors['instruction'], hover_plugin_content)
        docs_fp = os.path.join(test_tmp_dir, 'instruction-docs.json')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as json_file:
            docs_json = json.load(json_file)
        self.assertIn('instructions', docs_json)
        self.assertIn('macros', docs_json)
        self.assertIn('predefined', docs_json)
        self.assertIn('constants', docs_json['predefined'])
        self.assertIn('data', docs_json['predefined'])
        self.assertIn('memory_zones', docs_json['predefined'])
        self.assertEqual({}, docs_json['predefined']['constants'])
        self.assertEqual({}, docs_json['predefined']['data'])
        self.assertEqual({}, docs_json['predefined']['memory_zones'])
        self.assertIn('LDA', docs_json['instructions'])
        self.assertIn('### `LDA`', docs_json['instructions']['LDA'])
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
                '\\.byte', '\\.2byte', '\\.4byte', '\\.8byte', '\\.16byte',
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
                'include', 'require', 'error', 'create_memzone', 'print', 'define',
                'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
                'mute', 'unmute', 'emit',
                'create-scope', 'use-scope', 'deactivate-scope',
            ],
            'preprocessor directives'
        )
        self.assertIsFile(os.path.join(test_tmp_dir, 'tester-assembly.sublime-color-scheme'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'tester-assembly__cstr.sublime-snippet'))
        self.assertIsFile(os.path.join(test_tmp_dir, 'tester-assembly__include.sublime-snippet'))
        hover_plugin = f"bespokeasm_hover_{re.sub(r'[^0-9A-Za-z_]', '_', 'tester-assembly')}.py"
        self.assertIsFile(os.path.join(test_tmp_dir, hover_plugin))
        settings_fp = os.path.join(test_tmp_dir, 'tester-assembly.sublime-settings')
        self.assertIsFile(settings_fp)
        with open(settings_fp) as settings_file:
            settings_json = json.load(settings_file)
        self.assertTrue(settings_json['hover']['mnemonics'])
        self.assertTrue(settings_json['hover']['labels'])
        self.assertTrue(settings_json['hover']['constants'])
        self.assertTrue(settings_json['semantic_highlighting'])
        expected_hover_colors = build_hover_color_map(DEFAULT_COLOR_SCHEME)
        hover_colors_fp = os.path.join(test_tmp_dir, 'hover-colors.json')
        self.assertIsFile(hover_colors_fp)
        with open(hover_colors_fp) as colors_file:
            colors_json = json.load(colors_file)
        self.assertDictEqual(expected_hover_colors, colors_json)
        hover_plugin_fp = os.path.join(test_tmp_dir, hover_plugin)
        with open(hover_plugin_fp) as hover_plugin_file:
            hover_plugin_content = hover_plugin_file.read()
        self.assertNotIn('##HOVER_COLOR_', hover_plugin_content)
        self.assertIn(expected_hover_colors['instruction'], hover_plugin_content)
        docs_fp = os.path.join(test_tmp_dir, 'instruction-docs.json')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as json_file:
            docs_json = json.load(json_file)
        self.assertIn('instructions', docs_json)
        self.assertIn('macros', docs_json)
        self.assertIn('predefined', docs_json)
        self.assertIn('constants', docs_json['predefined'])
        self.assertIn('data', docs_json['predefined'])
        self.assertIn('memory_zones', docs_json['predefined'])
        self.assertEqual({}, docs_json['predefined']['constants'])
        self.assertEqual({}, docs_json['predefined']['data'])
        self.assertEqual({}, docs_json['predefined']['memory_zones'])
        self.assertIn('NOP', docs_json['instructions'])
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
        self._assert_vim_contextual_syntax(syn, vim_ft)
        # The instruction region should contain an escaped version of 'ma.hl' from the test config.
        self.assertRegex(
            syn,
            r'syn\s+region\s+\w+InstrLine\s+matchgroup=\w+Instruction\s+start=/.+ma\\\.hl.+/',
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
        self._assert_vim_contextual_syntax(syn, vim_ft)
        # Instructions present (syn region alternation with word boundaries)
        m = re.search(
            rf'^syn\s+region\s+{re.escape(vim_ft)}InstrLine\s+'
            rf'matchgroup={re.escape(vim_ft)}Instruction\s+start=/(.+?)/\s+end=',
            syn,
            re.MULTILINE,
        )
        self.assertIsNotNone(m, 'Instruction region line should exist')
        pat = m.group(1)
        # Extract the alternation group between \%( ... ) without using nested-regex
        start = pat.find(r'\%(')
        end = pat.rfind(r'\)')
        self.assertTrue(start >= 0 and end > start, 'Instruction pattern should contain alternation group')
        group = pat[start+3:end]
        for mnemonic in ['lda', 'add', 'set', 'big', 'hlt']:
            self.assertRegex(group, rf'(?:^|\\\|){re.escape(mnemonic)}(?:\\\||$)')
        # No macros
        self.assertNotRegex(syn, rf'(?m)^syn\s+region\s+{re.escape(vim_ft)}MacroLine\b', 'No macros expected')
        # No registers
        self.assertIsNone(
            re.search(rf'^syn\s+keyword\s+{re.escape(vim_ft)}Register\b', syn, re.MULTILINE),
            'No registers expected',
        )
        # Directives
        self.assertIn(
            f'syn region {vim_ft}DirectiveLine matchgroup={vim_ft}Directive start=/\\s*\\.org\\>/',
            syn,
        )
        self.assertIn(
            f'syn region {vim_ft}DirectiveLine matchgroup={vim_ft}Directive start=/\\s*\\.memzone\\>/',
            syn,
        )
        self.assertIn(
            f'syn region {vim_ft}DirectiveLine matchgroup={vim_ft}Directive start=/\\s*\\.align\\>/',
            syn,
        )
        # Data types
        for dt in ['fill', 'zero', 'zerountil', 'byte', '2byte', '4byte', '8byte', '16byte', 'cstr', 'asciiz']:
            self.assertIn(
                f'syn region {vim_ft}DataTypeLine matchgroup={vim_ft}DataType start=/\\s*\\.{dt}\\>/',
                syn,
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
        self._assert_vim_contextual_syntax(syn, vim_ft)
        # Registers present
        m = re.search(rf'^syn\s+keyword\s+{re.escape(vim_ft)}Register\s+(.+)$', syn, re.MULTILINE)
        self.assertIsNotNone(m, 'Register keyword line should exist')
        regs = set(m.group(1).split())
        self.assertTrue({'a', 'j', 'i', 'h', 'l', 'hl', 'sp', 'mar'}.issubset(regs))
        # Instructions present
        m = re.search(
            rf'^syn\s+region\s+{re.escape(vim_ft)}InstrLine\s+'
            rf'matchgroup={re.escape(vim_ft)}Instruction\s+start=/(.+?)/\s+end=',
            syn,
            re.MULTILINE,
        )
        self.assertIsNotNone(m, 'Instruction region line should exist')
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
        self._assert_vim_contextual_syntax(syn, vim_ft)
        m = re.search(
            rf'^syn\s+region\s+{re.escape(vim_ft)}InstrLine\s+'
            rf'matchgroup={re.escape(vim_ft)}Instruction\s+start=/(.+?)/\s+end=',
            syn,
            re.MULTILINE,
        )
        self.assertIsNotNone(m, 'Instruction region line should exist')
        pat = m.group(1)
        start = pat.find(r'\%(')
        end = pat.rfind(r'\)')
        self.assertTrue(start >= 0 and end > start, 'Instruction pattern should contain alternation group')
        group = pat[start+3:end]
        for mnemonic in ['jsr', 'call', 'jsr2', 'call2', 'jump_to_subroutine', 'nop']:
            self.assertRegex(group, rf'(?:^|\\\|){re.escape(mnemonic)}(?:\\\||$)')
        shutil.rmtree(test_dir)

    def test_vim_instruction_region_ends_before_next_same_line_instruction(self):
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

        region_line = next(
            line for line in syn.splitlines()
            if line.startswith(f'syn region {vim_ft}InstrLine ')
        )
        self.assertIn(r'end=/\s*\ze\<', region_line)
        self.assertIn(r'\|\s*\ze;\|$/ oneline', region_line)
        for mnemonic in ['lda', 'add', 'set', 'big', 'hlt']:
            self.assertIn(mnemonic, region_line)

        start_index = region_line.index('start=/')
        end_index = region_line.index(' end=/')
        self.assertLess(start_index, end_index)
        shutil.rmtree(test_dir)

    def test_vim_ftplugin_generated(self):
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
        ftplugin_fp = os.path.join(str(test_dir), 'ftplugin', f'{vim_ft}.vim')
        self.assertIsFile(ftplugin_fp)
        with open(ftplugin_fp) as f:
            ftplugin = f.read()

        self.assertIn(f'if exists("b:did_{vim_ft}_ftplugin") | finish | endif', ftplugin)
        self.assertIn(f'augroup bespokeasm_{vim_ft}', ftplugin)
        self.assertIn('autocmd! * <buffer>', ftplugin)
        self.assertIn(f'autocmd bespokeasm_{vim_ft} BufReadPost <buffer>', ftplugin)
        self.assertIn(f'autocmd bespokeasm_{vim_ft} BufWritePost <buffer>', ftplugin)
        self.assertIn(f'autocmd bespokeasm_{vim_ft} CursorHold <buffer>', ftplugin)
        self.assertIn(f'setlocal keywordprg=:call\\ {vim_ft}_docs#Show', ftplugin)
        self.assertIn(f'g:bespokeasm_{vim_ft}_max_scan_lines = 10000', ftplugin)
        self.assertIn(f'call s:RefreshLabelsGuarded_{vim_ft}()', ftplugin)
        self.assertIn(f'silent! syntax clear {vim_ft}LabelUsage', ftplugin)
        self.assertIn(r'\%(@\)\@<=\<\%(', ftplugin)
        self.assertNotIn(' \\\n', ftplugin)
        self.assertIn(
            f"autocmd bespokeasm_{vim_ft} CursorHold <buffer> call {vim_ft}_docs#PopupAtCursor(expand('<cword>'))",
            ftplugin,
        )
        self.assertIn('Cross-file label resolution is not supported.', ftplugin)
        shutil.rmtree(test_dir)

    def test_vim_autoload_docs_generated(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_compiler_features.yaml')
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
        docs_fp = os.path.join(str(test_dir), 'autoload', f'{vim_ft}_docs.vim')
        self.assertIsFile(docs_fp)
        with open(docs_fp) as f:
            docs = f.read()

        self.assertIn('let s:docs = {', docs)
        self.assertIn(f'function! {vim_ft}_docs#Show(word) abort', docs)
        self.assertIn(f'function! {vim_ft}_docs#PopupAtCursor(word) abort', docs)
        self.assertIn('"ld": "', docs)
        self.assertIn('"a": "', docs)
        self.assertIn('".org": "', docs)
        for line in docs.splitlines():
            if not line.startswith('\\   "'):
                continue
            self.assertRegex(line, r'^\\   "(?:[^"\\]|\\.)+": "(?:[^"\\]|\\.)*",$')
            self.assertNotRegex(line, r'(?<!\\)\\",$')
        shutil.rmtree(test_dir)

    def test_vim_digit_leading_filetype_is_sanitized(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_line_creation_little_endian.yaml')
        configgen = VimConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            '6502-asm',
            None,
            'asmtest',
        )
        configgen.generate()
        vim_ft = '_6502asmassembly'

        for subdir, filename in [
            ('syntax', f'{vim_ft}.vim'),
            ('ftdetect', f'{vim_ft}.vim'),
            ('ftplugin', f'{vim_ft}.vim'),
            ('autoload', f'{vim_ft}_docs.vim'),
        ]:
            self.assertIsFile(os.path.join(str(test_dir), subdir, filename))

        docs_fp = os.path.join(str(test_dir), 'autoload', f'{vim_ft}_docs.vim')
        with open(docs_fp) as f:
            docs = f.read()
        self.assertFalse(vim_ft[0].isdigit())
        self.assertIn(f'function! {vim_ft}_docs#Show(word) abort', docs)
        self.assertIn(f'function! {vim_ft}_docs#PopupAtCursor(word) abort', docs)
        shutil.rmtree(test_dir)

    def test_vim_syntax_includes_label_usage(self):
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

        self._assert_vim_contextual_syntax(syn, vim_ft)
        self.assertNotRegex(syn, rf'(?m)^syn\s+match\s+{re.escape(vim_ft)}LabelUsage\b')
        self.assertIn(f'hi def link {vim_ft}LabelUsage Identifier', syn)
        self.assertRegex(syn, rf'(?m)^hi\s+{re.escape(vim_ft)}LabelUsage\s+guifg=')
        shutil.rmtree(test_dir)

    def test_vim_string_escape_round_trips_docs(self):
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
        value = 'quote " backslash \\ newline\ncarriage\rend'
        escaped = configgen._vim_string_escape(value)

        def decode_vim_double_quoted_string(text):
            result = []
            index = 0
            while index < len(text):
                char = text[index]
                if char == '\\' and index + 1 < len(text):
                    next_char = text[index + 1]
                    if next_char == 'n':
                        result.append('\n')
                    elif next_char == 'r':
                        result.append('\r')
                    else:
                        result.append(next_char)
                    index += 2
                    continue
                result.append(char)
                index += 1
            return ''.join(result)

        self.assertEqual(decode_vim_double_quoted_string(escaped), value)
        self.assertIn(r'\"', escaped)
        self.assertIn(r'\\', escaped)
        self.assertIn(r'\n', escaped)
        self.assertIn(r'\r', escaped)
        shutil.rmtree(test_dir)

    def test_vim_configgen_with_macros(self):
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_macros.yaml')
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
        self._assert_vim_contextual_syntax(syn, vim_ft)
        m = re.search(
            rf'^syn\s+region\s+{re.escape(vim_ft)}MacroLine\s+'
            rf'matchgroup={re.escape(vim_ft)}Macro\s+start=/(.+?)/\s+end=',
            syn,
            re.MULTILINE,
        )
        self.assertIsNotNone(m, 'Macro region line should exist')
        self.assertIn('push2', m.group(1))
        shutil.rmtree(test_dir)

    def test_vim_instruction_and_macro_regions_end_on_either_mnemonic(self):
        """A line with a mix of instructions and macros: each region must end before
        the next operation mnemonic regardless of whether it's an instruction or a macro."""
        test_dir = tempfile.mkdtemp()
        config_file = pkg_resources.files(config_files).joinpath('test_instruction_macros.yaml')
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

        instr_line = next(
            line for line in syn.splitlines()
            if line.startswith(f'syn region {vim_ft}InstrLine ')
        )
        macro_line = next(
            line for line in syn.splitlines()
            if line.startswith(f'syn region {vim_ft}MacroLine ')
        )

        instructions = ['push', 'pop', 'mov', 'add', 'addc', 'ldar']
        macros = ['push2', 'mov2', 'add16', 'swap', 'incs']

        for region_line, region_name in ((instr_line, 'InstrLine'), (macro_line, 'MacroLine')):
            end_match = re.search(r' end=/(.+?)/ oneline ', region_line)
            self.assertIsNotNone(end_match, f'{region_name} should have an end= pattern')
            end_pat = end_match.group(1)
            self.assertTrue(
                end_pat.startswith(r'\s*\ze\<'),
                f'{region_name} end pattern should start with operation-mnemonic terminator, got: {end_pat}',
            )
            self.assertIn(r'\|\s*\ze;\|$', end_pat, f'{region_name} should also terminate on ; or EOL')
            for mnemonic in instructions + macros:
                self.assertRegex(
                    end_pat,
                    rf'(?:\\%\(|\\\|){re.escape(mnemonic)}(?:\\\||\\\))',
                    f'{region_name} end pattern should terminate before {mnemonic!r}',
                )
        shutil.rmtree(test_dir)

    def test_vim_background_foreground_colors(self):
        """Test that VIM syntax generator does not override editor-level colors."""
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

        self._assert_vim_contextual_syntax(syn, vim_ft)

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

    def test_constant_definition_hover_patterns(self):
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
        configgen.generate()
        constants_fp = os.path.join(
            str(test_dir),
            'extensions',
            'bespokeasm-test',
            'constants_hover.js',
        )
        self.assertIsFile(constants_fp)
        with open(constants_fp) as js_file:
            js_content = js_file.read()
        js_match = re.search(r'line\.match\(/(.+?)/\)', js_content)
        self.assertIsNotNone(js_match, 'constants hover regex should be present')
        self._assert_constant_definition_pattern(
            js_match.group(1),
            'vscode constants_hover.js',
        )
        shutil.rmtree(test_dir)

        test_destination_dir = tempfile.mkdtemp()
        test_tmp_dir = tempfile.mkdtemp()
        configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_destination_dir),
            None,
            None,
            'asmtest',
        )
        configgen._generate_files_in_dir(test_tmp_dir)
        hover_plugin = f"bespokeasm_hover_{re.sub(r'[^0-9A-Za-z_]', '_', 'bespokeasm-test')}.py"
        hover_fp = os.path.join(test_tmp_dir, hover_plugin)
        self.assertIsFile(hover_fp)
        with open(hover_fp) as hover_file:
            hover_content = hover_file.read()
        sublime_match = re.search(
            r'CONSTANT_DEFINITION_PATTERN\s*=\s*re\.compile\(r\'([^\']+)\'\)',
            hover_content,
        )
        self.assertIsNotNone(sublime_match, 'sublime hover regex should be present')
        self._assert_constant_definition_pattern(
            sublime_match.group(1),
            'sublime hover plugin',
        )
        shutil.rmtree(test_tmp_dir)
        shutil.rmtree(test_destination_dir)

    def test_hover_mnemonic_pattern_matches_dotted_instruction(self):
        config_file = (
            pl.Path(__file__).resolve().parent.parent
            / 'examples'
            / 'slu4-minimal-64x4'
            / 'slu4-minimal-64x4.yaml'
        )
        test_dir = tempfile.mkdtemp()
        configgen = VSCodeConfigGenerator(
            str(config_file),
            0,
            str(test_dir),
            None,
            None,
            'asmtest',
        )
        configgen.generate()
        extension_fp = os.path.join(
            str(test_dir),
            'extensions',
            'slu4-min64x4-asm',
            'extension.js',
        )
        self.assertIsFile(extension_fp)
        with open(extension_fp) as js_file:
            js_content = js_file.read()
        js_match = re.search(r'const wordPattern = /(.+?)/i;', js_content)
        self.assertIsNotNone(js_match, 'wordPattern should be present in extension.js')
        vscode_word_pattern = re.compile(js_match.group(1), re.IGNORECASE)
        match = vscode_word_pattern.search('  AN.Z $10')
        self.assertIsNotNone(match, 'VSCode wordPattern should match dotted mnemonic')
        self.assertEqual(match.group(0), 'AN.Z')
        shutil.rmtree(test_dir)

        test_destination_dir = tempfile.mkdtemp()
        test_tmp_dir = tempfile.mkdtemp()
        configgen = SublimeConfigGenerator(
            str(config_file),
            0,
            str(test_destination_dir),
            None,
            None,
            'asmtest',
        )
        configgen._generate_files_in_dir(test_tmp_dir)
        hover_plugin = f"bespokeasm_hover_{re.sub(r'[^0-9A-Za-z_]', '_', 'slu4-min64x4-asm')}.py"
        hover_fp = os.path.join(test_tmp_dir, hover_plugin)
        self.assertIsFile(hover_fp)
        with open(hover_fp) as hover_file:
            hover_content = hover_file.read()
        sublime_match = re.search(
            r'WORD_PATTERN\s*=\s*re\.compile\(r\'([^\']+)\'',
            hover_content,
        )
        self.assertIsNotNone(sublime_match, 'WORD_PATTERN should be present in hover plugin')
        sublime_word_pattern = re.compile(sublime_match.group(1), re.IGNORECASE)
        match = sublime_word_pattern.search('  AN.Z $10')
        self.assertIsNotNone(match, 'Sublime wordPattern should match dotted mnemonic')
        self.assertEqual(match.group(0), 'AN.Z')
        shutil.rmtree(test_tmp_dir)
        shutil.rmtree(test_destination_dir)

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
