import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.expression import ExpressionUseContext
from bespokeasm.expression import parse_expression
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M1_HARNESS_DIR = PROJECT_ROOT / 'dev' / 'flow-counters-m1'
M1_CONFIG_PATH = M1_HARNESS_DIR / 'flow-counters-m1.yaml'


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _load_config() -> dict:
    yaml = YAML(typ='safe')
    with M1_CONFIG_PATH.open() as config_file:
        return yaml.load(config_file)


def _write_config(tmp_path: Path, config: dict, name: str = 'isa.yaml') -> Path:
    config_path = tmp_path / name
    yaml = YAML()
    with config_path.open('w') as config_file:
        yaml.dump(config, config_file)
    return config_path


def _without_flow_metadata(config: dict) -> dict:
    config = copy.deepcopy(config)
    config.pop('flow_counters', None)
    for instruction in config['instructions'].values():
        for key in (
            'flow_effects',
            'flow_terminal',
            'flow_transfer',
            'flow_target_operand',
            'flow_call_effects',
            'flow_invalidates',
            'flow_write_operands',
        ):
            instruction.pop(key, None)
        for variant in instruction.get('variants', []):
            for key in (
                'flow_effects',
                'flow_terminal',
                'flow_transfer',
                'flow_target_operand',
                'flow_call_effects',
                'flow_invalidates',
                'flow_write_operands',
            ):
                variant.pop(key, None)
    return config


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config_path: Path = M1_CONFIG_PATH,
    flow_checks: bool = True,
    output_name: str = 'out.bin',
) -> Assembler:
    source_path = tmp_path / f'{output_name}.asm'
    output_path = tmp_path / output_name
    source_path.write_text(source)
    assembler = Assembler(
        source_file=str(source_path),
        config_file=str(config_path),
        generate_binary=True,
        output_file=str(output_path),
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=False,
        pretty_print_format=None,
        pretty_print_output=None,
        is_verbose=0,
        include_paths=[str(tmp_path)],
        predefined=[],
        flow_checks=flow_checks,
    )
    return assembler


def _assemble(*args, **kwargs) -> tuple[Assembler, bytes]:
    assembler = _assembler(*args, **kwargs)
    assembler.assemble_bytecode()
    return assembler, Path(assembler._output_file).read_bytes()


def _assert_flow_error(
    tmp_path: Path,
    source: str,
    expected: str,
    *,
    config_path: Path = M1_CONFIG_PATH,
    flow_checks: bool = True,
    expected_line: int | None = None,
) -> Assembler:
    assembler = _assembler(
        tmp_path,
        source,
        config_path=config_path,
        flow_checks=flow_checks,
    )
    with pytest.raises(SystemExit, match=expected):
        assembler.assemble_bytecode()
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert diagnostic.category == 'flow'
    assert diagnostic.line_id is not None
    # diagnostics must attribute the source *file* as well as the line
    assert diagnostic.line_id.filename.endswith('out.bin.asm')
    if expected_line is not None:
        assert diagnostic.line_id.line_num == expected_line
    return assembler


def test_m1_counter_operand_data_and_strip_equivalence(tmp_path):
    tracked = (M1_HARNESS_DIR / 'tracked.asm').read_text()
    stripped = (M1_HARNESS_DIR / 'stripped.asm').read_text()

    _, tracked_bytes = _assemble(tmp_path, tracked, output_name='tracked.bin')
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(tmp_path, stripped, output_name='stripped.bin')
    SymbolScope._global_scope = None
    disabled, disabled_bytes = _assemble(
        tmp_path,
        tracked,
        flow_checks=False,
        output_name='disabled.bin',
    )

    assert tracked_bytes == stripped_bytes == disabled_bytes
    assert tracked_bytes == bytes([0x10, 0x80, 0x01, 0x01, 0x11])
    assert disabled.analysis_source_index is not None
    assert not any(
        diagnostic.category == 'flow'
        for diagnostic in disabled.model.diagnostic_reporter.diagnostics
    )


