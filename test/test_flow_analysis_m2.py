import copy
from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M2_DIR = PROJECT_ROOT / 'dev' / 'flow-counters-m2'
M2_CONFIG = M2_DIR / 'flow-counters-m2.yaml'


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config_path: Path = M2_CONFIG,
    static_analysis: bool = True,
    output_name: str = 'out.bin',
) -> Assembler:
    source_path = tmp_path / f'{output_name}.asm'
    output_path = tmp_path / output_name
    source_path.write_text(source)
    return Assembler(
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
        static_analysis=static_analysis,
    )


def _assemble(*args, **kwargs) -> tuple[Assembler, bytes]:
    assembler = _assembler(*args, **kwargs)
    assembler.assemble_bytecode()
    return assembler, Path(assembler._output_file).read_bytes()


def _assert_flow_error(
    tmp_path: Path,
    source: str,
    expected: str,
    *,
    config_path: Path = M2_CONFIG,
    static_analysis: bool = True,
    expected_line: int | None = None,
) -> Assembler:
    assembler = _assembler(
        tmp_path,
        source,
        config_path=config_path,
        static_analysis=static_analysis,
    )
    with pytest.raises(SystemExit, match=expected):
        assembler.assemble_bytecode()
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert diagnostic.category == 'flow'
    if expected_line is not None:
        assert diagnostic.line_id.line_num == expected_line
    return assembler


def _load_config() -> dict:
    yaml = YAML(typ='safe')
    with M2_CONFIG.open() as config_file:
        return yaml.load(config_file)


def _write_config(tmp_path: Path, config: dict) -> Path:
    config_path = tmp_path / 'isa.yaml'
    yaml = YAML()
    with config_path.open('w') as config_file:
        yaml.dump(config, config_file)
    return config_path


def test_m2_caller_parameter_offsets_follow_local_stack_push(tmp_path):
    baseline = (M2_DIR / 'subroutine-parameters.asm').read_text()
    inserted = (M2_DIR / 'subroutine-parameters-with-local.asm').read_text()

    _, baseline_bytes = _assemble(tmp_path, baseline, output_name='baseline.bin')
    SymbolScope._global_scope = None
    _, inserted_bytes = _assemble(tmp_path, inserted, output_name='inserted.bin')

    assert baseline_bytes == bytes([0x6C, 3, 0x6D, 7])
    assert inserted_bytes == bytes([0x14, 0x6C, 7, 0x6D, 11, 0x15])


def test_m2_endtrack_reconciles_routine_stack_before_rts(tmp_path):
    source = (M2_DIR / 'subroutine-parameters-with-rts.asm').read_text()
    stripped = (M2_DIR / 'subroutine-parameters-with-rts-stripped.asm').read_text()

    _, bytecode = _assemble(tmp_path, source, output_name='with-rts.bin')
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(
        tmp_path,
        stripped,
        output_name='with-rts-stripped.bin',
    )

    assert bytecode == stripped_bytes
    assert bytecode == bytes([0x14, 0x6C, 7, 0x6D, 11, 0x15, 0x69])


