"""Editor extensions highlight #annotate namespaces and argument names, and format-scoped names."""
import importlib.resources as pkg_resources
import json
import re
import zipfile

import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
from bespokeasm.configgen.color_scheme import SyntaxElement
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator
from ruamel.yaml import YAML

from test import config_files

ANNOTATIONS = {
    'xmin': {
        'verbatim': {'documentation': {'description': 'xmin script text.'}, 'parts': {'header': {}}},
        'arguments': {
            'kind': {'type': 'enum', 'values': ['addr', 'var'], 'required': True},
            'count': {'type': 'integer'},
        },
    },
}

OUTPUT_FORMAT_SHARED = {
    'xmin': {
        'predefined': {
            'memory_zones': [{'name': 'XMIN_CODE', 'start': 0x100, 'end': 0xfff}],
            'constants': [{'name': 'XMIN_DEBUG', 'value': 0}],
        },
    },
}

OUTPUT_FORMATS = {
    'xmin': {
        'shared': 'xmin',
        'template': '{code}',
        'sections': {'code': {'generator': 'hex'}},
    },
}


# Each annotation scope and the color element it is drawn with.
ANNOTATION_SCOPES = {
    'entity.name.namespace.annotation': SyntaxElement.ANNOTATION_NAMESPACE,
    'variable.parameter.annotation': SyntaxElement.ANNOTATION_ARGUMENT,
    'constant.other.annotation.value': SyntaxElement.ANNOTATION_VALUE,
}


def _color(element: SyntaxElement) -> str:
    return DEFAULT_COLOR_SCHEME.get_color(element)


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


@pytest.fixture
def config_path(tmp_path) -> str:
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    config['annotations'] = ANNOTATIONS
    config['output_format_shared'] = OUTPUT_FORMAT_SHARED
    config['output_formats'] = OUTPUT_FORMATS
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    return str(path)


def _generator(cls, config_path: str, tmp_path):
    destination = tmp_path / 'out'
    destination.mkdir()
    return cls(config_path, 0, str(destination), 'test-lang', '1.0.0', 'testasm'), destination


def test_model_names_for_highlighting(config_path):
    model = AssemblerModel(config_path, 0, DiagnosticReporter())
    namespaces, arguments = model.annotation_highlight_names
    # Longest first, so an alternation never stops at a shorter prefix.
    assert namespaces == ['listing', 'xmin']
    assert arguments == ['page_break', 'collapse', 'heading', 'count', 'hide', 'kind']
    # Names that only output formats define are highlighted like predefined ones.
    assert {'XMIN_CODE', 'XMIN_DEBUG'} <= set(model.predefined_labels)


def test_vscode_grammar(config_path, tmp_path):
    generator, destination = _generator(VSCodeConfigGenerator, config_path, tmp_path)
    generator.generate()
    extension = destination / 'extensions' / 'test-lang'
    grammar = json.loads((extension / 'syntaxes' / 'tmGrammar.json').read_text())

    annotation = grammar['repository']['annotation_directive']
    assert annotation['beginCaptures']['1']['name'] == 'keyword.control.preprocessor'
    continuation_rule, namespace_rule, argument_rule, strings, numbers, value_rule = annotation['patterns']
    assert continuation_rule == {
        'match': '\\\\(?=\\s*$)', 'name': 'punctuation.separator.continuation.annotation',
    }
    # The directive ends before a comment, or at the end of a line that does not end in \.
    end = re.compile(annotation['end'])
    assert end.search('#annotate xmin kind=var ; note').start() == len('#annotate xmin kind=var')
    assert end.search('#annotate xmin kind=var  ').start() == len('#annotate xmin kind=var')
    assert end.search('#annotate xmin kind=var \\') is None
    assert end.search('#annotate xmin kind=var \\  ') is None
    assert namespace_rule['match'] == '\\G(\\s+)(listing|xmin)\\b'
    assert namespace_rule['captures']['2']['name'] == 'entity.name.namespace.annotation'
    assert argument_rule['match'] == '\\b(page_break|collapse|heading|count|hide|kind)\\b(?:\\s*(=))?'
    assert argument_rule['captures']['1']['name'] == 'variable.parameter.annotation'
    assert argument_rule['captures']['2']['name'] == 'punctuation.separator.key-value.annotation'
    assert (strings, numbers) == ({'include': '#strings'}, {'include': '#numeric-values'})
    # A word value after '=' (numbers and strings keep their own scopes).
    assert value_rule['match'] == '(?<==)\\s*([A-Za-z_][A-Za-z0-9_]*)\\b'
    assert value_rule['captures']['1']['name'] == 'constant.other.annotation.value'

    preprocessor = next(
        pattern for pattern in grammar['repository']['directives']['patterns']
        if pattern.get('name') == 'meta.preprocessor'
    )
    assert {'include': '#annotation_directive'} in preprocessor['patterns']
    assert 'XMIN_CODE' in grammar['repository']['compiler_labels']['match']

    theme = json.loads(next(extension.glob('*theme.json')).read_text())
    rules = {rule['scope']: rule for rule in theme['tokenColors']}
    for scope, element in ANNOTATION_SCOPES.items():
        assert rules[scope]['settings']['foreground'] == _color(element)

    # A #verbatim block: first in main, so its lines are never read as assembly.
    assert grammar['repository']['main']['patterns'][0] == {'include': '#verbatim_blocks'}
    (block,) = grammar['repository']['verbatim_blocks']['patterns']
    assert block['contentName'] == 'string.unquoted.verbatim.xmin'
    begin, end = re.compile(block['begin']), re.compile(block['end'])
    assert begin.search('  #verbatim xmin ; why').groups() == ('#', 'verbatim', 'xmin', None, '; why')
    assert begin.search('#verbatim xmin header ; top').groups() == ('#', 'verbatim', 'xmin', 'header', '; top')
    assert begin.search('#verbatim listing') is None
    assert begin.search('#verbatim xmin headr') is None
    assert block['beginCaptures']['4']['name'] == 'constant.other.annotation.value'
    assert end.search('#endverbatim ; done').groups() == ('#', 'endverbatim', '; done')
    assert block['beginCaptures']['3']['name'] == 'entity.name.namespace.annotation'
    assert block['endCaptures']['3']['name'] == 'comment.line.semicolon'
    assert rules['string.unquoted.verbatim']['settings']['foreground'] == _color(SyntaxElement.VERBATIM_TEXT)

    # A trailing \ on a data directive or embedded string: a main rule, so instruction and other
    # directive lines, whose rules end at the line's end, never reach it.
    assert grammar['repository']['line_continuation'] == {
        'match': '\\\\(?=\\s*$)', 'name': 'punctuation.separator.continuation',
    }
    assert {'include': '#line_continuation'} in grammar['repository']['main']['patterns']
    for name in ('instructions', 'directives'):
        assert '#line_continuation' not in json.dumps(grammar['repository'][name])
    continuation = re.compile(grammar['repository']['line_continuation']['match'])
    assert continuation.search('.cstr "a" \\').start() == len('.cstr "a" ')
    assert continuation.search('"world" \\  ').start() == len('"world" ')
    assert continuation.search('.cstr "a\\" x') is None