def test_m1_counter_resolves_in_fill_value_and_repeated_expression(tmp_path):
    source = (
        '#track stack\n'
        'push\n'
        '.fill 2, COUNTER(stack)\n'
        '.byte COUNTER(stack) + COUNTER(stack)\n'
        'pop\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x10, 1, 1, 2, 0x11])


def test_m1_custom_source_path_supplies_constant_delta(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['source'] = 'documentation.cycles'
    for instruction in config['instructions'].values():
        instruction.pop('flow_effects', None)
        instruction['documentation'] = {'cycles': 1}
    config_path = _write_config(tmp_path, config)
    source = '#track stack exit=2\nnop\ndepth COUNTER(stack)\n#endtrack stack\n'
    _, bytecode = _assemble(tmp_path, source, config_path=config_path)
    assert bytecode == bytes([0, 0x80, 1])


def test_m1_directives_have_zero_address_footprint(tmp_path):
    tracked = (
        '.org 4\n'
        'before:\n'
        '#track stack\n'
        'nop\n'
        '#endtrack stack\n'
        'after:\n'
        '.byte after - before\n'
    )
    stripped = '.org 4\nbefore:\nnop\nafter:\n.byte after - before\n'
    _, tracked_bytes = _assemble(tmp_path, tracked, output_name='tracked-layout.bin')
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(tmp_path, stripped, output_name='stripped-layout.bin')
    assert tracked_bytes == stripped_bytes
    assert tracked_bytes[-2:] == bytes([0, 1])


def test_m1_multiple_same_line_instructions_apply_effects_in_order(tmp_path):
    source = '#track stack\npush depth COUNTER(stack)\npop\n#endtrack stack\n'
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x10, 0x80, 0x01, 0x11])


def test_m1_mute_does_not_stop_tracking(tmp_path):
    source = '\n'.join([
        '#track stack',
        '#mute',
        'push',
        '#unmute',
        'depth COUNTER(stack)',
        'pop',
        '#endtrack stack',
    ])
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode[-3:] == bytes([0x80, 0x01, 0x11])


@pytest.mark.parametrize(
    ('source', 'message', 'line_number'),
    [
        ('#track stack\npop\n#endtrack stack\n', 'underflow', 2),
        ('#track stack\npush\npush\npush\n#endtrack stack exit=3\n', 'overflow', 4),
        ('#track stack\npush\n#endtrack stack\n', 'exit mismatch', 3),
        ('#track stack\nnop\n', 'reaches EOF', 2),
        ('depth COUNTER(stack)\n', 'inactive flow counter', 1),
    ],
)
def test_m1_bounds_exit_eof_and_inactive_errors(
    tmp_path,
    source,
    message,
    line_number,
):
    _assert_flow_error(
        tmp_path,
        source,
        message,
        expected_line=line_number,
    )


def test_m1_exit_policy_none_and_explicit_exit(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['exit_policy'] = 'none'
    config_path = _write_config(tmp_path, config)
    source = '#track stack\npush\n#endtrack stack\n'
    _assemble(tmp_path, source, config_path=config_path)

    SymbolScope._global_scope = None
    source = '#track stack\npush\n#endtrack stack exit=1\n'
    _assemble(tmp_path, source, config_path=config_path)

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack\npush\n#endtrack stack exit=0\n',
        'exit mismatch',
        config_path=config_path,
    )


def test_m1_track_init_and_exit_parameters(tmp_path):
    source = '#track stack init=1 exit=0\npop\n#endtrack stack\n'
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x11])


@pytest.mark.parametrize(
    ('directive', 'message'),
    [
        ('#track', 'directive syntax'),
        ('#endtrack', 'directive syntax'),
        ('#track stack init=', 'requires a value'),
        ('#endtrack stack nonsense', 'invalid flow directive parameters'),
        ('#track 123', 'invalid flow counter class name'),
        ('#track stack mode=(', 'Invalid syntax'),
        ('#track stack mode=called mode=jumped', 'duplicate flow directive parameter'),
    ],
)
@pytest.mark.parametrize('flow_checks', [True, False])
def test_m1_malformed_flow_directive_always_reports_syntax_error(
    tmp_path,
    directive,
    message,
    flow_checks,
):
    _assert_flow_error(
        tmp_path,
        f'{directive}\n',
        message,
        flow_checks=flow_checks,
    )


@pytest.mark.parametrize(
    ('policy', 'outcome'),
    [
        ('ignore', 'ok'),
        ('warn', 'warning'),
        ('error', 'error'),
    ],
)
def test_m1_unknown_instruction_policy(tmp_path, policy, outcome):
    config = _load_config()
    config['flow_counters']['stack']['unknown_instructions'] = policy
    config['instructions']['mystery'] = {
        'flow_transfer': 'none',
        'bytecode': {'value': 0x33, 'size': 8},
    }
    config_path = _write_config(tmp_path, config)
    source = '#track stack\nmystery\n#endtrack stack\n'

    if outcome == 'error':
        _assert_flow_error(tmp_path, source, 'no effect metadata', config_path=config_path)
        return
    assembler, _ = _assemble(tmp_path, source, config_path=config_path)
    flow_warnings = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.category == 'flow' and diagnostic.level == 'warning'
    ]
    assert bool(flow_warnings) is (outcome == 'warning')


