import importlib.resources as pkg_resources
import json
import os
import re
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
from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
from bespokeasm.configgen.color_scheme import SyntaxElement
from bespokeasm.docsgen import build_documentation_model
from bespokeasm.docsgen.markdown_generator import MarkdownGenerator
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

    def _generate_sublime_color_rules(self) -> list:
        """
        Generate Sublime Text color rules by mapping generic syntax elements
        to Sublime-specific TextMate scopes.

        Returns:
            List of color rule dictionaries for Sublime Text
        """
        # Mapping from generic syntax elements to Sublime TextMate scopes
        scope_mappings = [
            (SyntaxElement.HEX_NUMBER, 'constant.numeric.integer.hexadecimal', 'Numbers - Hex'),
            (SyntaxElement.BINARY_NUMBER, 'constant.numeric.integer.binary', 'Numbers - Binary'),
            (SyntaxElement.DECIMAL_NUMBER, 'constant.numeric.integer.decimal', 'Numbers - Decimal'),
            (SyntaxElement.CHARACTER_NUMBER, 'constant.numeric.character', 'Numbers - Character'),
            (SyntaxElement.LABEL_DEFINITION, 'variable.other.label.definition', 'Labels - Definitions'),
            # (SyntaxElement.LABEL_USAGE, 'variable.other.label.usage', 'Labels - Usages'),
            (SyntaxElement.LABEL_NAME, 'variable.other.label', 'Labels'),
            (SyntaxElement.PUNCTUATION_STRING, 'punctuation.definition.string', 'String Punctuation'),
            (SyntaxElement.STRING, 'string.quoted', 'Strings'),
            (SyntaxElement.STRING_ESCAPE, 'constant.character.escape', 'Strings - Escaped Characters'),
            (SyntaxElement.COMMENT, 'comment.line', 'Comments'),
            (SyntaxElement.PARAMETER, 'variable.parameter', 'Parameters'),
            (SyntaxElement.INSTRUCTION, 'variable.function.instruction', 'Instruction Functions'),
            (SyntaxElement.MACRO, 'variable.function.macro', 'Macro Functions'),
            (SyntaxElement.REGISTER, 'variable.language', 'Variables - Language'),
            (SyntaxElement.CONSTANT_DEFINITION, 'variable.other.constant.definition', 'Constants - Definitions'),
            # (SyntaxElement.CONSTANT_USAGE, 'variable.other.constant.usage', 'Constants - Usages'),
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
                'foreground': hex_color,
                'name': name,
                'scope': scope
            })

        # Special rules with additional styling
        label_usage_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.LABEL_USAGE)
        rules.append({
            'foreground': label_usage_color,
            'name': 'Labels - Usages',
            'scope': 'variable.other.label.usage',
            'background': f'color({label_usage_color} alpha(0.05))',
        })

        constant_usage_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.CONSTANT_USAGE)
        rules.append({
            'foreground': constant_usage_color,
            'name': 'Constants - Usages',
            'scope': 'variable.other.constant.usage',
            'background': f'color({constant_usage_color} alpha(0.05))',
        })

        bracket_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BRACKET)
        rules.append({
            'font_style': 'bold',
            'foreground': bracket_color,
            'name': 'Punctuation - Addressing Brackets',
            'scope': 'punctuation.section.brackets'
        })

        double_bracket_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.DOUBLE_BRACKET)
        rules.append({
            'font_style': 'bold',
            'foreground': double_bracket_color,
            'name': 'Punctuation - Addressing Double Brackets',
            'scope': 'punctuation.section.double_brackets'
        })

        paren_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.PARENTHESIS)
        rules.append({
            'foreground': paren_color,
            'name': 'Punctuation - Parenthesis',
            'scope': 'punctuation.section.parens'
        })

        return rules

    def _hover_plugin_filename(self) -> str:
        safe_name = re.sub(r'[^0-9A-Za-z_]', '_', self.language_name or 'bespokeasm')
        return f'bespokeasm_hover_{safe_name}.py'

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

        # handle compiler predefined labels and built-in constants
        from bespokeasm.assembler.keywords import BUILTIN_CONSTANTS_SET
        predefined_labels = self.model.predefined_labels
        all_constants = list(predefined_labels) + list(BUILTIN_CONSTANTS_SET)
        if len(all_constants) > 0:
            if self.verbose > 2:
                print(f'  adding syntax for a total of {len(all_constants)} predefined labels and built-in constants')
            # update the compiler constants syntax
            syntax_dict['contexts']['compiler_labels'][0]['match'] = self._replace_token_with_regex_list(
                syntax_dict['contexts']['compiler_labels'][0]['match'],
                '##COMPILERCONSTANTS##',
                all_constants,
            )
        else:
            # remove the compiler constants syntax
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

        # generate color scheme file from central configuration
        color_scheme_fp = os.path.join(destination_dir, self.language_name + '.sublime-color-scheme')
        color_scheme_data = {
            'globals': {
                'background': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BACKGROUND),
                'caret': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.CARET),
                'foreground': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.FOREGROUND),
                'line_highlight': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.LINE_HIGHLIGHT),
                'selection': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.SELECTION)
            },
            'name': 'BespokeASM Color Scheme',
            'rules': self._generate_sublime_color_rules()
        }

        with open(color_scheme_fp, 'w', encoding='utf-8') as f:
            json.dump(color_scheme_data, f, indent=2)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(color_scheme_fp)}')

        doc_model = build_documentation_model(self.model, self.verbose)
        markdown_generator = MarkdownGenerator(doc_model, self.verbose)
        instruction_docs = {
            name.upper(): markdown_generator.generate_instruction_markdown(
                name,
                doc,
                add_header_rule=True
            )
            for name, doc in doc_model.instruction_docs.items()
        }
        macro_docs = {
            name.upper(): markdown_generator.generate_instruction_markdown(
                name,
                doc,
                include_missing_doc_notice=False,
                add_header_rule=True
            )
            for name, doc in doc_model.macro_docs.items()
        }
        hover_docs = {
            'instructions': instruction_docs,
            'macros': macro_docs
        }
        docs_fp = os.path.join(destination_dir, 'instruction-docs.json')
        with open(docs_fp, 'w', encoding='utf-8') as docs_file:
            json.dump(hover_docs, docs_file, ensure_ascii=False, indent=2)
            if self.verbose > 1:
                print(f'  generated {os.path.basename(docs_fp)}')

        hover_colors = {
            'instruction': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.INSTRUCTION),
            'parameter': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.PARAMETER),
            'number': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.DECIMAL_NUMBER),
            'punctuation': DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.PUNCTUATION_SEPARATOR),
        }
        hover_colors_fp = os.path.join(destination_dir, 'hover-colors.json')
        with open(hover_colors_fp, 'w', encoding='utf-8') as colors_file:
            json.dump(hover_colors, colors_file, ensure_ascii=False, indent=2)
            if self.verbose > 1:
                print(f'  generated {os.path.basename(hover_colors_fp)}')

        # copy keymap files over
        keymap_fp = os.path.join(destination_dir, 'Default.sublime-keymap')
        fp = pkg_resources.files(resources).joinpath('sublime-keymap.json')
        shutil.copy(str(fp), keymap_fp)
        # replace the file extension name in the keymap file
        self._replace_token_in_file(keymap_fp, '##FILEEXTENSION##', self.code_extension)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(keymap_fp)}')

        fp = pkg_resources.files(resources).joinpath('bespokeasm_hover.py')
        hover_plugin = self._hover_plugin_filename()
        hover_plugin_fp = os.path.join(destination_dir, hover_plugin)
        shutil.copy(str(fp), hover_plugin_fp)
        self._replace_token_in_file(hover_plugin_fp, '##PACKAGE_NAME##', self.language_name)
        self._replace_token_in_file(hover_plugin_fp, '##LABEL_PATTERN##', self._label_pattern())
        self._replace_token_in_file(hover_plugin_fp, '##MNEMONIC_PATTERN##', self._mnemonic_pattern())
        if self.verbose > 1:
            print(f'  generated {hover_plugin}')

        fp = pkg_resources.files(resources).joinpath('sublime-settings.json')
        settings_fp = os.path.join(destination_dir, f'{self.language_name}.sublime-settings')
        shutil.copy(str(fp), settings_fp)
        self._replace_token_in_file(settings_fp, '##LANGUAGE_NAME##', self.language_name)
        if self.verbose > 1:
            print(f'  generated {os.path.basename(settings_fp)}')

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
