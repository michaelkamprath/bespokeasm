"""Acceptance coverage for M5.1 flow-counter documentation generation."""
import copy
import difflib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.configgen.hover_docs import build_hover_docs
from bespokeasm.docsgen import DocumentationGenerator
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _flow_docs_config() -> dict:
    """Return one compact ISA exercising every M5.1 derived-doc form."""
    return {
        'description': 'M5.1 documentation acceptance ISA',
        'general': {
            'min_version': '0.8.0',
            'address_size': 16,
            'identifier': {
                'name': 'flow-docs-test',
                'version': '1.0.0',
            },
        },
        'flow_counters': {
            'stack': {
                'documentation': {
                    'title': 'Data Stack Depth',
                    'description': 'Tracks routine-owned stack bytes.',
                },
                'min_value': 0,
                'max_value': 32,
                'default_init': 0,
                'exit_policy': 'balanced',
                'coordinate_offsets': 'positive',
                'allow_zero_offset': False,
                'unknown_instructions': 'error',
                'invalidate_on_write': [0xffff],
                'join': 'require-equal',
                'entry_modes': {
                    'called': {
                        'init': 0,
                        'exit': 0,
                        'description': 'Entered with a saved return address.',
                    },
                },
            },
            'cycles': {
                'source': 'documentation.cycles',
                'default_init': 0,
                'exit_policy': 'none',
                'unknown_instructions': 'ignore',
            },
        },
        'operand_sets': {
            'value': {
                'documentation': {
                    'title': 'Immediate value',
                },
                'operand_values': {
                    'immediate': {
                        'type': 'numeric',
                        'argument': {
                            'size': 16,
                            'word_align': True,
                        },
                    },
                },
            },
        },
        'instructions': {
            'push': {
                'documentation': {
                    'title': 'Push',
                    'cycles': 2,
                    'modifies': [
                        {
                            'register': 'sp',
                            'description': 'Moves the stack pointer.',
                        },
                    ],
                },
                'flow_effects': {'stack': 1},
                'flow_transfer': 'none',
                'bytecode': {'value': 0x10, 'size': 8},
            },
            'no_effect': {
                'documentation': {'title': 'Zero effect'},
                'flow_effects': {'stack': 0},
                'flow_transfer': 'none',
                'bytecode': {'value': 0x00, 'size': 8},
            },
            'adjust': {
                'documentation': {'title': 'Adjust stack'},
                'flow_effects': {'stack': '-ARG(0)'},
                'flow_transfer': 'none',
                'bytecode': {'value': 0x20, 'size': 8},
                'operands': {
                    'count': 1,
                    'operand_sets': {'list': ['value']},
                },
            },
            'rts': {
                'documentation': {'title': 'Return', 'cycles': 3},
                'flow_effects': {'stack': -2},
                'flow_terminal': {
                    'stack': 'before_effect',
                    'cycles': 'after_effect',
                },
                'flow_transfer': 'return',
                'bytecode': {'value': 0x69, 'size': 8},
            },
            'call': {
                'documentation': {'title': 'Call'},
                'flow_effects': {'stack': 2},
                'flow_call_effects': {'stack': 0},
                'flow_transfer': 'call',
                'flow_target_operand': 0,
                'bytecode': {'value': 0x30, 'size': 8},
                'operands': {
                    'count': 1,
                    'operand_sets': {'list': ['value']},
                },
            },
            'call_pop': {
                'documentation': {'title': 'Callee-pops call'},
                'flow_effects': {'stack': 2},
                'flow_call_effects': {'stack': -1},
                'flow_transfer': 'call',
                'flow_target_operand': 0,
                'bytecode': {'value': 0x31, 'size': 8},
                'operands': {
                    'count': 1,
                    'operand_sets': {'list': ['value']},
                },
            },
            'variantop': {
                'aliases': ['aliasop'],
                'documentation': {
                    'title': 'Variant operation',
                    'modifies': [
                        {
                            'flag': 'z',
                            'description': 'Updates zero.',
                        },
                    ],
                },
                'flow_effects': {'stack': 1},
                'flow_transfer': 'none',
                'bytecode': {'value': 0x40, 'size': 8},
                'variants': [
                    {
                        'flow_effects': {'stack': 2},
                        'bytecode': {'value': 0x41, 'size': 8},
                    },
                ],
            },
            'branch_cycles': {
                'documentation': {
                    'title': 'Branch with asymmetric timing',
                    'cycles': {
                        'taken': 3,
                        'fall_through': 2,
                    },
                },
                'flow_effects': {'stack': 0},
                'flow_transfer': 'conditional',
                'flow_target_operand': 0,
                'bytecode': {'value': 0x50, 'size': 8},
                'operands': {
                    'count': 1,
                    'operand_sets': {'list': ['value']},
                },
            },
            'write_addr': {
                'documentation': {'title': 'Write memory'},
                'flow_effects': {'stack': 0},
                'flow_transfer': 'none',
                'flow_write_operands': [0],
                'bytecode': {'value': 0x60, 'size': 8},
                'operands': {
                    'count': 1,
                    'operand_sets': {'list': ['value']},
                },
            },
            'replace_stack_anchor': {
                'documentation': {'title': 'Replace stack anchor'},
                'flow_effects': {'cycles': 2},
                'flow_invalidates': ['stack'],
                'flow_transfer': 'none',
                'bytecode': {'value': 0x61, 'size': 8},
            },
        },
    }