def test_missing_transfer_metadata_fails_and_m5_handles_direct_transfer(tmp_path):
    config = _load_config()
    config['instructions']['nop'].pop('flow_transfer')
    missing_path = _write_config(tmp_path, config, 'missing.yaml')
    _assert_flow_error(
        tmp_path,
        '#track stack\nnop\n#endtrack stack\n',
        'missing required flow_transfer',
        config_path=missing_path,
    )

    SymbolScope._global_scope = None
    config = _load_config()
    config['instructions']['nop']['flow_transfer'] = 'unconditional'
    config['instructions']['nop']['flow_target_operand'] = 0
    config['instructions']['nop']['operands'] = {
        'count': 1,
        'operand_sets': {'list': ['depth']},
    }
    transfer_path = _write_config(tmp_path, config, 'transfer.yaml')
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\nnop 0\n#endtrack stack\n',
        config_path=transfer_path,
    )
    assert bytecode == bytes([0, 0])


def test_m1_inert_and_unused_counter_classes_are_usage_gated(tmp_path):
    config = _load_config()
    config['flow_counters']['unused'] = {
        'unknown_instructions': 'error',
        'exit_policy': 'balanced',
    }
    config_path = _write_config(tmp_path, config)
    _assemble(
        tmp_path,
        '#track stack\nnop\n#endtrack stack\n',
        config_path=config_path,
    )

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track unused\nnop\n#endtrack unused\n',
        'is inert',
        config_path=config_path,
    )


def test_m1_effect_metadata_lookup_is_memoized(tmp_path, monkeypatch):
    assembler = _assembler(tmp_path, 'nop\n')
    model = assembler.model
    original = model._effective_instruction_configs
    scans = 0

    def counted_effective_configs(instruction_config):
        nonlocal scans
        scans += 1
        return original(instruction_config)

    monkeypatch.setattr(
        model,
        '_effective_instruction_configs',
        counted_effective_configs,
    )

    assert model.flow_counter_has_effect_metadata('stack')
    first_scan_count = scans
    assert first_scan_count > 0
    assert model.flow_counter_has_effect_metadata('stack')
    assert scans == first_scan_count

    assert not model.flow_counter_has_effect_metadata('missing')
    negative_scan_count = scans
    assert negative_scan_count > first_scan_count
    assert not model.flow_counter_has_effect_metadata('missing')
    assert scans == negative_scan_count


def test_m1_feature_enablement_and_inactive_condition_are_usage_gated(tmp_path):
    no_flow_path = _write_config(tmp_path, _without_flow_metadata(_load_config()))
    _, ordinary = _assemble(tmp_path, 'push\npop\n', config_path=no_flow_path)
    assert ordinary == bytes([0x10, 0x11])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack\n#endtrack stack\n',
        'does not enable flow counters',
        config_path=no_flow_path,
    )

    # acceptance case 56 also covers the expression-operand path: a COUNTER()
    # operand against a non-enabled ISA errors at the use, like #track does
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        'depth COUNTER(stack)\n',
        'does not enable flow counters',
        config_path=no_flow_path,
    )

    SymbolScope._global_scope = None
    _, inactive = _assemble(
        tmp_path,
        '#ifdef NEVER\n#track stack\n#endtrack stack\n#endif\nnop\n',
        config_path=no_flow_path,
    )
    assert inactive == bytes([0])


