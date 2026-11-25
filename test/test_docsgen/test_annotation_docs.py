"""Generated ISA docs cover annotations, output formats and format-scoped zones and constants."""
import copy
import importlib.resources as pkg_resources
import json

import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.configgen.hover_docs import build_hover_docs
from bespokeasm.docsgen.documentation_model import DocumentationModel
from bespokeasm.docsgen.markdown_generator import MarkdownGenerator
from ruamel.yaml import YAML

from test import config_files

ANNOTATIONS = {
    'xmin': {
        'documentation': {
            'description': 'Export a symbol to an xmin script.',
            'examples': [
                {
                    'title': 'A variable',
                    'description': 'Exported as `int pa @ ...`.',
                    'code': '#annotate xmin kind=var type=int\npa: .2byte 0\n',
                },
                {'code': '#annotate xmin kind=const type=char\nCR = 13'},
            ],
        },
        'applies_to': ['label', 'constant'],
        'scopes': ['global'],
        'arguments': {
            'kind': {
                'type': 'enum',
                # Each value carries its own documentation; `const` has none.
                'values': {'var': {'documentation': {'description': 'a variable bound to the data'}}, 'const': None},
                'required': True,
                'documentation': {'description': 'What the export declares.'},
            },
            'type': {'type': 'enum', 'values': ['char', 'int', 'str'], 'required_when': {'kind': ['var', 'const']}},
            'count': {'type': 'integer', 'min': 1, 'allowed_when': {'kind': ['var']}},
            'array': {'type': 'boolean', 'allowed_when': {'kind': ['var']}},
            'note': {'type': 'string', 'default': 'none'},
        },
        'data_size': {
            'when': {'kind': ['var']},
            'words': {'type': {'char': 1, 'int': 2, 'str': 1}, 'times': 'count', 'infer_times': 'array'},
            'terminated_when': {'type': ['str']},
        },
        'value_range': {
            'when': {'kind': ['const']},
            'range': {'type': {'char': [0, 255], 'int': [-32768, 32767], 'str': None}},
        },
    },
}

OUTPUT_FORMAT_SHARED = {
    'xmin': {
        'predefined': {
            'memory_zones': [{
                'name': 'XMIN_CODE', 'start': 0x100, 'end': 0xfff,
                'documentation': {'title': 'xmin code', 'description': 'Where xmin code loads.'},
            }],
            'constants': [{'name': 'XMIN_DEBUG', 'value': 0, 'documentation': {'description': 'Debug level.'}}],
        },
    },
}

OUTPUT_FORMATS = {
    'xmin': {
        'shared': 'xmin',
        'documentation': {'description': 'An xmin source file.'},
        'requires_word_size': 8,
        'template': '{code}\n{symbols}',
        'sections': {
            'code': {'generator': 'hex'},
            'symbols': {
                'generator': 'exports', 'annotation': 'xmin',
                'lines_key': 'kind', 'lines': {'var': '{name}', 'const': '{name}'},
            },
        },
    },
    'xmin_debug': {
        'shared': 'xmin',
        'predefined': {'constants': [{'name': 'XMIN_DEBUG', 'value': 1}]},
        'template': '{code}',
        'sections': {'code': {'generator': 'hex'}},
    },
}


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


@pytest.fixture
def model(tmp_path) -> AssemblerModel:
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    config['annotations'] = ANNOTATIONS
    config['output_format_shared'] = OUTPUT_FORMAT_SHARED
    config['output_formats'] = OUTPUT_FORMATS
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    return AssemblerModel(str(path), 0, DiagnosticReporter())


@pytest.fixture
def markdown(model) -> str:
    return MarkdownGenerator(DocumentationModel(model)).generate()


def _section(markdown: str, heading: str) -> str:
    start = markdown.index(f'{heading}\n')
    end = markdown.find('\n# ', start + 1)
    return markdown[start:end if end != -1 else None]


def test_model_lists_format_scoped_items(model):
    doc_model = DocumentationModel(model)
    zone = next(item for item in doc_model.predefined_memory_zones if item['name'] == 'XMIN_CODE')
    assert zone['formats'] == ['xmin', 'xmin_debug']
    constant = next(item for item in doc_model.predefined_constants if item['name'] == 'XMIN_DEBUG')
    assert constant['formats'] == ['xmin', 'xmin_debug']
    assert constant['format_values'] == {'xmin': 0, 'xmin_debug': 1}