def _write_config(tmp_path: Path, config: dict, name: str = 'isa.yaml') -> Path:
    config_path = tmp_path / name
    yaml = YAML()
    with config_path.open('w') as config_file:
        yaml.dump(config, config_file)
    return config_path


def _generate_markdown(
    tmp_path: Path,
    config: dict,
    name: str = 'isa',
) -> str:
    config_path = _write_config(tmp_path, config, f'{name}.yaml')
    output_path = tmp_path / f'{name}.md'
    DocumentationGenerator(str(config_path)).generate_markdown_documentation(
        str(output_path),
    )
    return output_path.read_text()


def _without_flow_metadata(config: dict) -> dict:
    stripped = copy.deepcopy(config)
    stripped.pop('flow_counters', None)
    flow_keys = {
        'flow_effects',
        'flow_terminal',
        'flow_transfer',
        'flow_target_operand',
        'flow_call_effects',
        'flow_invalidates',
        'flow_write_operands',
    }
    for instruction in stripped.get('instructions', {}).values():
        for key in flow_keys:
            instruction.pop(key, None)
        for variant in instruction.get('variants', []):
            for key in flow_keys:
                variant.pop(key, None)
    return stripped


def _instruction_section(markdown: str, mnemonic: str) -> str:
    marker = f'### `{mnemonic.upper()}`'
    start = markdown.index(marker)
    following = markdown.find('\n### `', start + len(marker))
    if following < 0:
        following = len(markdown)
    return markdown[start:following]


def test_m5_1_generates_top_level_flow_counter_contract(tmp_path):
    """Acceptance 82/88: render ordered class facts, modes, and terminals."""
    markdown = _generate_markdown(tmp_path, _flow_docs_config())

    assert markdown.index('## Operand Sets') < markdown.index('# Flow Counters')
    assert markdown.index('# Flow Counters') < markdown.index('# Instructions')
    assert markdown.index('## Data Stack Depth') < markdown.index('## cycles')
    assert 'Tracks routine-owned stack bytes.' in markdown
    assert 'flow_effects.stack' in markdown
    assert '| Minimum Value | 0 |' in markdown
    assert '| Maximum Value | 32 |' in markdown
    assert '| Default Initial Value | 0 |' in markdown
    assert '| Exit Policy | `balanced` |' in markdown
    assert '| Coordinate Offsets | `positive` |' in markdown
    assert '| Allow Zero Offset | No |' in markdown
    assert '| Unknown Instructions | `error` |' in markdown
    assert '| Invalidated By Writes To | `0xffff` |' in markdown
    assert '| Join Policy | `require-equal` |' in markdown
    assert '| Mode | Initial Value | Exit Value | Description |' in markdown
    assert (
        '| `called` | 0 | 0 | Entered with a saved return address. |'
        in markdown
    )
    assert '| `rts` | Before effect |' in markdown
    assert '| `rts` | After effect |' in markdown
    assert 'Assembly-Language-Syntax#flow-counters' in markdown


