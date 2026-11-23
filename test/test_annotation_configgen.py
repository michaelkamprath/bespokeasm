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
    namespace_rule, argument_rule, strings, numbers, value_rule = annotation['patterns']
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
    _, argument_rule, strings, numbers, value_rule, pop_rule = contexts['annotation_arguments']
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
    assert 'variable.parameter.annotation' in color_scheme


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


# ---- hover lookups on #annotate lines --------------------------------------------------

ANNOTATE_LINE = '#annotate xmin kind=var count=3 ; kind in a comment'
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
    cases = [[ANNOTATE_LINE, column] for column, _ in ANNOTATE_LOOKUPS] + [['#if kind == 1', 5]]
    result = subprocess.run(
        [node, str(probe), str(destination / 'extensions' / 'test-lang'), json.dumps(cases)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == [expected for _, expected in ANNOTATE_LOOKUPS] + [None]


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
    source.write_text(ANNOTATE_LINE + '\n#if kind == 1\n')
    output = tmp_path / 'probe.out'
    script = tmp_path / 'probe.vim'
    cases = [(1, column + 1) for column, _ in ANNOTATE_LOOKUPS[1:5]] + [(2, 6)]
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
    assert found == [expected for _, expected in ANNOTATE_LOOKUPS[1:5]] + ['']