def test_format_scoped_items_say_which_formats_define_them(markdown):
    zones = _section(markdown, '## Predefined Memory Zones')
    assert 'Where xmin code loads. *Only with `-t xmin` or `-t xmin_debug`.*' in zones
    constants = _section(markdown, '## Predefined Constants')
    # A constant that the formats define differently shows its value for each.
    assert '0x0000 (`xmin`), 0x0001 (`xmin_debug`)' in constants


def test_output_formats_section(markdown):
    section = _section(markdown, '# Output Formats')
    assert '| `listing` | Source listing with addresses and assembled bytes. | built-in |' in section
    # This ISA has 8-bit words, so the xmin format's requires_word_size: 8 is not mentioned.
    assert (
        '| `xmin` | An xmin source file. | configuration | `xmin` | `XMIN_CODE`, `XMIN_DEBUG` |'
    ) in section
    assert '| `xmin_debug` |  | configuration |  | `XMIN_CODE`, `XMIN_DEBUG` |' in section
    assert '8-bit words' not in section
    # Shared sets are how a config is written; the ISA documentation does not mention them.
    assert 'shared set' not in section


def test_annotations_section(markdown):
    section = _section(markdown, '# Annotations')
    assert '## `xmin`\n\nExport a symbol to an xmin script.\n\nApplies to labels and constants, in global scope.' in section
    assert '| Argument | Description | Type | Values | Presence | Default |' in section
    assert (
        '| `kind` | What the export declares. | enum | `var`: a variable bound to the data<br>`const` | required |  |'
    ) in section
    assert '| `type` |  | enum | `char`, `int`, `str` | required when `kind` is `var` or `const` |  |' in section
    assert '| `count` |  | integer | 1 or more | optional; only when `kind` is `var` |  |' in section
    assert '| `note` |  | string |  | optional | `none` |' in section
    assert (
        "**Data size** (a label's data, when `kind` is `var`): one element's size depends on `type`: "
        '`char` 1 byte, `int` 2 bytes, `str` 1 byte. The data holds `count` elements (1 when absent); '
        'with `array`, as many elements as the data holds; when `type` is `str`, as many as the data '
        'holds before its string terminator, which must end the data.'
    ) in section
    assert (
        "**Value range** (a constant's value, when `kind` is `const`): by `type`: `char` 0 to 255, "
        '`int` -32768 to 32767, `str` not allowed.'
    ) in section
    # The framework's listing namespace is mentioned, not documented as a config namespace.
    assert '## `listing`' not in section


def test_each_value_range_rule_is_documented(tmp_path):
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    annotations = copy.deepcopy(ANNOTATIONS)
    xmin = annotations['xmin']
    xmin['value_range'] = [xmin['value_range'], {'when': {'kind': ['var']}, 'range': [0, 65535]}]
    config['annotations'] = annotations
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    markdown = MarkdownGenerator(DocumentationModel(AssemblerModel(str(path), 0, DiagnosticReporter()))).generate()
    section = _section(markdown, '# Annotations')
    assert "**Value range** (a constant's value, when `kind` is `const`): by `type`:" in section
    assert "**Value range** (a constant's value, when `kind` is `var`): 0 to 65535." in section


def test_output_formats_list_the_annotations_they_export(markdown):
    section = _section(markdown, '# Output Formats')
    assert '| Format | Description | Defined By | Exports Annotations | Predefines |' in section


def test_no_annotations_or_formats_sections_without_them(tmp_path):
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    path = tmp_path / 'plain.json'
    path.write_text(json.dumps(config))
    markdown = MarkdownGenerator(DocumentationModel(AssemblerModel(str(path), 0, DiagnosticReporter()))).generate()
    assert '# Annotations' not in markdown
    # The built-in formats are still listed: every ISA accepts them.
    assert '# Output Formats' in markdown and '`xmin`' not in markdown


def test_hover_text_for_format_scoped_items(model):
    hover = build_hover_docs(model, 0)['predefined']
    assert '| **Only with** | `-t xmin` or `-t xmin_debug` |' in hover['memory_zones']['XMIN_CODE']
    constant = hover['constants']['XMIN_DEBUG']
    assert '| **Value** | `0x0000` (`xmin`), `0x0001` (`xmin_debug`) |' in constant
    assert '| **Only with** | `-t xmin` or `-t xmin_debug` |' in constant