def test_m5_1_non_flow_docs_are_inert(tmp_path):
    """Acceptance 83: flow enablement adds only its section and Counter rows."""
    config = _flow_docs_config()
    enabled = _generate_markdown(tmp_path, config, 'enabled')
    stripped = _generate_markdown(
        tmp_path,
        _without_flow_metadata(config),
        'stripped',
    )

    assert '# Flow Counters' not in stripped
    assert '| Counter |' not in stripped
    changes = list(difflib.ndiff(stripped.splitlines(), enabled.splitlines()))
    assert not [
        line
        for line in changes
        if line.startswith('- ')
    ], 'flow enablement changed or removed pre-existing documentation'
    flow_section = enabled.split('# Flow Counters', 1)[1].split(
        '# Instructions',
        1,
    )[0]
    flow_section_lines = set(flow_section.splitlines())
    modifies_scaffolding = {
        '',
        '# Flow Counters',
        '#### Modifies',
        '| Type | Target | Description |',
        '| --- | --- | --- |',
    }
    unexpected_additions = [
        line[2:]
        for line in changes
        if (
            line.startswith('+ ')
            and line[2:] not in flow_section_lines
            and line[2:] not in modifies_scaffolding
            and not line[2:].startswith('| Counter |')
            and not (
                line[2:].startswith('#### Modifies — Version ')
                and line[2:].endswith(' Counter Effects')
            )
        )
    ]
    assert not unexpected_additions
    assert enabled != stripped


def test_m5_1_non_flow_docs_end_with_exactly_one_terminating_newline(
    tmp_path,
):
    """Acceptance 83: pin the docs-inertness carve-out for the newline.

    Case 83 promises character identity with pre-feature output *apart from*
    the single terminating newline the generator appends per the POSIX
    text-file convention. This pins that carve-out to exactly one newline —
    never zero, never two — and that non-flow output carries no flow text.
    """
    stripped = _generate_markdown(
        tmp_path,
        _without_flow_metadata(_flow_docs_config()),
        'newline-pin',
    )

    assert stripped.endswith('\n')
    assert not stripped.endswith('\n\n')
    assert 'Flow Counters' not in stripped
    assert '| Counter |' not in stripped
    assert 'flow_effects' not in stripped


def test_m5_1_derives_delta_rows_and_preserves_manual_order(tmp_path):
    """Acceptance 84/87: derive nonzero, custom-source, and ARG rows."""
    markdown = _generate_markdown(tmp_path, _flow_docs_config())
    push = _instruction_section(markdown, 'push')
    zero = _instruction_section(markdown, 'no_effect')
    adjust = _instruction_section(markdown, 'adjust')

    assert push.index('| Register | sp |') < push.index('| Counter | stack | +1')
    assert push.count('| Counter | stack | +1') == 1
    assert '| Counter | cycles | +2' in push
    assert '| Counter | stack |' not in zero
    assert '| Counter | cycles |' not in zero
    assert '#### Modifies' in adjust
    assert '| Counter | stack | -ARG(0)' in adjust


def test_m5_1_derives_terminal_and_call_summary_rows(tmp_path):
    """Acceptance 85: show physical delta, terminal order, and call contracts."""
    markdown = _generate_markdown(tmp_path, _flow_docs_config())
    rts = _instruction_section(markdown, 'rts')
    call = _instruction_section(markdown, 'call')
    call_pop = _instruction_section(markdown, 'call_pop')

    assert '| Counter | stack | -2' in rts
    assert 'terminates the flow path' in rts
    assert 'before the instruction effect' in rts
    assert 'caller-visible net effect after return: +0' in call
    assert 'caller-visible net effect after return: -1' in call_pop
    assert 'flow_transfer' not in markdown