def test_m2_offset_is_accepted_in_indirect_register_operand(tmp_path):
    source = (
        'function:\n'
        '#track stack\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        'push\n'
        'load [sp + OFFSET(.slot)]\n'
        'pop\n'
        'pop\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x10, 0x10, 0x90, 2, 0x11, 0x11])


def test_m2_coordinate_data_and_strip_equivalence(tmp_path):
    tracked = (
        'function:\n'
        '#track stack\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        'push\n'
        '.byte OFFSET(.slot)\n'
        'pop\n'
        'pop\n'
        '#endtrack stack\n'
    )
    stripped = 'function:\npush\npush\n.byte 2\npop\npop\n'

    _, tracked_bytes = _assemble(tmp_path, tracked, output_name='tracked.bin')
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(tmp_path, stripped, output_name='stripped.bin')

    assert tracked_bytes == stripped_bytes


def test_m2_coordinate_with_scalar_baseline_and_elapsed_cycles(tmp_path):
    config = copy.deepcopy(_load_config())
    config['flow_counters']['cycles'] = {
        'default_init': 0,
        'exit_policy': 'none',
        'unknown_instructions': 'error',
    }
    for instruction in config['instructions'].values():
        instruction['flow_effects']['cycles'] = 2
    config_path = _write_config(tmp_path, config)
    source = (
        'function:\n'
        '#track cycles\n'
        '.start := COORDINATE(cycles, 2)\n'
        'nop\n'
        'nop\n'
        '.byte OFFSET(.start)\n'
        '#endtrack cycles\n'
    )

    _, bytecode = _assemble(tmp_path, source, config_path=config_path)
    assert bytecode == bytes([0, 0, 6])


def test_m2_coordinate_offset_accepts_compile_time_expression(tmp_path):
    source = (
        'PARAM_OFFSET = 3\n'
        'function:\n'
        '#track stack init=3\n'
        '.parameter := COORDINATE(stack, PARAM_OFFSET + 1 - 1)\n'
        '.byte OFFSET(.parameter)\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([3])


def test_m2_positive_coordinate_policy_rejects_negative_offset(tmp_path):
    source = (
        'function:\n'
        '#track stack\n'
        '.invalid := COORDINATE(stack, -5)\n'
        '#endtrack stack\n'
    )
    _assert_flow_error(
        tmp_path,
        source,
        'permits only positive coordinate offsets; got -5',
        expected_line=3,
    )


def test_m2_zero_coordinate_policy_can_reject_zero_offset(tmp_path):
    _assert_flow_error(
        tmp_path,
        'function:\n#track stack\n.x := COORDINATE(stack, 0)\n#endtrack stack\n',
        'does not permit zero coordinate offsets',
        expected_line=3,
    )


def test_m2_zero_coordinate_policy_defaults_to_allow(tmp_path):
    config = _load_config()
    config['flow_counters']['stack'].pop('allow_zero_offset')
    config_path = _write_config(tmp_path, config)
    source = (
        'function:\n'
        '#track stack\n'
        '.slot := COORDINATE(stack, 0)\n'
        '.byte OFFSET(.slot)\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source, config_path=config_path)
    assert bytecode == bytes([0])


def test_m2_negative_and_both_coordinate_policies(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['coordinate_offsets'] = 'negative'
    negative_config = _write_config(tmp_path, config)
    source = (
        'function:\n'
        '#track stack\n'
        '.below := COORDINATE(stack, -3)\n'
        '.byte OFFSET(.below)\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source, config_path=negative_config)
    assert bytecode == bytes([0xFD])

    SymbolScope._global_scope = None
    config['flow_counters']['stack']['coordinate_offsets'] = 'both'
    both_config = _write_config(tmp_path, config)
    source = (
        'function:\n'
        '#track stack init=3\n'
        '.above := COORDINATE(stack, 3)\n'
        '.below := COORDINATE(stack, -3)\n'
        '.byte OFFSET(.above), OFFSET(.below)\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source, config_path=both_config)
    assert bytecode == bytes([3, 0xFD])


def test_m2_popped_coordinate_is_never_resurrected(tmp_path):
    _assert_flow_error(
        tmp_path,
        (M2_DIR / 'invalidated.asm').read_text(),
        'invalid.*saved position was crossed and is no longer live',
        expected_line=7,
    )


def test_m2_negative_coordinate_is_never_resurrected_after_crossing(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['coordinate_offsets'] = 'negative'
    config_path = _write_config(tmp_path, config)
    source = (
        'function:\n'
        '#track stack\n'
        '.slot := COORDINATE(stack, -1)\n'
        'push\n'
        'push\n'
        'pop\n'
        '.byte OFFSET(.slot)\n'
        '#endtrack stack\n'
    )
    _assert_flow_error(
        tmp_path,
        source,
        'invalid.*saved position was crossed and is no longer live',
        expected_line=7,
        config_path=config_path,
    )


def test_m2_coordinate_cannot_cross_tracking_instances(tmp_path):
    source = (
        'function:\n'
        '#track stack\n'
        '.slot := COORDINATE(stack, 1)\n'
        '#endtrack stack\n'
        '#track stack\n'
        '.byte OFFSET(.slot)\n'
        '#endtrack stack\n'
    )
    _assert_flow_error(tmp_path, source, 'earlier tracking instance', expected_line=6)


def test_m2_local_and_global_coordinate_identity_are_distinct(tmp_path):
    source = (
        '#track stack\n'
        'push\n'
        'x := COORDINATE(stack, 1)\n'
        'function:\n'
        'push\n'
        '.x := COORDINATE(stack, 1)\n'
        'push\n'
        '.byte OFFSET(.x), OFFSET(x)\n'
        'pop\n'
        'pop\n'
        'pop\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode[-5:-3] == bytes([2, 3])


@pytest.mark.parametrize(
    'declaration',
    [
        '.x := 4',
        '.x := 2 * COUNTER(stack)',
        '.x := COUNTER(stack) + COUNTER(other)',
        '.x := COUNTER(stack) - 2',
    ],
)
def test_m2_rejects_non_coordinate_rhs_forms(tmp_path, declaration):
    _assert_flow_error(
        tmp_path,
        f'function:\n#track stack\n{declaration}\n#endtrack stack\n',
        'coordinate declaration',
        expected_line=3,
    )


@pytest.mark.parametrize(
    'source',
    [
        '#track stack\n.x := COORDINATE(stack, 1)\n#endtrack stack\n',
        '#track stack\n.org 4\n.x := COORDINATE(stack, 1)\n#endtrack stack\n',
    ],
)
def test_m2_local_coordinate_requires_active_local_scope(tmp_path, source):
    _assert_flow_error(tmp_path, source, 'too low of scope')


@pytest.mark.parametrize(
    'ordinary_symbol',
    ['value = 0', 'value:'],
)
def test_m2_offset_rejects_ordinary_symbols(tmp_path, ordinary_symbol):
    source = (
        f'{ordinary_symbol}\n'
        '#track stack\n'
        '.byte OFFSET(value)\n'
        '#endtrack stack\n'
    )
    _assert_flow_error(tmp_path, source, 'requires a symbol declared with :=')


@pytest.mark.parametrize(
    'offset',
    ['COUNTER(stack)', 'OFFSET(slot)', '1 + COUNTER(stack)'],
)
def test_m2_coordinate_offset_with_flow_content_reports_flow_error(tmp_path, offset):
    """Bug: a flow expression inside a COORDINATE() offset crashed the assembler.

    ``slot := COORDINATE(stack, COUNTER(stack))`` raised an uncaught
    ``SyntaxError`` ('flow expression has no tagged use context') out of the
    coordinate line factory, presenting a CLI user with a Python traceback
    instead of a diagnostic. Acceptance case 74 requires exactly this form —
    ``.x := COORDINATE(stack, COUNTER(other))`` — to be *rejected*: the offset
    must be an ordinary compile-time scalar expression containing no
    flow-derived value.

    Expected behavior: a flow-category error on the declaration line stating
    the offset must be an ordinary compile-time expression.
    """
    _assert_flow_error(
        tmp_path,
        f'#track stack\npush\nslot := COORDINATE(stack, {offset})\npop\n#endtrack stack\n',
        'ordinary compile-time expression',
        expected_line=3,
    )


def test_m2_disabled_coordinate_with_flow_offset_is_ignored(tmp_path):
    """Bug: the same flow-in-offset form also crashed under --no-static-analysis.

    The requirements state that with analysis disabled, "a flow construct used
    only by another ignored flow construct does not prevent compilation": the
    entire ``:=`` declaration is ignored analysis-only syntax, so flow content
    inside its offset must be ignored along with it, not crash the assembler.

    Expected behavior: the declaration is ignored (recorded only in the
    diagnostic-only spelling index), no flow diagnostics are produced, and the
    rest of the source assembles normally.
    """
    disabled, bytecode = _assemble(
        tmp_path,
        'slot := COORDINATE(stack, COUNTER(stack))\nnop\n',
        static_analysis=False,
    )
    assert bytecode == bytes([0x00])
    assert not any(
        diagnostic.category == 'flow'
        for diagnostic in disabled.model.diagnostic_reporter.diagnostics
    )


def test_m2_numeric_fallback_takes_precedence_over_coordinate_indexes(tmp_path):
    """Bug: coordinate lookups intercepted numerically resolvable references.

    Pre-flow-counters, an unresolved label-or-number token (e.g. ``face`` under
    ``default_numeric_base: hex``) fell back to numeric interpretation. The M2
    symbol resolution consulted the coordinate record and the disabled-mode
    ignored-declaration index *before* that fallback, so with hex as the
    default base, ``face := COORDINATE(stack, 1)`` followed by
    ``.byte face & $ff`` failed ('static analysis is disabled; cannot resolve
    face') under --no-static-analysis while its stripped twin assembled the
    byte 0xCE — violating strip-equivalence (acceptance cases 76/78, which
    require the index to be consulted only for *otherwise-unresolved*
    references).

    Expected behavior: the numeric fallback wins first in both disabled and
    enabled modes; coordinate-specific diagnostics apply only to references
    that cannot be resolved any ordinary way.
    """
    config = _load_config()
    config['general']['default_numeric_base'] = 'hex'
    config_path = _write_config(tmp_path, config)

    disabled_source = 'face := COORDINATE(stack, 1)\n.byte face & $ff\n'
    _, disabled_bytes = _assemble(
        tmp_path,
        disabled_source,
        config_path=config_path,
        static_analysis=False,
    )
    assert disabled_bytes == bytes([0xCE])

    SymbolScope._global_scope = None
    enabled_source = (
        '#track stack\n'
        'push\n'
        'face := COORDINATE(stack, 1)\n'
        '.byte face & $ff\n'
        'pop\n'
        '#endtrack stack\n'
    )
    _, enabled_bytes = _assemble(
        tmp_path,
        enabled_source,
        config_path=config_path,
        output_name='enabled.bin',
    )
    assert enabled_bytes == bytes([0x10, 0xCE, 0x11])


def test_m2_disabled_unused_declaration_is_ignored(tmp_path):
    assembler, bytecode = _assemble(
        tmp_path,
        (M2_DIR / 'disabled-unused.asm').read_text(),
        static_analysis=False,
    )
    assert bytecode == bytes([0])
    assert assembler.analysis_source_index is None


def test_m2_disabled_coordinate_dependency_has_dedicated_diagnostic(tmp_path):
    source = 'function:\n.field := COORDINATE(stack, 0)\n.byte .field\n'
    _assert_flow_error(
        tmp_path,
        source,
        r'static analysis is disabled; cannot resolve \.field',
        static_analysis=False,
        expected_line=3,
    )


def test_m2_disabled_declaration_does_not_reserve_or_shadow_symbol(tmp_path):
    source = (
        'function:\n'
        '.field := COORDINATE(stack, 0)\n'
        '.field:\n'
        '.byte .field\n'
    )
    _, bytecode = _assemble(tmp_path, source, static_analysis=False)
    assert bytecode == bytes([0])


def test_m2_coordinate_construct_requires_flow_capability(tmp_path):
    config = _load_config()
    config.pop('flow_counters')
    for instruction in config['instructions'].values():
        instruction.pop('flow_effects')
        instruction.pop('flow_transfer')
    config_path = _write_config(tmp_path, config)
    _assert_flow_error(
        tmp_path,
        'function:\n.x := 4\nnop\n',
        'does not enable flow counters',
        config_path=config_path,
        expected_line=2,
    )
    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        'function:\n.x := COORDINATE(stack, 0)\nnop\n',
        config_path=config_path,
        static_analysis=False,
        output_name='disabled-no-feature.bin',
    )
    assert bytecode == bytes([0])