def test_sublime_syntax(config_path, tmp_path):
    generator, destination = _generator(SublimeConfigGenerator, config_path, tmp_path)
    generator.generate()
    with zipfile.ZipFile(destination / 'test-lang.sublime-package') as package:
        syntax = YAML(typ='safe').load(package.read('test-lang.sublime-syntax').decode())
        color_scheme = package.read('test-lang.sublime-color-scheme').decode()

    contexts = syntax['contexts']
    assert contexts['annotation_directive'][0]['push'] == 'annotation_namespace'
    namespace_rule = contexts['annotation_namespace'][1]
    assert namespace_rule['match'] == '\\s*\\b(listing|xmin)\\b'
    assert namespace_rule['captures'][1] == 'entity.name.namespace.annotation'
    _, argument_rule, strings, numbers, value_rule, continuation_rule, pop_rule = contexts['annotation_arguments']
    assert continuation_rule == {
        'match': '\\\\(?=\\s*$)', 'scope': 'punctuation.separator.continuation.annotation',
    }
    assert re.search(pop_rule['match'], '#annotate xmin kind=var \\') is None
    assert re.search(pop_rule['match'], '#annotate xmin kind=var').start() == len('#annotate xmin kind=var')
    assert argument_rule['match'] == '\\b(page_break|collapse|heading|count|hide|kind)\\b(?:\\s*(=))?'
    assert argument_rule['captures'] == {
        1: 'variable.parameter.annotation', 2: 'punctuation.separator.key-value.annotation',
    }
    # Only numbers, not full expressions: a value such as `var` must not become an operand variable.
    assert (strings, numbers) == ({'include': 'strings'}, {'include': 'numbers'})
    assert value_rule['match'] == '(?<==)\\s*([A-Za-z_][A-Za-z0-9_]*)\\b'
    assert value_rule['captures'] == {1: 'constant.other.annotation.value'}
    assert pop_rule['pop'] is True
    assert {'include': 'annotation_directive'} in contexts['preprocessor_directives'][0]['push']
    assert 'XMIN_CODE' in contexts['compiler_labels'][0]['match']
    assert 'entity.name.namespace.annotation' in color_scheme
    assert 'constant.other.annotation.value' in color_scheme
    assert contexts['main'][0] == {'include': 'verbatim_blocks'}
    (block,) = contexts['verbatim_blocks']
    assert re.match(block['match'], '  #verbatim xmin ; why') and not re.match(block['match'], '#verbatim listing')
    assert re.match(block['match'], '#verbatim xmin header ; top').group(4) == 'header'
    assert block['captures'][3] == 'entity.name.namespace.annotation'
    assert block['captures'][4] == 'constant.other.annotation.value'
    assert block['push'] == ['verbatim_body_xmin', 'verbatim_header']
    assert contexts['verbatim_body_xmin'] == [
        {'meta_content_scope': 'string.unquoted.verbatim.xmin'},
        {'match': '^(?=\\s*\\#endverbatim\\b)', 'pop': True},
    ]
    assert 'string.unquoted.verbatim' in color_scheme
    assert 'variable.parameter.annotation' in color_scheme
    # A trailing \ on a data directive or embedded string, in main and in the data directive.
    assert contexts['line_continuation'] == [
        {'match': '\\\\(?=\\s*$)', 'scope': 'punctuation.separator.continuation'},
    ]
    assert {'include': 'line_continuation'} in contexts['main']
    data_directive = next(rule for rule in contexts['data_types_directives'] if 'push' in rule)
    assert {'include': 'line_continuation'} in data_directive['push']
    assert re.search(contexts['line_continuation'][0]['match'], '.byte 1, \\ ').start() == len('.byte 1, ')