def test_namespace_and_argument_descriptions_are_both_kept(model):
    # An argument's documentation must not replace the namespace's own description.
    namespace = model.annotation_namespaces['xmin']
    assert namespace.description == 'Export a symbol to an xmin script.'
    assert namespace.arguments['kind'].description == 'What the export declares.'
    assert namespace.arguments['kind'].value_descriptions == (('var', 'a variable bound to the data'),)


def test_annotation_hover_text(model):
    hover = build_hover_docs(model, 0)['annotations']
    assert set(hover) == {'listing', 'xmin'}
    # The enum values, which an editor colors as values in the hover.
    assert hover['xmin']['values'] == ['char', 'const', 'int', 'str', 'var']
    assert hover['listing']['values'] == []
    assert hover['xmin']['doc'].startswith('### `xmin` : Annotation\n\n---\n\nExport a symbol to an xmin script.')
    assert hover['listing']['doc'].startswith('### `listing` : Framework Annotation')
    kind = hover['xmin']['arguments']['kind']
    assert kind.startswith('### `kind` : `xmin` Annotation Argument\n\n---\n\nWhat the export declares.')
    assert '- `var`: a variable bound to the data' in kind
    # The argument that chooses a constraint's value shows that constraint; others do not.
    assert '**Data size**' in hover['xmin']['arguments']['type']
    assert '**Value range**' in hover['xmin']['arguments']['type']
    assert '**Data size**' not in hover['xmin']['arguments']['note']
    assert 'Leaves the symbol\'s lines out of the listing' in hover['listing']['arguments']['hide']

    # Namespaces without #verbatim parts have none to show.
    assert hover['xmin']['parts'] == {} and hover['listing']['parts'] == {}


