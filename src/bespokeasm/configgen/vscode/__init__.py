import importlib.resources as pkg_resources
import json
import os
import shutil
from pathlib import Path

import bespokeasm.configgen.vscode.resources as resources
from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import EXPRESSION_FUNCTIONS_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.configgen import LanguageConfigGenerator
from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
from bespokeasm.configgen.color_scheme import SyntaxElement


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
        super().__init__(config_file_path, is_verbose, vscode_config_dir, language_name,  language_version, code_extension)

    def _generate_vscode_color_rules(self) -> list:
        """
        Generate VS Code color rules by mapping generic syntax elements
        to VS Code-specific TextMate scopes.

        Returns:
            List of color rule dictionaries for VS Code tmTheme format
        """
        # Mapping from generic syntax elements to VS Code TextMate scopes
        scope_mappings = [
            (SyntaxElement.HEX_NUMBER, 'constant.numeric.integer.hexadecimal', 'Numbers - Hex'),
            (SyntaxElement.BINARY_NUMBER, 'constant.numeric.integer.binary', 'Numbers - Binary'),
            (SyntaxElement.DECIMAL_NUMBER, 'constant.numeric.integer.decimal', 'Numbers - Decimal'),
            (SyntaxElement.CHARACTER_NUMBER, 'constant.numeric.character', 'Numbers - Character'),
            (SyntaxElement.LABEL_NAME, 'variable.other.label', 'Labels'),
            (SyntaxElement.PUNCTUATION_STRING, 'punctuation.definition.string', 'String Punctuation'),
            (SyntaxElement.STRING, 'string.quoted', 'Strings'),
            (SyntaxElement.STRING_ESCAPE, 'constant.character.escape', 'Strings - Escaped Characters'),
            (SyntaxElement.COMMENT, 'comment.line', 'Comments'),
            (SyntaxElement.PARAMETER, 'variable.parameter', 'Parameters'),
            (SyntaxElement.INSTRUCTION, 'variable.function.instruction', 'Functions - Instruction'),
            (SyntaxElement.MACRO, 'variable.function.macro', 'Functions - Macro'),
            (SyntaxElement.REGISTER, 'variable.language', 'Variables - Language'),
            (SyntaxElement.CONSTANT_NAME, 'variable.other.constant', 'Variables - Constant'),
            (SyntaxElement.COMPILER_LABEL, 'constant.language', 'Variables - Language Defined'),
            (SyntaxElement.PREPROCESSOR, 'keyword.control.preprocessor', 'Keyword - Preprocessor'),
            (SyntaxElement.DATA_TYPE, 'storage.type', 'Data Types'),
            (SyntaxElement.OPERATOR, 'keyword.operator', 'Keyword - Operators'),
            (SyntaxElement.DIRECTIVE, 'keyword.other', 'Keyword - Other'),
            (SyntaxElement.PUNCTUATION_PREPROCESSOR, 'punctuation.definition.preprocessor', 'Punctuation - Preprocessor'),
            (SyntaxElement.PUNCTUATION_SEPARATOR, 'punctuation.separator', 'Punctuation - Separator'),
            (SyntaxElement.PUNCTUATION_VARIABLE, 'punctuation.definition.variable', 'Punctuation - Variable'),
        ]

        rules = []

        # Generate standard rules
        for syntax_element, scope, name in scope_mappings:
            hex_color = DEFAULT_COLOR_SCHEME.get_color(syntax_element)
            rules.append({
                'name': name,
                'scope': scope,
                'settings': {'foreground': hex_color}
            })

        # Special rules with additional styling
        bracket_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BRACKET)
        rules.append({
            'name': 'Punctuation - Addressing Brackets',
            'scope': 'punctuation.section.brackets',
            'settings': {
                'foreground': bracket_color,
                'font_style': 'bold'
            }
        })

        double_bracket_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.DOUBLE_BRACKET)
        rules.append({
            'name': 'Punctuation - Addressing Double Brackets',
            'scope': 'punctuation.section.double_brackets',
            'settings': {
                'foreground': double_bracket_color,
                'font_style': 'bold'
            }
        })

        paren_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.PARENTHESIS)
        rules.append({
            'name': 'Punctuation - Parenthesis',
            'scope': 'punctuation.section.parens',
            'settings': {'foreground': paren_color}
        })

        return rules

    def _generate_tmtheme_xml(self, language_id: str) -> str:
        """Generate tmTheme XML content by mapping generic syntax elements to VS Code scopes."""
        color_rules = self._generate_vscode_color_rules()

        # Build the XML structure
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            '<dict>',
            '    <key>name</key>',
            f'    <string>{language_id} Color Scheme</string>',
            '    <key>settings</key>',
            '    <array>',
            '        <!-- Global settings -->',
            '        <dict>',
            '            <key>settings</key>',
            '            <dict>',
            '                <key>background</key>',
            f'                <string>{DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BACKGROUND)}</string>',
            '                <key>foreground</key>',
            f'                <string>{DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.FOREGROUND)}</string>',
            '                <key>caret</key>',
            f'                <string>{DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.CARET)}</string>',
            '            </dict>',
            '        </dict>',
            '        <!-- Scope styles -->'
        ]

        # Add each color rule
        for rule in color_rules:
            xml_parts.extend([
                '        <dict>',
                '            <key>name</key>',
                f'            <string>{rule["name"]}</string>',
                '            <key>scope</key>',
                f'            <string>{rule["scope"]}</string>',
                '            <key>settings</key>',
                '            <dict>',
                '                <key>foreground</key>',
                f'                <string>{rule["settings"]["foreground"]}</string>'
            ])

            # Add font style if present
            if 'font_style' in rule['settings']:
                xml_parts.extend([
                    '                <key>font_style</key>',
                    f'                <string>{rule["settings"]["font_style"]}</string>'
                ])

            xml_parts.extend([
                '            </dict>',
                '        </dict>'
            ])

        xml_parts.extend([
            '    </array>',
            '</dict>',
            '</plist>'
        ])

        return '\n'.join(xml_parts)

    def generate(self) -> None:
        extension_name = self.language_name
        extension_dir_path = os.path.join(self.export_dir, 'extensions', extension_name)

        if self.verbose >= 1:
            print(f'Generating Visual Studio Code extension for language "{self.language_id}" at: {extension_dir_path}')

        # create the extensions directory if it doesn't exist
        Path(extension_dir_path).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(extension_dir_path, 'syntaxes')).mkdir(parents=True, exist_ok=True)
        # generate package.json
        fp = pkg_resources.files(resources).joinpath('package.json')
        with open(fp) as json_file:
            package_json = json.load(json_file)

        scope_name = 'source.' + self.language_id
        theme_filename = self.language_id + '.tmTheme'
        package_json['name'] = self.language_name
        package_json['displayName'] = self.model.description
        package_json['version'] = self.language_version
        package_json['contributes']['languages'][0]['id'] = self.language_id
        package_json['contributes']['languages'][0]['extensions'] = ['.'+self.code_extension]
        package_json['contributes']['grammars'][0]['language'] = self.language_id
        package_json['contributes']['grammars'][0]['scopeName'] = scope_name
        package_json['contributes']['snippets'][0]['language'] = self.language_id
        package_json['contributes']['themes'][0]['label'] = \
            package_json['contributes']['themes'][0]['label'].replace('##LANGUAGE_ID##', self.language_name)
        package_json['contributes']['themes'][0]['path'] = './' + theme_filename

        package_fp = os.path.join(extension_dir_path, 'package.json')
        with open(package_fp, 'w', encoding='utf-8') as f:
            json.dump(package_json, f, ensure_ascii=False, indent=4)
            if self.verbose > 1:
                print('  generated package.json')

        # generate tmGrammar.json
        fp = pkg_resources.files(resources).joinpath('tmGrammar.json')
        with open(fp) as json_file:
            grammar_json = json.load(json_file)

        grammar_json['scopeName'] = scope_name
        # handle instructions
        grammar_json['repository']['instructions']['begin'] = self._replace_token_with_regex_list(
            grammar_json['repository']['instructions']['begin'],
            '##INSTRUCTIONS##',
            self.model.instruction_mnemonics
        )
        grammar_json['repository']['instructions']['end'] = self._replace_token_with_regex_list(
            grammar_json['repository']['instructions']['end'],
            '##OPERATIONS##',
            self.model.operation_mnemonics
        )
        if len(self.model.macro_mnemonics) > 0:
            grammar_json['repository']['macros']['begin'] = self._replace_token_with_regex_list(
                grammar_json['repository']['macros']['begin'],
                '##MACROS##',
                self.model.macro_mnemonics
            )
            grammar_json['repository']['macros']['end'] = self._replace_token_with_regex_list(
                grammar_json['repository']['macros']['end'],
                '##OPERATIONS##',
                self.model.operation_mnemonics
            )
        else:
            del grammar_json['repository']['macros']
            for idx, pattern_item in enumerate(grammar_json['repository']['main']['patterns']):
                if pattern_item['include'] == '#macros':
                    grammar_json['repository']['main']['patterns'].remove(pattern_item)
                    break

        # handle registers
        if len(self.model.registers) > 0:
            if self.verbose > 2:
                print(f'  adding syntax for a total of {len(self.model.registers)} registers')
            # update the registers syntax
            grammar_json['repository']['registers']['match'] = self._replace_token_with_regex_list(
                grammar_json['repository']['registers']['match'],
                '##REGISTERS##',
                self.model.registers
            )
        else:
            # remove the registers syntax
            del grammar_json['repository']['registers']

        # handled predefined labels
        predefined_labels = self.model.predefined_labels
        if len(predefined_labels) > 0:
            if self.verbose > 2:
                print(f'  adding syntax for a total of {len(predefined_labels)} predefined labels')
            # update the registers syntax
            grammar_json['repository']['compiler_labels']['match'] = self._replace_token_with_regex_list(
                grammar_json['repository']['compiler_labels']['match'],
                '##COMPILERCONSTANTS##',
                predefined_labels
            )
        else:
            # remove the registers syntax
            del grammar_json['repository']['compiler_labels']

        # handle bespokeasm directives
        for item in grammar_json['repository']['directives']['patterns']:
            if 'meta.directive' == item['name']:
                directives_regex = '|'.join(['\\.'+d for d in COMPILER_DIRECTIVES_SET])
                directives_str = item['begin']
                item['begin'] = directives_str.replace('##DIRECTIVES##', directives_regex)
            elif 'storage.type' == item['name']:
                datatypes_regex = '|'.join(['\\.'+d for d in BYTECODE_DIRECTIVES_SET])
                datatypes_str = item['match']
                item['match'] = datatypes_str.replace('##DATATYPES##', datatypes_regex)
            elif 'meta.preprocessor' == item['name']:
                for pattern in item['patterns']:
                    if 'name' in pattern and 'keyword.control.preprocessor' == pattern['name']:
                        # Sort by length (desc) to avoid prefix matches like 'if' matching 'ifdef'
                        preprocessor_regex = '|'.join(sorted(PREPROCESSOR_DIRECTIVES_SET, key=len, reverse=True))
                        preprocesspr_str = pattern['match']
                        pattern['match'] = preprocesspr_str.replace('##PREPROCESSOR##', preprocessor_regex)

        # handle expresion functions
        for item in grammar_json['repository']['operators']['patterns']:
            if 'keyword.operator.word' == item['name']:
                func_regex = '|'.join([d for d in EXPRESSION_FUNCTIONS_SET])
                func_str = item['match']
                item['match'] = func_str.replace('##EXPRESSION_FUNCTIONS##', func_regex)

        tmGrammar_fp = os.path.join(extension_dir_path, 'syntaxes', 'tmGrammar.json')
        with open(tmGrammar_fp, 'w', encoding='utf-8') as f:
            json.dump(grammar_json, f, ensure_ascii=False, indent=4)
            if self.verbose > 1:
                print(f'  generated {os.path.basename(tmGrammar_fp)}')

        # copy snippets.json and lanaguage-configuration.json, nothing to modify
        fp = pkg_resources.files(resources).joinpath('snippets.json')
        shutil.copy(str(fp), extension_dir_path)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(str(fp))}')

        fp = pkg_resources.files(resources).joinpath('language-configuration.json')
        shutil.copy(str(fp), extension_dir_path)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(str(fp))}')

        # Generate theme file from central color configuration
        color_theme_xml = self._generate_tmtheme_xml(self.language_id)
        with open(os.path.join(extension_dir_path, theme_filename), 'w') as theme_file:
            theme_file.write(color_theme_xml)
            if self.verbose > 1:
                print(f'  generated {theme_filename}')