def test_vim_syntax(config_path, tmp_path):
    generator, destination = _generator(VimConfigGenerator, config_path, tmp_path)
    generator.generate()
    vim_ft = generator.language_id.replace('-', '').lower()
    syntax = (destination / 'syntax' / f'{vim_ft}.vim').read_text()

    assert (
        f'syn match {vim_ft}AnnotationNamespace '
        r'/\%(^\s*#annotate\s\+\)\@<=\%(listing\|xmin\)\>/'
    ) in syntax
    # Argument names only on #annotate lines, and not in a trailing comment.
    assert (
        f'syn match {vim_ft}AnnotationArgument '
        r'/\%(^\s*#annotate\>[^;]*\)\@<=\<\%(page_break\|collapse\|heading\|count\|hide\|kind\)\>/'
    ) in syntax
    assert f'syn match {vim_ft}AnnotationPunct ' r'/\%(^\s*#annotate\>[^;]*\)\@<==/' in syntax
    assert f'syn match {vim_ft}AnnotationValue ' r'/\%(^\s*#annotate\>[^;]*=\s*\)\@<=\h\w*\>/' in syntax
    # A continued directive: a region from the trailing \ holds contained copies of the rules.
    assert (
        f'syn region {vim_ft}AnnotationContinued matchgroup={vim_ft}AnnotationPunct '
        r'start=/\%(^\s*#annotate\>[^;]*\)\@<=\\\s*$/ end=/\%(\\\s*\)\@<!$/ '
        f'contains={vim_ft}AnnotationArgument,{vim_ft}AnnotationPunct,{vim_ft}AnnotationValue,'
    ) in syntax
    assert (
        f'syn match {vim_ft}AnnotationArgument '
        r'/\<\%(page_break\|collapse\|heading\|count\|hide\|kind\)\>/ contained'
    ) in syntax
    # Defined after the instruction rules, so a value such as `int` is not taken as a mnemonic.
    assert syntax.index(f'syn match {vim_ft}AnnotationValue') > syntax.index(f'syn region {vim_ft}InstrLine')
    for group, element in (
        ('AnnotationNamespace', SyntaxElement.ANNOTATION_NAMESPACE),
        ('AnnotationArgument', SyntaxElement.ANNOTATION_ARGUMENT),
        ('AnnotationValue', SyntaxElement.ANNOTATION_VALUE),
    ):
        assert re.search(rf'^hi {vim_ft}{group} guifg={_color(element)}', syntax, re.MULTILINE | re.IGNORECASE)
    assert re.search(rf'^hi def link {vim_ft}AnnotationArgument Identifier$', syntax, re.MULTILINE)
    assert 'XMIN_CODE' in syntax and 'XMIN_DEBUG' in syntax
    assert (
        f'syn region {vim_ft}Verbatim start=/^\\ze\\s*#verbatim\\s\\+\\%(xmin\\)\\>/ '
        f'end=/^\\ze\\s*#endverbatim\\>/ contains='
    ) in syntax
    assert re.search(rf'^hi {vim_ft}Verbatim guifg={_color(SyntaxElement.VERBATIM_TEXT)}', syntax, re.MULTILINE | re.I)
    assert re.search(rf'^hi def link {vim_ft}Verbatim String$', syntax, re.MULTILINE)


def test_vim_verbatim_block_highlighting(config_path, tmp_path):
    """In Vim, every line of a block is the Verbatim group, while the directive lines keep their own."""
    import shutil
    import subprocess
    vim = shutil.which('vim')
    if not vim:
        pytest.skip('vim is not available')
    generator, destination = _generator(VimConfigGenerator, config_path, tmp_path)
    generator.generate()
    vim_ft = generator.language_id.replace('-', '').lower()
    source = tmp_path / 'block.testasm'
    source.write_text(
        '#verbatim xmin ; why\n  x = 1 ; text\n#if kind\n#endverbatim ; done\n  ld a, b, c\n'
        '#verbatim xmin header ; top\n# text\n#endverbatim\n'
    )
    output = tmp_path / 'groups.out'
    script = tmp_path / 'groups.vim'
    script.write_text('\n'.join([
        'let out = []',
        'for lnum in range(1, 8)',
        '  let groups = []',
        '  for col in range(1, len(getline(lnum)))',
        "    if getline(lnum)[col - 1] !~# '\\s'",
        "      call add(groups, synIDattr(synID(lnum, col, 1), 'name'))",
        '    endif',
        '  endfor',
        "  call add(out, join(uniq(groups), ','))",
        'endfor',
        f"call writefile(out, '{output}')",
    ]) + '\n')
    subprocess.run(
        [vim, '-u', 'NONE', '-N', '-es', '-c', f'set rtp={destination},$VIMRUNTIME', '-c', 'syntax on',
         '-c', f'set ft={vim_ft}', '-c', f'source {script}', '-c', 'qa!', str(source)],
        capture_output=True, text=True, timeout=60,
    )
    groups = [line.replace(vim_ft, '').split(',') for line in output.read_text().splitlines()]
    assert groups[0] == ['VerbatimPunc', 'VerbatimDirective', 'VerbatimNamespace', 'VerbatimComment']
    assert groups[1] == ['Verbatim'] and groups[2] == ['Verbatim']
    assert 'Verbatim' not in groups[3] and 'PreProc' in groups[3] and 'Comment' in groups[3]
    assert 'Verbatim' not in groups[4]
    assert groups[5] == ['VerbatimPunc', 'VerbatimDirective', 'VerbatimNamespace', 'VerbatimPart', 'VerbatimComment']
    assert groups[6] == ['Verbatim']