def test_m1_flow_keywords_are_reserved_only_for_enabled_isas(tmp_path):
    no_flow_config = _without_flow_metadata(_load_config())
    for value, mnemonic in enumerate(
        (
            'track',
            'endtrack',
            'entry',
            'set',
            'suspend',
            'resume',
            'counter',
            'offset',
            'coordinate',
        ),
        start=0x70,
    ):
        no_flow_config['instructions'][mnemonic] = {
            'bytecode': {'value': value, 'size': 8},
        }
    no_flow_path = _write_config(tmp_path, no_flow_config, 'no-flow-keywords.yaml')

    source = (
        'track:\n'
        'COUNTER = 9\n'
        'track\n'
        'endtrack\n'
        'entry\n'
        'set\n'
        'suspend\n'
        'resume\n'
        'counter\n'
        'offset\n'
        'coordinate\n'
        '.byte track\n'
        '.byte COUNTER\n'
    )
    _, bytecode = _assemble(
        tmp_path,
        source,
        config_path=no_flow_path,
        output_name='no-flow-keywords.bin',
    )
    assert bytecode == bytes([
        0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0, 9,
    ])

    no_flow_config = _without_flow_metadata(_load_config())
    no_flow_config['instructions']['assert'] = {
        'bytecode': {'value': 0x72, 'size': 8},
    }
    flow_path = _write_config(tmp_path, no_flow_config, 'base-keywords.yaml')
    with pytest.raises(SystemExit, match='also a BespokeASM keyword'):
        _assembler(tmp_path, 'nop\n', config_path=flow_path)

    for flow_checks in (True, False):
        with pytest.raises(SystemExit, match='used an assembler keyword'):
            _assemble(
                tmp_path,
                'track:\nnop\n',
                flow_checks=flow_checks,
                output_name=f'flow-label-{flow_checks}.bin',
            )


def test_m1_disabled_checks_resolve_dependencies_but_require_capability(tmp_path):
    annotated = '#track stack\npush\npop\n#endtrack stack\n'
    _, annotated_bytes = _assemble(
        tmp_path,
        annotated,
        flow_checks=False,
    )
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(
        tmp_path,
        'push\npop\n',
        flow_checks=False,
        output_name='stripped.bin',
    )
    assert annotated_bytes == stripped_bytes

    SymbolScope._global_scope = None
    _, counter_bytes = _assemble(
        tmp_path,
        '#track stack\npush\ndepth COUNTER(stack)\npop\n#endtrack stack\n',
        flow_checks=False,
        output_name='counter.bin',
    )
    assert counter_bytes == bytes([0x10, 0x80, 0x01, 0x11])

    no_flow_path = _write_config(tmp_path, _without_flow_metadata(_load_config()))
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack\npush\npop\n#endtrack stack\n',
        'does not enable flow counters',
        config_path=no_flow_path,
        flow_checks=False,
    )


@pytest.mark.parametrize(
    ('line', 'context'),
    [
        ('.org COUNTER(stack)', 'layout expressions'),
        ('.align COUNTER(stack)', 'layout expressions'),
        ('.fill COUNTER(stack), 0', 'fill-count expressions'),
        ('.zero COUNTER(stack)', 'layout expressions'),
        ('.zerountil COUNTER(stack)', 'layout expressions'),
        ('#if COUNTER(stack)', 'conditional-compilation directives'),
        ('VALUE = COUNTER(stack)', 'ordinary constant assignments'),
    ],
)
def test_m1_counter_is_rejected_from_layout_and_selection_contexts(tmp_path, line, context):
    _assert_flow_error(
        tmp_path,
        f'#track stack\n{line}\n#endtrack stack\n',
        context,
        expected_line=2,
    )


@pytest.mark.parametrize(
    ('line', 'context'),
    [
        ('start: .org COUNTER(stack)', 'layout expressions'),
        ('start: .align COUNTER(stack)', 'layout expressions'),
        ('start: .fill COUNTER(stack), 0', 'fill-count expressions'),
    ],
)
def test_m1_label_prefixed_layout_contexts_still_reject_flow_expressions(
    tmp_path,
    line,
    context,
):
    """Bug: label-prefixed layout lines escaped the flow-context check entirely.

    ``LineOjectFactory._validate_flow_expression_context`` only examined the
    start of the *full* line text, so ``start: .org COUNTER(stack)`` did not
    look like a layout directive to it. The flow expression then reached the
    expression parser's backstop, which raised a raw ``SyntaxError`` that
    nothing caught — a Python traceback for a CLI user instead of a diagnostic.

    Expected behavior (acceptance case 72): a labeled layout line must produce
    the same flow-category diagnostic, on the same line, as its unlabeled form;
    flow expressions must be rejected from every layout context before they
    can influence address assignment.
    """
    _assert_flow_error(
        tmp_path,
        f'#track stack\n{line}\n#endtrack stack\n',
        context,
        expected_line=2,
    )