def test_verbatim_part_hover_text():
    """Each #verbatim part has hover text: its description, or a note that it is placed separately."""
    with open(pkg_resources.files(config_files).joinpath('xmin', 'slu4-minimal-64x4.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    reporter = DiagnosticReporter()
    parts = build_hover_docs(_model_from(config, reporter), 0)['annotations']['xmin']['parts']
    assert list(parts) == ['header']
    assert parts['header'].startswith('### `header` : `#verbatim xmin` Part\n\n---\n\nxmin comment lines')
    del config['annotations']['xmin']['verbatim']['parts']['header']['documentation']
    parts = build_hover_docs(_model_from(config, reporter), 0)['annotations']['xmin']['parts']
    assert parts['header'].endswith('---\n\nAn output format places these blocks separately.')


def _model_from(config: dict, reporter: DiagnosticReporter) -> AssemblerModel:
    import tempfile
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    with tempfile.TemporaryDirectory() as directory:
        path = f'{directory}/isa.json'
        with open(path, 'w') as handle:
            json.dump(config, handle)
        return AssemblerModel(path, 0, reporter)


def test_namespace_hover_lists_the_arguments(model):
    """A hover is too narrow for the arguments table, so the namespace hover lists one argument per
    line: type and values, when it is needed, its default, then its description. Each value's own
    description is in the argument's hover. The generated ISA docs keep the table."""
    doc = build_hover_docs(model, 0)['annotations']['xmin']['doc']
    assert '| Argument |' not in doc and '<br>' not in doc
    assert (
        '**Arguments:**\n\n'
        '- `kind`: enum (`var`, `const`), required. What the export declares.\n'
        '- `type`: enum (`char`, `int`, `str`), required when `kind` is `var` or `const`.\n'
        '- `count`: integer (1 or more), optional; only when `kind` is `var`.\n'
        '- `array`: boolean (a bare flag, or `true`/`false`), optional; only when `kind` is `var`.\n'
        '- `note`: string, optional, default `none`.'
    ) in doc


def _load_error(tmp_path, annotations) -> str:
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    config['annotations'] = annotations
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    with pytest.raises(SystemExit) as exc_info:
        AssemblerModel(str(path), 0, DiagnosticReporter())
    return str(exc_info.value)


ARG = 'annotations.ns.arguments.a'


@pytest.mark.parametrize(('argument', 'expected'), [
    ({'documentation': 'text'}, f'{ARG}.documentation must be a mapping'),
    ({'documentation': {'title': 'x'}}, f'{ARG}.documentation.title is not a documentation setting'),
    ({'documentation': {'description': 3}}, f'{ARG}.documentation.description must be a string'),
    (
        {'documentation': {'values': {'x': 'ex'}}},
        f'{ARG}.documentation.values is not a documentation setting; document each value under {ARG}.values',
    ),
    ({'values': {'x': 'ex'}}, f'{ARG}.values.x must be a mapping with an optional documentation block'),
    ({'values': {'x': {'title': 'ex'}}}, f'{ARG}.values.x.title is not a value setting'),
    ({'values': {'x': {'documentation': 'ex'}}}, f'{ARG}.values.x.documentation must be a mapping'),
    (
        {'values': {'x': {'documentation': {'title': 'ex'}}}},
        f'{ARG}.values.x.documentation.title is not a documentation setting; a value takes description',
    ),
    ({'values': {'x': {'documentation': {'description': 3}}}}, f'{ARG}.values.x.documentation.description must be a string'),
    ({'values': {}}, f'{ARG}.values is required for an enum argument'),
    ({'values': []}, f'{ARG}.values is required for an enum argument and must not be empty'),
])
def test_argument_documentation_errors(tmp_path, argument, expected):
    spec = {'type': 'enum', 'values': ['x'], **argument}
    assert expected in _load_error(tmp_path, {'ns': {'arguments': {'a': spec}}})


def test_enum_values_as_a_mapping_keep_their_order_and_work_in_conditions(tmp_path):
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    config['annotations'] = {'ns': {'arguments': {
        'kind': {'type': 'enum', 'values': {'b': None, 'a': {'documentation': {'description': 'the a'}}}},
        'n': {'type': 'integer', 'allowed_when': {'kind': ['a']}},
    }}}
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    kind = AssemblerModel(str(path), 0, DiagnosticReporter()).annotation_namespaces['ns'].arguments['kind']
    assert kind.values == ('b', 'a')
    assert kind.value_descriptions == (('a', 'the a'),)


def test_a_word_size_the_isa_does_not_meet_is_noted(tmp_path):
    with open(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    config['output_formats'] = {'wide': {
        'documentation': {'description': 'A 16-bit dump.'},
        'requires_word_size': 16,
        'template': '{code}',
        'sections': {'code': {'generator': 'listing'}},
    }}
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    markdown = MarkdownGenerator(DocumentationModel(AssemblerModel(str(path), 0, DiagnosticReporter()))).generate()
    assert '| `wide` | A 16-bit dump. *Cannot be used with this ISA: it needs 16-bit words.* | configuration |' in markdown


def test_namespace_examples_in_the_documentation(markdown):
    section = _section(markdown, '# Annotations')
    assert (
        '### Examples\n\n#### A variable\n\nExported as `int pa @ ...`.\n\n'
        '```assembly\n#annotate xmin kind=var type=int\npa: .2byte 0\n```\n\n'
        '```assembly\n#annotate xmin kind=const type=char\nCR = 13\n```'
    ) in section


def test_namespace_examples_in_hover_text(model):
    hover = build_hover_docs(model, 0)['annotations']
    assert '#### Examples\n\n##### A variable' in hover['xmin']['doc']
    # The framework's listing namespace has a built-in example.
    assert '#### Examples\n\n##### A heading above a collapsed table' in hover['listing']['doc']


NS = 'annotations.ns.documentation'


@pytest.mark.parametrize(('documentation', 'expected'), [
    ({'title': 'x'}, f'{NS}.title is not a documentation setting; annotations take description, examples'),
    ({'examples': 'code'}, f'{NS}.examples must be a list of examples'),
    ({'examples': ['code']}, f'{NS}.examples[0] must be a mapping with code'),
    ({'examples': [{'title': 'x'}]}, f'{NS}.examples[0] needs code'),
    ({'examples': [{'code': 'x', 'notes': 'y'}]}, f'{NS}.examples[0].notes is not an example setting'),
    ({'examples': [{'code': 3}]}, f'{NS}.examples[0].code must be a string'),
])
def test_namespace_documentation_errors(tmp_path, documentation, expected):
    assert expected in _load_error(tmp_path, {'ns': {'documentation': documentation}})