def test_vim_continued_data_line_highlighting(config_path, tmp_path):
    """In Vim, the trailing \\ of a data directive or embedded string is Continuation; on an
    instruction, an #annotate line or in a comment, it keeps that line's group."""
    import shutil
    import subprocess
    vim = shutil.which('vim')
    if not vim:
        pytest.skip('vim is not available')
    generator, destination = _generator(VimConfigGenerator, config_path, tmp_path)
    generator.generate()
    vim_ft = generator.language_id.replace('-', '').lower()
    source = tmp_path / 'continued.testasm'
    source.write_text(
        'msg: .cstr "ab" \\\n'
        '      "cd" \\\n'
        '      "e"   ; done\n'
        '.byte 1, 2, \\\n'
        '  3\n'
        '  ld a, b, c \\\n'
        '#annotate xmin kind=var \\\n'
        '   count=2\n'
        '; C:\\dir\\\n'
    )
    output = tmp_path / 'groups.out'
    script = tmp_path / 'groups.vim'
    script.write_text('\n'.join([
        'let out = []',
        'for lnum in range(1, 9)',
        "  let col = match(getline(lnum), '\\\\\\s*$') + 1",
        "  call add(out, col > 0 ? synIDattr(synID(lnum, col, 1), 'name') : '-')",
        'endfor',
        f"call writefile(out, '{output}')",
    ]) + '\n')
    subprocess.run(
        [vim, '-u', 'NONE', '-N', '-es', '-c', f'set rtp={destination},$VIMRUNTIME', '-c', 'syntax on',
         '-c', f'set ft={vim_ft}', '-c', f'source {script}', '-c', 'qa!', str(source)],
        capture_output=True, text=True, timeout=60,
    )
    groups = [line.replace(vim_ft, '') for line in output.read_text().splitlines()]
    assert groups == [
        'Continuation', 'Continuation', '-', 'Continuation', '-',
        'InstrLine', 'AnnotationPunct', '-', 'Comment',
    ]


# ---- hover lookups on #annotate lines --------------------------------------------------

ANNOTATE_LINE = '#annotate xmin kind=var count=3 ; kind in a comment'
VERBATIM_LINE = '#verbatim xmin ; xmin in a comment'
# On a #verbatim line, only the namespace has annotation hover text.
VERBATIM_LOOKUPS = [(2, None), (11, '### `xmin` : Annotation'), (19, None)]
# (column, expected first line of the hover text, or None)
ANNOTATE_LOOKUPS = [
    (2, None),                                              # the directive itself has its own hover
    (11, '### `xmin` : Annotation'),
    (16, '### `kind` : `xmin` Annotation Argument'),
    (21, '### `kind` : `xmin` Annotation Argument'),          # a value shows its argument
    (25, '### `count` : `xmin` Annotation Argument'),
    (35, None),                                             # `kind` in the comment
]


def _first_line(doc):
    return doc.split('\n')[0] if doc else None


def test_sublime_annotation_hover_lookup(config_path):
    import importlib.util
    import pathlib
    import sys
    import types
    sys.modules.setdefault('sublime', types.SimpleNamespace())
    sys.modules.setdefault('sublime_plugin', types.SimpleNamespace(EventListener=object))
    module_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / 'src' / 'bespokeasm' / 'configgen' / 'sublime' / 'resources' / 'bespokeasm_hover.py'
    )
    spec = importlib.util.spec_from_file_location('bespokeasm_hover_annotations', str(module_path))
    hover = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hover)

    from bespokeasm.configgen.hover_docs import build_hover_docs
    docs = build_hover_docs(AssemblerModel(config_path, 0, DiagnosticReporter()), 0)['annotations']
    for column, expected in ANNOTATE_LOOKUPS:
        assert _first_line(hover._get_annotation_doc(ANNOTATE_LINE, column, docs)) == expected, column
    assert hover._get_annotation_doc('#if kind == 1', 5, docs) is None
    for column, expected in VERBATIM_LOOKUPS:
        assert _first_line(hover._get_annotation_doc(VERBATIM_LINE, column, docs)) == expected, column
    listing = '#annotate listing heading="kind" hide'
    assert _first_line(hover._get_annotation_doc(listing, listing.index('kind') + 1, docs)) is None
    assert _first_line(hover._get_annotation_doc(listing, listing.index('hide') + 1, docs)) == (
        '### `hide` : `listing` Annotation Argument'
    )


NODE_PROBE = r'''
const Module = require('module');
const fs = require('fs');
const path = require('path');
const extensionDir = process.argv[2];
const original = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'vscode') {
    return { SemanticTokensLegend: class { constructor(types, modifiers) { this.types = types; } } };
  }
  return original.call(this, request, ...rest);
};
const source = fs.readFileSync(path.join(extensionDir, 'extension.js'), 'utf8')
  + '\nmodule.exports.__probe = getAnnotationDocAtPosition;\n';
const probePath = path.join(extensionDir, '__probe.js');
fs.writeFileSync(probePath, source);
const lookup = require(probePath).__probe;
const docs = JSON.parse(fs.readFileSync(path.join(extensionDir, 'instruction-docs.json'), 'utf8')).annotations;
const results = JSON.parse(process.argv[3]).map(([line, column]) => {
  const doc = lookup(line, column, docs);
  return doc ? doc.split('\n')[0] : null;
});
console.log(JSON.stringify(results));
'''