def test_m5_1_derives_watched_write_invalidation_rows(tmp_path):
    """Watched addresses and write operands produce an explicit Counter row.

    The operand reference is zero-based and says so, matching the zero-based
    ``ARG(0)`` presentation of operand-dependent delta rows.
    """
    markdown = _generate_markdown(tmp_path, _flow_docs_config())
    write_addr = _instruction_section(markdown, 'write_addr')

    assert (
        '| Counter | stack | Becomes indeterminate when zero-based '
        'write-target operand(s) 0 may address 0xffff. |'
        in write_addr
    )


def test_m5_1_derives_direct_invalidation_rows(tmp_path):
    """Direct anchor replacement produces an explicit Counter row."""
    markdown = _generate_markdown(tmp_path, _flow_docs_config())
    instruction = _instruction_section(markdown, 'replace_stack_anchor')

    assert (
        '| Counter | stack | Unconditionally becomes indeterminate. |'
        in instruction
    )


def test_m5_1_edge_map_deltas_have_intentional_stable_rendering(tmp_path):
    """Acceptance 84/87: edge maps never leak Python dictionary syntax."""
    config = _flow_docs_config()
    markdown = _generate_markdown(tmp_path, config)
    branch = _instruction_section(markdown, 'branch_cycles')

    assert (
        '| Counter | cycles | taken +3 / fall-through +2 physical effect. |'
        in branch
    )
    assert "{'taken':" not in branch

    config['instructions']['branch_cycles']['documentation']['cycles'] = {
        'taken': 0,
        'fall_through': 0,
    }
    zero_branch = _instruction_section(
        _generate_markdown(tmp_path, config, 'zero-edge-map'),
        'branch_cycles',
    )
    assert '| Counter | cycles |' not in zero_branch


def test_m5_1_versions_use_effective_merged_semantics_and_alias_hover(
    tmp_path,
):
    """Acceptance 86: markdown/hover use merged metadata and root alias docs."""
    config = _flow_docs_config()
    markdown = _generate_markdown(tmp_path, config)
    markdown_variant = _instruction_section(markdown, 'variantop')
    config_path = _write_config(tmp_path, config)
    model = AssemblerModel(str(config_path), 0, DiagnosticReporter())
    hover_docs = build_hover_docs(model)
    variant_markdown = hover_docs['instructions']['VARIANTOP']

    for rendered in (markdown_variant, variant_markdown):
        version_1 = rendered.split(
            '#### Modifies — Version 1 Counter Effects',
            1,
        )[1].split(
            '#### Modifies — Version 2 Counter Effects',
            1,
        )[0]
        version_2 = rendered.split(
            '#### Modifies — Version 2 Counter Effects',
            1,
        )[1]
        assert '| Counter | stack | +1' in version_1
        assert '| Counter | stack | +2' in version_2
    assert variant_markdown.count('| Flag | z | Updates zero. |') == 1
    assert hover_docs['instructions']['ALIASOP'] == variant_markdown


def test_m5_1_multi_version_counter_rows_follow_all_manual_modifies(
    tmp_path,
):
    """Acceptance 84/86: every Counter row follows all hand-authored rows."""
    markdown = _generate_markdown(tmp_path, _flow_docs_config())
    variant = _instruction_section(markdown, 'variantop')

    manual_index = variant.index('| Flag | z | Updates zero. |')
    counter_indexes = [
        variant.index('| Counter | stack | +1'),
        variant.index('| Counter | stack | +2'),
    ]
    assert all(manual_index < index for index in counter_indexes)


def test_m5_1_variants_only_root_aligns_docs_with_effective_configs(
    tmp_path,
):
    """Acceptance 86: a structural root version does not shift flow metadata."""
    config = _flow_docs_config()
    config['instructions']['variants_only'] = {
        'documentation': {'title': 'Variants only'},
        'flow_effects': {'stack': 1},
        'flow_transfer': 'none',
        'operands': {'count': 0},
        'variants': [
            {
                'flow_effects': {'stack': 2},
                'bytecode': {'value': 0x60, 'size': 8},
            },
        ],
    }
    markdown = _generate_markdown(tmp_path, config)
    variant = _instruction_section(markdown, 'variants_only')

    assert '#### Modifies — Version 2 Counter Effects' in variant
    assert '| Counter | stack | +2 physical effect. |' in variant
    assert '| Counter | stack | +1 physical effect. |' not in variant