def test_m1_labels_starting_with_layout_directive_names_are_not_layout_contexts(tmp_path):
    """Bug: the layout-context check false-positived on layout-like label names.

    The check used ``startswith(('.org', '.align', '.zero', ...))`` against the
    raw line text, so a line whose *label* merely begins with a layout directive
    name — for example the local label ``.orglabel:`` — poisoned any legitimate
    flow expression sharing the line: ``.orglabel: depth COUNTER(stack)`` was
    rejected as "flow expressions are not allowed in layout expressions".

    Expected behavior: layout-directive matching respects token boundaries, so
    a label that merely starts with a directive name is not a layout context
    and the line assembles normally.
    """
    source = '\n'.join([
        '#track stack',
        'main:',
        'push',
        '.orglabel: depth COUNTER(stack)',
        'pop',
        '#endtrack stack',
    ])
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x10, 0x80, 0x01, 0x11])


def test_m1_disabled_mode_ignores_analysis_directive_parameters(tmp_path):
    """Disabled analysis strips valid parameters without checking their modes.

    ``#track stack mode=called`` compiled with ``--no-flow-checks`` errored
    with 'flow directive parameter "mode" is not available in M1', even though
    ``mode=`` is well-formed syntax. The requirements
    (Static-Analysis Execution Control; acceptance case 76) say disabled mode
    must treat flow directives as recognized analysis-only syntax that is
    otherwise ignored — equivalent to stripping those lines — and produce no
    flow diagnostics. With analysis enabled, the selected ISA must declare the
    requested entry mode.
    """
    annotated = '#track stack mode=called\npush\npop\n#endtrack stack\n'
    disabled, annotated_bytes = _assemble(
        tmp_path,
        annotated,
        flow_checks=False,
    )
    assert not any(
        diagnostic.category == 'flow'
        for diagnostic in disabled.model.diagnostic_reporter.diagnostics
    )
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(
        tmp_path,
        'push\npop\n',
        flow_checks=False,
        output_name='stripped.bin',
    )
    assert annotated_bytes == stripped_bytes == bytes([0x10, 0x11])

    # With analysis enabled, a mode absent from this M1 fixture is an error.
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\npush\npop\n#endtrack stack\n',
        'has no entry mode "called"',
        expected_line=1,
    )


@pytest.mark.parametrize(
    'context',
    [
        ExpressionUseContext.LAYOUT,
        ExpressionUseContext.PREPROCESSOR_CONDITION,
        ExpressionUseContext.INSTRUCTION_SELECTION,
    ],
)
def test_m1_expression_parser_rejects_counter_from_non_value_contexts(context):
    with pytest.raises(SyntaxError, match='flow expressions are not allowed'):
        parse_expression(
            LineIdentifier(1, 'selection.asm'),
            'COUNTER(stack)',
            context=context,
        )


def test_m1_retrack_of_active_counter_errors_with_endtrack_guidance(tmp_path):
    """Coverage for acceptance case 15 (second half): the re-``#track`` diagnostic.

    A second ``#track`` for a counter whose lexical region is still open must
    error even when the counter is balanced, and case 15 explicitly requires
    the diagnostic to identify the still-open prior region and recommend
    inserting a lexical ``#endtrack <counter>``. The behavior existed but the
    required guidance text had no test pinning it. (M1 has no flow terminals,
    so a balanced-but-open region stands in for the spec's "even if all
    earlier paths terminated" case until M3/M5 ship terminals.)
    """
    _assert_flow_error(
        tmp_path,
        '#track stack\npush\npop\n#track stack\nnop\n#endtrack stack\n',
        'insert #endtrack stack before opening another counter',
        expected_line=4,
    )