def test_vscode_annotation_hover_lookup(config_path, tmp_path):
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not available to run the VS Code hover lookup')
    generator, destination = _generator(VSCodeConfigGenerator, config_path, tmp_path)
    generator.generate()
    probe = tmp_path / 'probe.js'
    probe.write_text(NODE_PROBE)
    cases = (
        [[ANNOTATE_LINE, column] for column, _ in ANNOTATE_LOOKUPS] + [['#if kind == 1', 5]]
        + [[VERBATIM_LINE, column] for column, _ in VERBATIM_LOOKUPS]
    )
    result = subprocess.run(
        [node, str(probe), str(destination / 'extensions' / 'test-lang'), json.dumps(cases)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == (
        [expected for _, expected in ANNOTATE_LOOKUPS] + [None] + [expected for _, expected in VERBATIM_LOOKUPS]
    )


# A source whose #verbatim block assigns xmin variables and has an #include: neither is assembly.
VERBATIM_SOURCE = [
    'PORT = $10',
    '#verbatim xmin header ; the block',
    'prvBeg = start',
    '#include "inside.asm"',
    '#endverbatim',
    'LIMIT = 4',
]
# Each block line becomes spaces of its own length, so offsets computed from the lines stay exact.
MASKED_VERBATIM_SOURCE = [
    'PORT = $10', '#verbatim xmin header ; the block', ' ' * len('prvBeg = start'),
    ' ' * len('#include "inside.asm"'), '#endverbatim', 'LIMIT = 4',
]


# Symbols used after a #verbatim block. A semantic pass that lost the block's line lengths would
# place its highlights early, on other text.
SEMANTIC_SOURCE = [
    '#verbatim xmin header',
    '# a long line of block text, which an empty mask would drop from the offsets',
    'prvBeg = start',
    '#endverbatim',
    'LIMIT = 4',
    'start:',
    '  .byte LIMIT, start   ; start and LIMIT',
]


def _generated_sublime_plugin(config_path, tmp_path):
    """The generated Sublime plugin, with its symbol patterns filled in from the configuration."""
    import importlib.util
    import sys
    import types
    sys.modules.setdefault('sublime', types.SimpleNamespace())
    sys.modules.setdefault('sublime_plugin', types.SimpleNamespace(EventListener=object))
    generator, destination = _generator(SublimeConfigGenerator, config_path, tmp_path)
    generator.generate()
    with zipfile.ZipFile(destination / 'test-lang.sublime-package') as package:
        (name,) = (item for item in package.namelist() if item.startswith('bespokeasm_hover'))
        module_path = tmp_path / name
        module_path.write_bytes(package.read(name))
    spec = importlib.util.spec_from_file_location(f'bespokeasm_hover_{tmp_path.name}', str(module_path))
    hover = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hover)
    return hover


def test_sublime_plugin_ignores_verbatim_block_text(config_path, tmp_path):
    """The Sublime plugin's symbol lookups and semantic pass do not read a #verbatim block's text."""
    import pathlib
    hover = _generated_sublime_plugin(config_path, tmp_path)
    assert hover._mask_verbatim_blocks(VERBATIM_SOURCE) == MASKED_VERBATIM_SOURCE
    (tmp_path / 'inside.asm').write_text('INSIDE = 1\n')
    (tmp_path / 'lib.asm').write_text('\n'.join(VERBATIM_SOURCE) + '\n')
    entries = hover._collect_included_files(['#include "lib.asm"'], str(tmp_path))
    assert [pathlib.Path(entry['path']).name for entry in entries] == ['lib.asm']   # not inside.asm
    assert entries[0]['lines'] == MASKED_VERBATIM_SOURCE
    constants = hover._build_definition_map([{'path': 'main.asm', 'lines': MASKED_VERBATIM_SOURCE}], 'constant')
    assert sorted(constants) == ['LIMIT', 'PORT']


def test_sublime_semantic_regions_cover_their_symbols(config_path, tmp_path):
    """Each usage region the Sublime plugin draws covers exactly the symbol it marks, after a
    #verbatim block too: the regions are placed by offsets computed from the lines."""
    import types
    hover = _generated_sublime_plugin(config_path, tmp_path)

    class Region:
        def __init__(self, a, b):
            self.a, self.b = a, b

    class View:
        def __init__(self, text):
            self.text, self.regions = text, {}

        def id(self):
            return 1

        def change_count(self):
            return 1

        def file_name(self):
            return None

        def size(self):
            return len(self.text)

        def substr(self, region):
            return self.text[region.a:region.b]

        def add_regions(self, key, regions, scope=None, flags=0):
            self.regions[key] = [(region.a, self.text[region.a:region.b]) for region in regions]

        def erase_regions(self, key):
            self.regions.pop(key, None)

    hover.sublime = types.SimpleNamespace(Region=Region, DRAW_SOLID_UNDERLINE=0)
    hover._is_bespokeasm_view = lambda view: True
    hover._get_semantic_setting = lambda view: True
    text = '\n'.join(SEMANTIC_SOURCE) + '\n'
    view = View(text)
    hover._update_semantic_regions(view)
    usage_line = text.index('  .byte')
    # One usage each: none in the block, the comment, or the definitions.
    assert view.regions['bespokeasm_constant_usages'] == [(text.index('LIMIT', usage_line), 'LIMIT')]
    assert view.regions['bespokeasm_label_usages'] == [(text.index('start', usage_line), 'start')]


SEMANTIC_NODE_PROBE = r'''
const Module = require('module');
const fs = require('fs');
const path = require('path');
const extensionDir = process.argv[2];
const lines = JSON.parse(process.argv[3]);
const original = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'vscode') {
    return {
      SemanticTokensLegend: class { constructor(types, modifiers) { this.types = types; this.modifiers = modifiers; } },
      SemanticTokensBuilder: class {
        constructor() { this.tokens = []; }
        push(line, character, length, type, modifiers) { this.tokens.push([line, character, length, type, modifiers]); }
        build() { return this.tokens; }
      },
    };
  }
  return original.call(this, request, ...rest);
};
const source = fs.readFileSync(path.join(extensionDir, 'extension.js'), 'utf8')
  + '\nmodule.exports.__probe = { buildSemanticTokens, semanticLegend };\n';
const probePath = path.join(extensionDir, '__semantic_probe.js');
fs.writeFileSync(probePath, source);
const { buildSemanticTokens, semanticLegend } = require(probePath).__probe;
const document = {
  lineCount: lines.length,
  lineAt: (i) => ({ text: lines[i] }),
  uri: { fsPath: '' },
};
const tokens = buildSemanticTokens(document).map(([line, character, length, type, modifiers]) => ({
  line, text: lines[line].slice(character, character + length), type: semanticLegend.types[type], modifiers,
}));
console.log(JSON.stringify(tokens));
'''


def test_vscode_semantic_tokens_cover_their_symbols(config_path, tmp_path):
    """Each semantic token the VS Code extension gives covers exactly the symbol it marks, and none
    falls in a #verbatim block, whose `prvBeg = start` is not a constant definition."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not available to run the VS Code extension code')
    generator, destination = _generator(VSCodeConfigGenerator, config_path, tmp_path)
    generator.generate()
    probe = tmp_path / 'semantic_probe.js'
    probe.write_text(SEMANTIC_NODE_PROBE)
    result = subprocess.run(
        [node, str(probe), str(destination / 'extensions' / 'test-lang'), json.dumps(SEMANTIC_SOURCE)],
        capture_output=True, text=True, check=True,
    )
    tokens = [
        (token['line'], token['text'], token['type'], token['modifiers'] != 0)
        for token in json.loads(result.stdout)
    ]
    assert tokens == [
        (4, 'LIMIT', 'constant', True),       # the definitions
        (5, 'start', 'label', True),
        (6, 'LIMIT', 'constant', False),      # the usages: none in the block or the comment
        (6, 'start', 'label', False),
    ]


def test_sublime_code_block_colors_each_instruction_on_a_line(config_path, tmp_path):
    """The generated plugin knows the instruction set's mnemonics, so every instruction on a line
    gets the instruction color, as in the editor, not only the first."""
    hover = _generated_sublime_plugin(config_path, tmp_path)
    colors = {'instruction': '#000001', 'parameter': '#000002'}
    rendered = hover._render_code_block(['  ld a, b, c  mv a, b'], colors)
    words = re.findall(r'<span style="color:([^;]+);">(\w+)</span>', rendered)
    assert words == [
        ('#000001', 'ld'), ('#000002', 'a'), ('#000002', 'b'), ('#000002', 'c'),
        ('#000001', 'mv'), ('#000002', 'a'), ('#000002', 'b'),
    ]


FENCE_NODE_PROBE = r'''
const Module = require('module');
const fs = require('fs');
const path = require('path');
const extensionDir = process.argv[2];
const original = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'vscode') {
    return { SemanticTokensLegend: class { constructor(types) { this.types = types; } } };
  }
  return original.call(this, request, ...rest);
};
const source = fs.readFileSync(path.join(extensionDir, 'extension.js'), 'utf8')
  + '\nmodule.exports.__probe = withHoverCodeLanguage;\n';
const probePath = path.join(extensionDir, '__fence_probe.js');
fs.writeFileSync(probePath, source);
console.log(JSON.stringify(require(probePath).__probe(process.argv[3], 'test-lang')));
'''


def test_vscode_hover_code_fences_use_the_extensions_language(config_path, tmp_path):
    """VS Code colors fenced code in a hover with the grammar of the fence's language, so the
    extension names its own language on the docs' assembly fences; other fences are unchanged."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not available to run the VS Code extension code')
    generator, destination = _generator(VSCodeConfigGenerator, config_path, tmp_path)
    generator.generate()
    probe = tmp_path / 'fence_probe.js'
    probe.write_text(FENCE_NODE_PROBE)
    doc = 'Example:\n\n```assembly\nld a\n```\n\n```asm\nmv a\n```\n\n```\n#annotate <namespace>\n```'
    result = subprocess.run(
        [node, str(probe), str(destination / 'extensions' / 'test-lang'), doc],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == doc.replace('```assembly', '```test-lang').replace('```asm', '```test-lang')


VERBATIM_NODE_PROBE = r'''
const path = require('path');
const extensionDir = process.argv[2];
const includeFiles = require(path.join(extensionDir, 'include_files.js'));
const constantsHover = require(path.join(extensionDir, 'constants_hover.js'));
const source = JSON.parse(process.argv[3]);
const masked = includeFiles.maskVerbatimBlocks(source);
const included = includeFiles.collectIncludedFiles(['#include "lib.asm"'], process.argv[4]);
const constants = constantsHover.buildConstantDefinitionMapFromFiles([{ lines: masked }]);
console.log(JSON.stringify({
  masked,
  included: included.map((entry) => [path.basename(entry.path), entry.lines]),
  constants: [...constants.keys()].sort(),
}));
'''


def test_vscode_extension_ignores_verbatim_block_text(config_path, tmp_path):
    """The VS Code extension's symbol lookups and semantic tokens do not read a #verbatim block's text."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not available to run the VS Code extension code')
    generator, destination = _generator(VSCodeConfigGenerator, config_path, tmp_path)
    generator.generate()
    extension = destination / 'extensions' / 'test-lang'
    assert 'return includeFiles.maskNonAssemblyText(lines);' in (extension / 'extension.js').read_text()
    (tmp_path / 'inside.asm').write_text('INSIDE = 1\n')
    (tmp_path / 'lib.asm').write_text('\n'.join(VERBATIM_SOURCE) + '\n')
    probe = tmp_path / 'probe.js'
    probe.write_text(VERBATIM_NODE_PROBE)
    result = subprocess.run(
        [node, str(probe), str(extension), json.dumps(VERBATIM_SOURCE), str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    found = json.loads(result.stdout)
    assert found['masked'] == MASKED_VERBATIM_SOURCE
    assert found['included'] == [['lib.asm', MASKED_VERBATIM_SOURCE + ['']]]   # not inside.asm
    assert found['constants'] == ['LIMIT', 'PORT']


def test_vim_annotation_docs_lookup(config_path, tmp_path):
    import shutil
    import subprocess
    vim = shutil.which('vim')
    generator, destination = _generator(VimConfigGenerator, config_path, tmp_path)
    generator.generate()
    vim_ft = generator.language_id.replace('-', '').lower()
    autoload = (destination / 'autoload' / f'{vim_ft}_docs.vim').read_text()
    assert '"annotate:xmin": ' in autoload and '"annotate:xmin:kind": ' in autoload
    assert '"annotate:listing:hide": ' in autoload
    if not vim:
        pytest.skip('vim is not available to run the docs lookup')
    source = tmp_path / 'probe.testasm'
    source.write_text(ANNOTATE_LINE + '\n#if kind == 1\n' + VERBATIM_LINE + '\n')
    output = tmp_path / 'probe.out'
    script = tmp_path / 'probe.vim'
    cases = [(1, column + 1) for column, _ in ANNOTATE_LOOKUPS[1:5]] + [(2, 6), (3, 12)]
    script.write_text('\n'.join([
        f"redir! > {output}",
        f'for [lnum, col] in {[list(case) for case in cases]}',
        '  call cursor(lnum, col)',
        f"  call {vim_ft}_docs#Show(expand('<cword>'))",
        "  let found = ''",
        "  for b in range(1, bufnr('$'))",
        "    if bufname(b) =~# '__bespokeasm_docs__' && bufexists(b)",
        "      let found = get(getbufline(b, 3), 0, '')",
        '    endif',
        '  endfor',
        "  echo '|' . found",
        '  silent! pclose',
        'endfor',
        'redir END',
    ]) + '\n')
    subprocess.run(
        [vim, '-u', 'NONE', '-N', '-es', '-c', f'set rtp={destination},$VIMRUNTIME', '-c', 'filetype plugin on',
         '-c', f'set ft={vim_ft}', '-c', f'source {script}', '-c', 'qa!', str(source)],
        capture_output=True, text=True, timeout=60,
    )
    found = [line[1:] for line in output.read_text().splitlines() if line.startswith('|')]
    assert found == [expected for _, expected in ANNOTATE_LOOKUPS[1:5]] + ['', '### `xmin` : Annotation']


def test_hover_colors_are_the_syntax_colors():
    """Hover code uses the colors the editor's syntax highlighting uses for the same text."""
    from bespokeasm.configgen.color_scheme import build_hover_color_map
    from bespokeasm.configgen.color_scheme import DEFAULT_COLOR_SCHEME
    hover_colors = build_hover_color_map(DEFAULT_COLOR_SCHEME)
    for key, element in (
        ('annotation_namespace', SyntaxElement.ANNOTATION_NAMESPACE),
        ('annotation_argument', SyntaxElement.ANNOTATION_ARGUMENT),
        ('annotation_value', SyntaxElement.ANNOTATION_VALUE),
        ('string', SyntaxElement.STRING),
        ('punctuation_string', SyntaxElement.PUNCTUATION_STRING),
        ('comment', SyntaxElement.COMMENT),
        ('label', SyntaxElement.LABEL_DEFINITION),
        ('label_colon', SyntaxElement.PUNCTUATION_LABEL_COLON),
        ('verbatim_text', SyntaxElement.VERBATIM_TEXT),
        ('preprocessor', SyntaxElement.PREPROCESSOR),
        ('punctuation_preprocessor', SyntaxElement.PUNCTUATION_PREPROCESSOR),
    ):
        assert hover_colors[key] == DEFAULT_COLOR_SCHEME.get_color(element), key


# A continued #annotate, then lines that look continued but are not: the `\` is in a comment, or
# ends a data line, whose continuation is assembly.
ANNOTATE_CONTINUED_SOURCE = [
    '#annotate xmin kind=addr gap \\',
    '    description="a; b" \\',          # a ; inside quotes is not a comment
    '    note=x',
    'UART = $fe00',
    '#annotate xmin kind=addr ; a comment ends the line \\',
    'NOTE = 2',
    '.byte 1, \\',
    '  2',
]
MASKED_ANNOTATE_CONTINUED_SOURCE = [
    ANNOTATE_CONTINUED_SOURCE[0], ' ' * len(ANNOTATE_CONTINUED_SOURCE[1]), ' ' * len(ANNOTATE_CONTINUED_SOURCE[2]),
    *ANNOTATE_CONTINUED_SOURCE[3:],
]
# The #annotate line each row continues, or -1.
ANNOTATE_CONTINUATION_STARTS = [-1, 0, 0, -1, -1, -1, -1, -1]
PART_HOVER_DOCS = {'xmin': {'doc': 'NAMESPACE', 'parts': {'header': 'PART'}, 'arguments': {'note': 'NOTE'}}}
# (line, column, expected hover) on #verbatim lines, and on an #annotate continuation line read
# with its #annotate line's namespace in front, as the plugins do.
PART_HOVER_CASES = [
    ('#verbatim xmin header', 11, 'NAMESPACE'),
    ('#verbatim xmin header', 16, 'PART'),
    ('#verbatim   xmin   header ; c', 20, 'PART'),
    ('#verbatim xmin header', 3, None),
    ('#verbatim xmin footer', 16, None),
    ('#verbatim xmin', 11, 'NAMESPACE'),
    ('#annotate xmin     note=x', 20, 'NOTE'),
]


def test_sublime_plugin_reads_annotate_continuations_as_arguments(config_path, tmp_path):
    """The Sublime plugin's symbol lookups skip an #annotate's continuation lines, which hold
    arguments, and its hover finds a #verbatim part and an argument on a continuation line."""
    hover = _generated_sublime_plugin(config_path, tmp_path)
    assert hover._mask_non_assembly_text(ANNOTATE_CONTINUED_SOURCE) == MASKED_ANNOTATE_CONTINUED_SOURCE
    assert [
        hover._annotate_continuation_start(lambda row: ANNOTATE_CONTINUED_SOURCE[row], row)
        for row in range(len(ANNOTATE_CONTINUED_SOURCE))
    ] == ANNOTATE_CONTINUATION_STARTS
    constants = hover._build_definition_map(
        [{'path': 'main.asm', 'lines': hover._mask_non_assembly_text(ANNOTATE_CONTINUED_SOURCE)}], 'constant',
    )
    assert sorted(constants) == ['NOTE', 'UART']
    for line, column, expected in PART_HOVER_CASES:
        assert hover._get_annotation_doc(line, column, PART_HOVER_DOCS) == expected, (line, column)


ANNOTATE_NODE_PROBE = r"""
const Module = require('module');
const fs = require('fs');
const path = require('path');
const extensionDir = process.argv[2];
const original = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'vscode') {
    return { SemanticTokensLegend: class { constructor(types) { this.types = types; } } };
  }
  return original.call(this, request, ...rest);
};
const includeFiles = require(path.join(extensionDir, 'include_files.js'));
const constantsHover = require(path.join(extensionDir, 'constants_hover.js'));
const source = fs.readFileSync(path.join(extensionDir, 'extension.js'), 'utf8')
  + '\nmodule.exports.__probe = getAnnotationDocAtPosition;\n';
const probePath = path.join(extensionDir, '__annotate_probe.js');
fs.writeFileSync(probePath, source);
const getDoc = require(probePath).__probe;
const lines = JSON.parse(process.argv[3]);
const cases = JSON.parse(process.argv[4]);
const docs = JSON.parse(process.argv[5]);
const masked = includeFiles.maskNonAssemblyText(lines);
console.log(JSON.stringify({
  masked,
  starts: lines.map((_, row) => includeFiles.annotateContinuationStart((r) => lines[r], row)),
  constants: [...constantsHover.buildConstantDefinitionMapFromFiles([{ lines: masked }]).keys()].sort(),
  hovers: cases.map(([line, column]) => getDoc(line, column, docs)),
}));
"""


def test_vscode_extension_reads_annotate_continuations_as_arguments(config_path, tmp_path):
    """The VS Code extension's symbol lookups skip an #annotate's continuation lines, and its
    hover finds a #verbatim part and an argument on a continuation line."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not available to run the VS Code extension code')
    generator, destination = _generator(VSCodeConfigGenerator, config_path, tmp_path)
    generator.generate()
    extension = destination / 'extensions' / 'test-lang'
    probe = tmp_path / 'annotate_probe.js'
    probe.write_text(ANNOTATE_NODE_PROBE)
    result = subprocess.run(
        [
            node, str(probe), str(extension), json.dumps(ANNOTATE_CONTINUED_SOURCE),
            json.dumps([case[:2] for case in PART_HOVER_CASES]), json.dumps(PART_HOVER_DOCS),
        ],
        capture_output=True, text=True, check=True,
    )
    found = json.loads(result.stdout)
    assert found['masked'] == MASKED_ANNOTATE_CONTINUED_SOURCE
    assert found['starts'] == ANNOTATE_CONTINUATION_STARTS
    assert found['constants'] == ['NOTE', 'UART']
    assert found['hovers'] == [case[2] for case in PART_HOVER_CASES]