def test_m5_1_non_flow_hover_does_not_add_alias_entries(tmp_path):
    """Acceptance 83/89: alias hover remains absent for a non-flow ISA."""
    config_path = _write_config(
        tmp_path,
        _without_flow_metadata(_flow_docs_config()),
    )
    model = AssemblerModel(str(config_path), 0, DiagnosticReporter())
    hover_docs = build_hover_docs(model)

    assert 'VARIANTOP' in hover_docs['instructions']
    assert 'ALIASOP' not in hover_docs['instructions']


@pytest.mark.parametrize(
    ('mutation', 'expected'),
    [
        (
            lambda config: config['flow_counters']['stack'].__setitem__(
                'documentation',
                'invalid',
            ),
            'flow_counters.stack.documentation must be a dictionary',
        ),
        (
            lambda config: config['flow_counters']['stack']['entry_modes'][
                'called'
            ].__setitem__('description', 4),
            (
                'flow_counters.stack.entry_modes.called.description '
                'must be a string'
            ),
        ),
    ],
)
def test_m5_1_invalid_documentation_metadata_fails_config_load(
    tmp_path,
    mutation,
    expected,
):
    """Acceptance 88: malformed class/mode documentation fails as flow config."""
    config = _flow_docs_config()
    mutation(config)
    config_path = _write_config(tmp_path, config)

    with pytest.raises(SystemExit, match=expected):
        DocumentationGenerator(
            str(config_path),
        ).generate_markdown_documentation(str(tmp_path / 'out.md'))


def test_m5_1_class_title_falls_back_to_class_name(tmp_path):
    """Acceptance 88: a class without documentation uses its name silently."""
    config = _flow_docs_config()
    config['flow_counters']['stack'].pop('documentation')
    markdown = _generate_markdown(tmp_path, config)

    assert '## stack' in markdown


def test_m5_1_entry_mode_exit_uses_the_class_exit_policy(tmp_path):
    """Acceptance 82: an omitted mode exit documents its effective contract."""
    config = _flow_docs_config()
    config['flow_counters']['cycles']['entry_modes'] = {
        'measurement': {
            'init': 0,
            'description': 'Measures an accumulating region.',
        },
    }
    markdown = _generate_markdown(tmp_path, config)

    assert (
        '| `measurement` | 0 | No implicit contract | '
        'Measures an accumulating region. |'
    ) in markdown


@pytest.mark.parametrize(
    ('mutation', 'expected'),
    [
        (
            lambda config: config['flow_counters']['stack'].__setitem__(
                'documentation',
                'invalid',
            ),
            'flow_counters.stack.documentation must be a dictionary',
        ),
        (
            lambda config: config['flow_counters']['stack']['entry_modes'][
                'called'
            ].__setitem__('description', 4),
            (
                'flow_counters.stack.entry_modes.called.description '
                'must be a string'
            ),
        ),
    ],
)
def test_m5_1_documentation_errors_are_flow_diagnostics_and_guard_return(
    tmp_path,
    monkeypatch,
    mutation,
    expected,
):
    """Acceptance 88: malformed docs report flow errors without fall-through."""
    diagnostics = []

    def nonfatal_error(
        self,
        line_id,
        message,
        category='user',
        color=None,
    ):
        diagnostics.append((message, category))

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)
    config = _flow_docs_config()
    mutation(config)
    config_path = _write_config(tmp_path, config)

    AssemblerModel(str(config_path), 0, DiagnosticReporter())

    assert diagnostics == [
        (
            expected,
            'flow',
        ),
    ]


def test_m5_1_harness_is_runnable():
    """Acceptance 82–89: the executable M5.1 development demo passes."""
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    result = subprocess.run(
        [
            sys.executable,
            str(
                PROJECT_ROOT
                / 'dev'
                / 'flow-counters-m5.1'
                / 'verify_m5_1.py'
            ),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'M5.1 development acceptance: PASS' in result.stdout