def test_m1_explicit_flow_checks_flag_matches_default(tmp_path):
    """Coverage for acceptance case 75: ``--flow-checks`` equals the default.

    With no flag and with explicit ``--flow-checks``, the same flow-enabled
    source must produce identical bytes and identical diagnostics — enabled is
    the default. The CLI-forwarding unit test only checked the boolean reaching
    the handler; this test drives the real compile handler through the real CLI
    twice and compares the produced binary and the full (path-normalized) CLI
    output, including a flow *warning* emitted by the analysis pass, so a
    regression in either the default or the diagnostic stream fails here.
    """
    from bespokeasm.__main__ import _compile_handler
    from bespokeasm.cli import build_cli
    from bespokeasm.cli import CommandHandlers
    from click.testing import CliRunner

    config = _load_config()
    config['flow_counters']['stack']['unknown_instructions'] = 'warn'
    config['instructions']['mystery'] = {
        'flow_transfer': 'none',
        'bytecode': {'value': 0x33, 'size': 8},
    }
    config_path = _write_config(tmp_path, config)
    source = (
        '#track stack\n'
        'push\n'
        'mystery\n'
        'depth COUNTER(stack)\n'
        'pop\n'
        '#endtrack stack\n'
    )

    def noop(*_args):
        return None

    results = {}
    for label, extra_args in (('default', []), ('explicit', ['--flow-checks'])):
        run_dir = tmp_path / label
        run_dir.mkdir()
        source_path = run_dir / 'prog.asm'
        source_path.write_text(source)
        SymbolScope._global_scope = None
        cli = build_cli(CommandHandlers(_compile_handler, noop, noop, noop, noop))
        result = CliRunner().invoke(
            cli,
            ['compile', str(source_path), '--config-file', str(config_path), *extra_args],
        )
        assert result.exit_code == 0, result.output
        results[label] = (
            (run_dir / 'prog.bin').read_bytes(),
            result.output.replace(str(run_dir), '<dir>'),
        )

    assert results['default'] == results['explicit']
    default_bytes, default_output = results['default']
    assert default_bytes == bytes([0x10, 0x33, 0x80, 0x01, 0x11])
    assert 'no effect metadata' in default_output


def test_m1_analyzer_survives_a_nonfatal_diagnostic_reporter(tmp_path, monkeypatch):
    """Design hardening: the analyzer must not rely on ``error()`` never returning.

    ``DiagnosticReporter.error`` currently calls ``sys.exit``, and several
    analyzer error paths dereference state that is invalid in the error case on
    the very next line — e.g. ``#endtrack`` with no active counter immediately
    reads ``self._active.name``, and ``#track`` of an undeclared class reads
    the ``None`` class config. They were safe only because the reporter is
    fail-fast today. If the reporter ever becomes accumulate-and-continue (the
    ``diagnostics`` list points that way, and the M5 worklist will want to
    report several path errors in one run), those sites turn into
    ``AttributeError``/``TypeError`` crashes that mask the real diagnostic.

    This test simulates a non-exiting reporter and drives the linear analyzer's
    error paths, asserting each degrades to a recorded flow diagnostic instead
    of an unhandled exception. Every ``_error()`` call site is expected to
    guard-and-return rather than fall through into invalid state.
    """
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

    original_error = DiagnosticReporter.error

    def nonfatal_error(self, line_id, message, category='user'):
        try:
            original_error(self, line_id, message, category=category)
        except SystemExit:
            pass

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)

    bad_delta_config = _load_config()
    bad_delta_config['instructions']['nop']['flow_effects']['stack'] = 'runtime'
    bad_delta_path = _write_config(tmp_path, bad_delta_config, 'bad-delta.yaml')

    scenarios = [
        # #endtrack with no active counter (read self._active.name after error)
        ('close-no-active', '#endtrack stack\nnop\n', M1_CONFIG_PATH),
        # #track of an undeclared class (read counter_config.get after error)
        ('unknown-class', '#track bogus\nnop\n', M1_CONFIG_PATH),
        # re-#track while active (must not clobber the open region)
        (
            'retrack',
            '#track stack\nnop\n#track stack\nnop\n#endtrack stack\n',
            M1_CONFIG_PATH,
        ),
        # non-integer delta (value += delta after error)
        ('bad-delta', '#track stack\nnop\n#endtrack stack\n', bad_delta_path),
    ]
    for name, source, config_path in scenarios:
        SymbolScope._global_scope = None
        assembler = _assembler(
            tmp_path,
            source,
            config_path=config_path,
            output_name=f'{name}.bin',
        )
        assembler.assemble_bytecode()
        assert any(
            diagnostic.category == 'flow' and diagnostic.level == 'error'
            for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        ), f'scenario {name} recorded no flow error'


def test_m1_flow_directives_are_case_sensitive(tmp_path):
    """Requirements clarification (2026-07): all preprocessor directives —
    everything introduced with ``#``, including the flow-counter directives —
    are case-sensitive and lowercase. ``#TRACK`` is not a directive; it falls
    through to the ordinary unknown-instruction error rather than being
    recognized case-insensitively.
    """
    assembler = _assembler(tmp_path, '#TRACK stack\nnop\n')
    with pytest.raises(SystemExit, match='unknown instruction'):
        assembler.assemble_bytecode()


def test_m1_harness_is_runnable():
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    result = subprocess.run(
        [sys.executable, str(M1_HARNESS_DIR / 'verify_m1.py')],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'M1 development acceptance: PASS' in result.stdout
