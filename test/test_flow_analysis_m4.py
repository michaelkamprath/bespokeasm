import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M4_HARNESS_DIR = PROJECT_ROOT / 'dev' / 'flow-counters-m4'
M4_CONFIG_PATH = M4_HARNESS_DIR / 'flow-counters-m4.yaml'
M5_CONFIG_PATH = PROJECT_ROOT / 'dev' / 'flow-counters-m5' / 'flow-counters-m5.yaml'


def _load_config() -> dict:
    yaml = YAML(typ='safe')
    with M4_CONFIG_PATH.open() as config_file:
        return yaml.load(config_file)


def _write_config(tmp_path: Path, config: dict, name: str = 'isa.yaml') -> Path:
    config_path = tmp_path / name
    yaml = YAML()
    with config_path.open('w') as config_file:
        yaml.dump(config, config_file)
    return config_path


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config_path: Path = M4_CONFIG_PATH,
    flow_checks: bool = True,
    output_name: str = 'out.bin',
    predefined: list[str] | None = None,
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
        predefined=predefined or [],
        flow_checks=flow_checks,
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
    config_path: Path = M4_CONFIG_PATH,
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
    if expected_line is not None:
        assert diagnostic.line_id.line_num == expected_line
    return assembler


def test_m4_development_acceptance_harness():
    result = subprocess.run(
        [sys.executable, str(M4_HARNESS_DIR / 'verify_m4.py')],
        cwd=PROJECT_ROOT,
        env={'PYTHONPATH': str(PROJECT_ROOT / 'src')},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'M4 development acceptance: PASS' in result.stdout


def test_m4_default_names_advance_independent_classes(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        '#track cycles\n'
        'push\n'
        '#assert stack == 1\n'
        '#assert cycles == 2\n'
        'pop\n'
        '#endtrack stack\n'
        '#endtrack cycles exit=4\n',
    )
    assert bytecode == bytes([0x10, 0x11])


def test_m4_overlapping_instances_of_one_class_advance_independently(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=outer\n'
        'nop\n'
        '#track cycles as=inner\n'
        'nop\n'
        '#endtrack inner exit=1\n'
        'nop\n'
        '#endtrack outer exit=3\n',
    )
    assert bytecode == bytes([0, 0, 0])


def test_m4_duplicate_active_name_fails_but_distinct_names_succeed(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track cycles as=window\n'
        '#track stack as=window\n',
        'flow counter "window" is still active',
        expected_line=2,
    )

    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=first\n'
        '#track cycles as=second\n'
        'nop\n'
        '#endtrack first exit=1\n'
        '#endtrack second exit=1\n',
    )
    assert bytecode == bytes([0])


@pytest.mark.parametrize(
    ('comparison', 'expected'),
    [
        ('==', 2),
        ('!=', 3),
        ('<', 3),
        ('<=', 2),
        ('>', 1),
        ('>=', 2),
    ],
)
def test_m4_assert_supports_scalar_comparisons(
    tmp_path,
    comparison,
    expected,
):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles\n'
        'push\n'
        f'#assert COUNTER(cycles) {comparison} {expected}\n'
        '#endtrack cycles exit=2\n',
    )
    assert bytecode == bytes([0x10])


def test_m4_failed_assert_reports_expected_and_actual(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track cycles\n'
        'nop\n'
        '#assert cycles == 2\n',
        'assertion failed: expected == 2, actual 1',
        expected_line=3,
    )


def test_m4_set_reanchors_only_the_named_counter(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=left\n'
        '#track cycles as=right\n'
        'nop\n'
        '#set left = COUNTER(right) + 4\n'
        'nop\n'
        '#assert left == 6\n'
        '#assert right == 2\n'
        '#endtrack left exit=6\n'
        '#endtrack right exit=2\n',
    )
    assert bytecode == bytes([0, 0])


def test_m4_suspend_pauses_only_the_named_counter(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=paused\n'
        '#track cycles as=running\n'
        'nop\n'
        '#suspend paused\n'
        'nop\n'
        '#resume paused = 1\n'
        'nop\n'
        '#assert paused == 2\n'
        '#assert running == 3\n'
        '#endtrack paused exit=2\n'
        '#endtrack running exit=3\n',
    )
    assert bytecode == bytes([0, 0, 0])


@pytest.mark.parametrize(
    ('source', 'expected', 'expected_line'),
    [
        (
            '#track cycles\n'
            '#suspend cycles\n'
            'depth COUNTER(cycles)\n',
            'cannot be resolved while flow counter "cycles" is suspended',
            3,
        ),
        (
            'routine:\n'
            '#track stack\n'
            '.slot := COORDINATE(stack, 0)\n'
            '#suspend stack\n'
            'depth .slot\n',
            'cannot be resolved while flow counter "stack" is suspended',
            5,
        ),
        (
            '#track stack\n'
            '#suspend stack\n'
            '.slot := COORDINATE(stack, 0)\n',
            'cannot declare a coordinate while the counter is suspended',
            3,
        ),
        (
            '#track stack\n'
            '#suspend stack\n'
            'rts\n',
            'cannot reconcile suspended flow counter "stack"',
            3,
        ),
    ],
)
def test_m4_suspended_state_rejects_value_dependent_operations(
    tmp_path,
    source,
    expected,
    expected_line,
):
    _assert_flow_error(
        tmp_path,
        source,
        expected,
        expected_line=expected_line,
    )


def test_m4_resume_from_coordinate_invalidates_presuspension_slots(tmp_path):
    _assert_flow_error(
        tmp_path,
        'routine:\n'
        '#track stack\n'
        '.saved := COORDINATE(stack, 0)\n'
        '#suspend stack\n'
        'push\n'
        '#resume stack = .saved\n'
        'depth .saved\n',
        'counter coordinate ".saved" is invalid',
        expected_line=7,
    )


def test_m4_plain_endtrack_may_abandon_a_suspended_region(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles\n'
        '#suspend cycles\n'
        'nop\n'
        '#endtrack cycles\n',
    )
    assert bytecode == bytes([0])


def test_m4_terminal_reconciles_all_instances_of_mapped_class_only(tmp_path):
    """Case 46: a return terminal reconciles every active instance of each
    mapped class; an active instance of a different class is unaffected by the
    reconciliation — but it cannot *cross* the return either (see the
    companion cross-return test), so it must be closed before the terminal.
    Here both same-class frames are reconciled by one ``rts`` while the
    ``cycles`` window observes only its own effects and closes beforehand.
    """
    _, bytecode = _assemble(
        tmp_path,
        '#track stack as=frame_a mode=called\n'
        '#track stack as=frame_b mode=called\n'
        '#track cycles\n'
        'nop\n'
        '#endtrack cycles exit=1\n'
        'rts\n'
        '#endtrack frame_a\n'
        '#endtrack frame_b\n',
    )
    assert bytecode == bytes([0x00, 0x69])


def test_m4_unmapped_counter_cannot_cross_a_return_terminal(tmp_path):
    """Bug: a live counter not mapped on a return terminal silently survived it.

    With ``stack`` mapped on ``rts`` and ``cycles`` merely active, the old
    behavior applied the normal cycles delta at the ``rts`` and kept the
    cycles path live — so cycles accrued effects from *unreachable* code after
    the return, and ``COUNTER(cycles)`` even resolved there. The requirements
    say unreachable lines receive no counter state, and the behavior was
    internally inconsistent: the same cycles region crossing the same ``rts``
    errors when tracked alone. Expected behavior: a return terminal is a
    region exit with no fall-through, so every live counter must either be
    reconciled by it (mapped) or have been closed with ``#endtrack`` before
    it; a live unmapped counter errors on the terminal's line.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\n'
        '#track cycles\n'
        'rts\n'
        '#endtrack cycles\n'
        '#endtrack stack\n',
        r'returns while flow counter "cycles" is still active; '
        r'end the region with #endtrack cycles before this transfer',
        expected_line=3,
    )


def test_m4_set_invalidates_prior_coordinates(tmp_path):
    """Bug: ``#set`` re-anchored a counter without invalidating its coordinates.

    Dead-coordinate rule 5 of the requirements: "``#set``, ``#resume``, and an
    ``#entry`` root at a non-initial depth also invalidate prior coordinates
    unless a future explicit preservation contract says otherwise." ``#set``
    exists precisely because the effect model could not express what happened
    to the counter, so no prior slot's survival is provable. The old behavior
    only ran the crossing-based liveness check, so ``.x`` after a
    ``#set`` happily emitted an offset from a stale slot.
    """
    _assert_flow_error(
        tmp_path,
        'function:\n'
        '#track stack\n'
        'push\n'
        '.x := COORDINATE(stack, 1)\n'
        '#set stack = 5\n'
        'depth .x\n'
        '#endtrack stack exit=5\n',
        r'counter coordinate "\.x" is invalid',
        expected_line=6,
    )


def test_m4_set_checks_bounds_after_reanchor(tmp_path):
    """Pins existing behavior: a ``#set`` value outside the class bounds errors.

    The spec is silent on whether the taken-on-faith ``#set`` value is bounds
    checked; the implementation checks it, which is the safer reading — a
    programmer asserting a value the class declares impossible is most likely
    a mistake. This test makes that a deliberate, documented choice.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack\n'
        '#set stack = -3\n'
        'nop\n'
        '#endtrack stack\n',
        'underflow',
        expected_line=2,
    )


def test_m4_resume_to_invalidated_coordinate_warns(tmp_path):
    """Decision (2026-07): ``#resume <counter> = <coordinate>`` naming a
    coordinate the analyzer already invalidated is accepted on faith — the
    spec only forbids reading invalid coordinates — but re-anchoring
    to a position that was provably crossed deserves a flow warning.
    """
    source = (
        'function:\n'
        '#track stack\n'
        'push\n'
        'push\n'
        '.x := COORDINATE(stack, 1)\n'
        'pop\n'
        'pop\n'
        '#suspend stack\n'
        'nop\n'
        '#resume stack = .x\n'
        'pop\n'
        '#endtrack stack\n'
    )
    assembler, _ = _assemble(tmp_path, source)
    warnings = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.level == 'warning' and diagnostic.category == 'flow'
    ]
    assert any(
        '.x' in diagnostic.message and 'invalidated' in diagnostic.message
        for diagnostic in warnings
    ), 'expected a flow warning about resuming to an invalidated coordinate'


def test_m4_failing_endtrack_on_one_of_two_same_class_windows(tmp_path):
    """Case 44 (negative half): each overlapping same-class window's
    ``#endtrack exit=`` is checked independently — a mismatch on the inner
    window errors, naming that window, while the outer remains unaffected.
    """
    _assert_flow_error(
        tmp_path,
        '#track cycles as=outer\n'
        '#track cycles as=inner\n'
        'nop\n'
        '#endtrack inner exit=5\n'
        '#endtrack outer exit=1\n',
        'flow counter "inner" exit mismatch: expected 5, actual 1',
        expected_line=4,
    )


def test_m4_violation_names_the_offending_counter_among_concurrent_classes(tmp_path):
    """Case 16: with two different-class counters active on one instruction
    stream, a violation is attributed to the specific offending counter.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack\n'
        '#track cycles\n'
        'pop\n'
        '#endtrack cycles\n'
        '#endtrack stack\n',
        'flow counter "stack" underflow',
        expected_line=3,
    )


def test_m4_error_paths_survive_a_nonfatal_diagnostic_reporter(tmp_path, monkeypatch):
    """Extends the M1/M2 nonfatal-reporter regression tests with M4 error sites.

    Every ``_error()`` call site must guard-and-return; with a non-exiting
    reporter each scenario must degrade to a recorded flow diagnostic rather
    than crash on invalid state (see the M1 test of the same name for the full
    rationale).
    """
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

    original_error = DiagnosticReporter.error

    def nonfatal_error(self, line_id, message, category='user', color=None):
        try:
            original_error(self, line_id, message, category=category, color=color)
        except SystemExit:
            pass

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)

    scenarios = [
        ('set-inactive', '#set absent = 1\nnop\n'),
        ('resume-not-suspended', '#track stack\n#resume stack = 0\nnop\n#endtrack stack\n'),
        ('suspend-twice', '#track stack\n#suspend stack\n#suspend stack\nnop\n'),
        ('assert-failure', '#track stack\npush\n#assert stack == 5\npop\n#endtrack stack\n'),
        (
            'unmapped-cross-return',
            '#track stack mode=called\n#track cycles\nrts\n#endtrack cycles\n#endtrack stack\n',
        ),
        (
            'suspended-terminal',
            '#track stack\n#suspend stack\nrts\n',
        ),
        (
            'instance-bound-looser-than-class',
            '#track stack max=100\nnop\n#endtrack stack\n',
        ),
        (
            'init-beyond-instance-bound',
            '#track stack init=6 max=4\nnop\n#endtrack stack\n',
        ),
    ]
    for name, source in scenarios:
        SymbolScope._global_scope = None
        assembler = _assembler(tmp_path, source, output_name=f'{name}.bin')
        assembler.assemble_bytecode()
        assert any(
            diagnostic.category == 'flow' and diagnostic.level == 'error'
            for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        ), f'scenario {name} recorded no flow error'


def test_m4_inactive_or_undeclared_instance_errors(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#assert absent == 0\n',
        '#assert references inactive flow counter "absent"',
        expected_line=1,
    )
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track missing\n',
        'flow counter class "missing" is not declared',
        expected_line=1,
    )


def test_m4_flow_directive_expressions_are_context_aware(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=source\n'
        '#track cycles as=target\n'
        'nop\n'
        '#set target = COUNTER(source) + 2\n'
        '#assert target == COUNTER(source) + 2\n'
        '#endtrack source exit=1\n'
        '#endtrack target exit=3\n',
    )
    assert bytecode == bytes([0])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#if COUNTER(source)\n'
        '#endif\n'
        'nop\n',
        'flow expressions are not allowed in conditional-compilation directives',
        expected_line=1,
    )


def test_m4_inactive_conditional_ignores_all_flow_directives(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#ifdef NEVER\n'
        '#track malformed as===\n'
        '#entry malformed value===\n'
        '#assert not valid syntax\n'
        '#set cycles\n'
        '#suspend\n'
        '#resume cycles\n'
        '#endif\n'
        'nop\n',
    )
    assert bytecode == bytes([0])


def test_m4_disabled_analysis_ignores_valid_manual_control_but_not_bad_syntax(
    tmp_path,
):
    _, annotated = _assemble(
        tmp_path,
        '#track cycles as=window\n'
        '#assert window == 99\n'
        '#set window = COUNTER(window) + 1\n'
        '#suspend window\n'
        '#resume window = 0\n'
        '#endtrack window exit=99\n'
        'nop\n',
        flow_checks=False,
        output_name='annotated.bin',
    )
    SymbolScope._global_scope = None
    _, stripped = _assemble(
        tmp_path,
        'nop\n',
        flow_checks=False,
        output_name='stripped.bin',
    )
    assert annotated == stripped == bytes([0])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#resume cycles\nnop\n',
        'invalid #resume directive syntax',
        flow_checks=False,
        expected_line=1,
    )


@pytest.mark.parametrize(
    ('slot', 'source'),
    [
        (
            'set',
            '#define FRAME 2\n'
            '#track stack\n'
            '#set stack = FRAME\n'
            'pop\npop\n'
            '#endtrack stack exit=0\n',
        ),
        (
            'resume',
            '#define RESUMED 2\n'
            '#track stack\n'
            '#suspend stack\n'
            'nop\n'
            '#resume stack = RESUMED\n'
            'pop\npop\n'
            '#endtrack stack exit=0\n',
        ),
        (
            'init',
            '#define START 2\n'
            '#track stack init=START exit=0\n'
            'pop\npop\n'
            '#endtrack stack\n',
        ),
        (
            'exit',
            '#define BALANCE 2\n'
            '#track stack\n'
            'push\npush\n'
            '#endtrack stack exit=BALANCE\n',
        ),
    ],
)
def test_m4_flow_directive_values_resolve_define_macros(tmp_path, slot, source):
    """Decision (2026-07): flow-directive value expressions accept every
    compile-time constant kind — assembler-assigned (``=``/``EQU``) constants,
    ``#define`` preprocessor macros, and ISA-configuration predefined
    constants — matching ``#assert`` and ordinary instruction operands.

    Previously ``#define``'d macros failed in all four value slots ("Label
    FRAME resolves to NONE"): preprocessor lines are dispatched before macro
    substitution, and unlike ``#assert`` the flow directives did not resolve
    their own value text. Only the *value* side is macro-resolved; counter and
    coordinate names stay literal.
    """
    expected = {
        'set': bytes([0x11, 0x11]),
        'resume': bytes([0x00, 0x11, 0x11]),
        'init': bytes([0x11, 0x11]),
        'exit': bytes([0x10, 0x10]),
    }[slot]
    _, bytecode = _assemble(tmp_path, source, output_name=f'{slot}.bin')
    assert bytecode == expected


def test_m4_flow_directive_values_resolve_isa_predefined_constants(tmp_path):
    """Companion pin: ISA-configuration predefined constants already resolve
    in flow-directive values (they enter the global symbol scope at model
    load, like ``=``/``EQU`` constants). Pinned so the all-constant-kinds rule
    is enforced for every kind, not just the one that needed fixing.
    """
    config = _load_config()
    config['predefined'] = {'constants': [{'name': 'ISAFRAME', 'value': 2}]}
    config_path = _write_config(tmp_path, config)
    _, bytecode = _assemble(
        tmp_path,
        '#track stack init=ISAFRAME\n'
        '#set stack = ISAFRAME\n'
        'pop\npop\n'
        '#endtrack stack exit=0\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0x11, 0x11])


def test_m4_macro_resolution_protects_flow_operand_and_identifier_names(tmp_path):
    """Macro resolution must never rewrite flow names, only values.

    With ``#define source 5`` in effect, ``#track cycles as=source`` must
    still create an instance literally named ``source`` (identifier
    parameters are not macro-resolved), and ``COUNTER(source)`` inside a
    ``#set`` value must still reference that instance (flow-operator argument
    names are protected from substitution, as in ``#assert``).
    """
    _, bytecode = _assemble(
        tmp_path,
        '#define source 5\n'
        '#track cycles as=source\n'
        '#track cycles as=target\n'
        'nop\n'
        '#set target = COUNTER(source) + 2\n'
        '#assert target == 3\n'
        '#endtrack source exit=1\n'
        '#endtrack target exit=3\n',
    )
    assert bytecode == bytes([0x00])


def test_m4_ordinary_line_macro_resolution_protects_flow_names(tmp_path):
    """Names passed to flow operators are literal in every context.

    Bug (inconsistency): ordinary lines receive whole-line preprocessor
    substitution in the line factory with no flow-name protection, so with
    ``#define stack 5`` in effect, ``depth COUNTER(stack)`` became
    ``COUNTER(5)`` ("COUNTER() requires one counter name") and
    ``.x := COORDINATE(stack, 1)`` became ``COORDINATE(5, 1)`` — while the
    same names in ``#assert``/``#set`` values were protected. The
    name-vs-value rule is context-universal: the names passed to
    ``COUNTER()`` and ``COORDINATE()`` stay literal wherever
    they appear; only value expressions are macro-resolved.
    """
    _, counter_bytes = _assemble(
        tmp_path,
        '#define stack 5\n'
        '#track stack\n'
        'push\n'
        'depth COUNTER(stack)\n'
        'pop\n'
        '#endtrack stack\n',
        output_name='counter.bin',
    )
    assert counter_bytes == bytes([0x10, 0x20, 0x01, 0x11])

    SymbolScope._global_scope = None
    _, coordinate_bytes = _assemble(
        tmp_path,
        '#define stack 5\n'
        'fn:\n'
        '#track stack\n'
        'push\n'
        '.x := COORDINATE(stack, 1)\n'
        'depth .x\n'
        'pop\n'
        '#endtrack stack\n',
        output_name='coordinate.bin',
    )
    assert coordinate_bytes == bytes([0x10, 0x20, 0x01, 0x11])

    # the COORDINATE() *offset* is a value expression: macros resolve there
    SymbolScope._global_scope = None
    _, offset_bytes = _assemble(
        tmp_path,
        '#define FRAMEOFF 1\n'
        'fn:\n'
        '#track stack\n'
        'push\n'
        '.x := COORDINATE(stack, FRAMEOFF)\n'
        'depth .x\n'
        'pop\n'
        '#endtrack stack\n',
        output_name='offset.bin',
    )
    assert offset_bytes == bytes([0x10, 0x20, 0x01, 0x11])


def test_m4_after_effect_return_mapping_counts_return_cost(tmp_path):
    """Pins the documented alternative for counting a return's own cost.

    With the unmapped-counter-cannot-cross-a-return rule, a cycles counter
    that must include the return instruction's cost maps the class on the
    return with ``after_effect``: the delta (and bounds/coordinate updates)
    apply first, then the exit contract is checked and the path ends.
    """
    config = _load_config()
    config['instructions']['rts']['flow_terminal']['cycles'] = 'after_effect'
    config_path = _write_config(tmp_path, config)

    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        '#track cycles exit=4\n'
        'nop\n'
        'rts\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0x00, 0x69])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\n'
        '#track cycles exit=5\n'
        'nop\n'
        'rts\n',
        'flow counter "cycles" exit mismatch: expected 5, actual 4',
        config_path=config_path,
        expected_line=4,
    )


def test_m4_macro_expansion_introduced_flow_names_stay_literal(tmp_path):
    """Names inside macro-*expanded* flow expressions are protected too.

    Bug: protection ran once, before expansion. If a macro value itself
    expanded to a flow expression, the recursive resolution then substituted
    the freshly introduced argument name (``#define stack 9`` →
    ``COUNTER(9)``), violating the context-universal literal-names rule.
    Resolution now re-protects after each expansion step until the text
    stabilizes.

    A source-level ``#define`` cannot carry a flow expression (the context
    validation rejects flow operators in preprocessor directives), but a
    command-line predefined symbol bypasses source validation entirely, so
    the expansion path is reachable in practice.
    """
    _, bytecode = _assemble(
        tmp_path,
        '#define stack 9\n'
        '#track stack\n'
        '#track cycles\n'
        'nop\n'
        '#set cycles = FLOW_VALUE + 1\n'
        '#assert cycles == 1\n'
        '#endtrack cycles\n'
        '#endtrack stack\n',
        predefined=['FLOW_VALUE=COUNTER(stack)'],
    )
    assert bytecode == bytes([0x00])


def test_m4_protection_sentinel_cannot_be_hijacked_by_user_macros(tmp_path):
    """The name-protection placeholder must not be a definable symbol.

    Bug: the placeholder was a valid preprocessor identifier
    (``__FLOW_PROTECTED_NAME_0``), so a user legally defining that symbol
    made the substitution rewrite the protected name (``COUNTER(stack)`` →
    ``COUNTER(9)``); plain-string restoration could also corrupt longer
    placeholders sharing a prefix. The placeholder now uses NUL-delimited
    text that can never lex as a preprocessor symbol and restores
    unambiguously.
    """
    _, bytecode = _assemble(
        tmp_path,
        '#define __FLOW_PROTECTED_NAME_0 9\n'
        '#track stack\n'
        'push\n'
        'depth COUNTER(stack)\n'
        'pop\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10, 0x20, 0x01, 0x11])


def test_m4_disabled_checks_still_reject_invalid_directive_values(tmp_path):
    """Disabling flow checks does not suppress invalid source values."""
    assembler = _assembler(
        tmp_path,
        '#define LOOP_A LOOP_B\n'
        '#define LOOP_B LOOP_A\n'
        '#track stack\n'
        '#set stack = LOOP_A\n'
        '#assert stack == LOOP_A\n'
        'nop\n'
        '#endtrack stack\n',
        flow_checks=False,
    )
    with pytest.raises(SystemExit, match='indirectly referring to itself'):
        assembler.assemble_bytecode()


def test_m4_macro_cycle_in_directive_value_errors_without_blowup(tmp_path):
    """A self-amplifying macro cycle must error via expansion-stack detection.

    Bug: the protecting resolver substituted layer-by-layer with a fixed
    100-layer cap instead of tracking the active expansion chain. A cycle
    like ``A → A+A`` doubles the text every layer, exhausting memory long
    before the cap. The resolver now mirrors the canonical expansion-stack
    cycle detection, erroring on the first self-reference.
    """
    assembler = _assembler(
        tmp_path,
        '#define DOUBLING DOUBLING+DOUBLING\n'
        '#track stack\n'
        '#set stack = DOUBLING\n'
        'nop\n'
        '#endtrack stack\n',
    )
    with pytest.raises(SystemExit, match='indirectly referring to itself'):
        assembler.assemble_bytecode()


def test_m4_long_macro_chains_keep_flow_name_protection(tmp_path):
    """Flow-name protection must hold for arbitrarily deep macro chains.

    Bug: past the resolver's 100-layer cap it fell back to the canonical
    resolver with no protection, so a 102-symbol chain ending in
    ``COUNTER(stack)`` resolved to ``COUNTER(9)`` when ``stack`` was
    ``#define``d. With expansion-stack resolution there is no cap: the chain
    resolves fully with the counter name literal.
    """
    chain_defines = ''.join(
        f'#define CHAIN_{i} CHAIN_{i + 1}\n' for i in range(101)
    )
    _, bytecode = _assemble(
        tmp_path,
        '#define stack 9\n'
        f'{chain_defines}'
        '#track stack\n'
        '#track cycles\n'
        'nop\n'
        '#set cycles = CHAIN_0 + 1\n'
        '#assert cycles == 1\n'
        '#endtrack cycles\n'
        '#endtrack stack\n',
        predefined=['CHAIN_101=COUNTER(stack)'],
    )
    assert bytecode == bytes([0x00])


# ---------------------------------------------------------------------------
# `#track min=`/`max=` instance bounds (0.8.0 release, cases 90-93)
# ---------------------------------------------------------------------------


def test_instance_max_errors_on_the_offending_instruction(tmp_path):
    """Case 90: ``#track stack max=2`` errors on the third push's line the
    moment the state exceeds the instance bound, exactly as a class
    ``max_value`` would.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack max=2\n'
        'push\n'
        'push\n'
        'push\n'
        'pop\npop\npop\n'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 3 exceeds maximum 2',
        expected_line=4,
    )


def test_instance_min_errors_on_the_offending_instruction(tmp_path):
    """Case 90: ``min=`` is symmetric — starting high via ``init=`` and
    popping below the instance minimum errors on the offending pop's line.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack init=4 min=2 exit=4\n'
        'pop\n'
        'pop\n'
        'pop\n'
        'push\npush\npush\n'
        '#endtrack stack\n',
        'flow counter "stack" underflow: value 1 is below minimum 2',
        expected_line=4,
    )


def test_instance_bound_accepts_address_label_expression(tmp_path):
    """Case 90: bound values accept every compile-time constant kind,
    including a memory-map-derived address-label expression resolved once at
    the ``#track``. The labels are address labels (not ``=`` constants), so
    resolution proves the analysis pass sees post-address-assignment values.
    """
    # positive half: lead_b - lead_a resolves to 2 and two pushes fit exactly
    _, bytecode = _assemble(
        tmp_path,
        'lead_a:\n'
        'nop\n'
        'nop\n'
        'lead_b:\n'
        '#track stack max=lead_b - lead_a\n'
        'push\n'
        'push\n'
        '#assert stack == 2\n'
        'pop\n'
        'pop\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x00, 0x00, 0x10, 0x10, 0x11, 0x11])

    # negative half: a third push exceeds the label-derived bound of 2
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        'lead_a:\n'
        'nop\n'
        'nop\n'
        'lead_b:\n'
        '#track stack max=lead_b - lead_a\n'
        'push\n'
        'push\n'
        'push\n'
        'pop\npop\npop\n'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 3 exceeds maximum 2',
        expected_line=8,
    )


def test_instance_max_tightens_class_max(tmp_path):
    """Case 91: with the class ``max_value`` of 32, ``#track stack max=8``
    enforces 8 — the ninth push errors against the instance bound, not the
    class bound.
    """
    pushes = 'push\n' * 9
    _assert_flow_error(
        tmp_path,
        '#track stack max=8\n'
        f'{pushes}'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 9 exceeds maximum 8',
        expected_line=10,
    )


def test_instance_max_looser_than_class_max_errors_on_track_line(tmp_path):
    """Case 91: an instance bound looser than the class bound is an error on
    the ``#track`` line naming both the instance and class bounds
    (tighten-only: a program must not claim more than the hardware provides).
    """
    _assert_flow_error(
        tmp_path,
        '#track stack max=100\n'
        'nop\n'
        '#endtrack stack\n',
        r'instance bound max=100 is looser than the class maximum 32',
        expected_line=1,
    )


def test_instance_min_looser_than_class_min_errors_on_track_line(tmp_path):
    """Case 91: symmetric for ``min=`` below the class ``min_value``."""
    _assert_flow_error(
        tmp_path,
        '#track stack min=-1\n'
        'nop\n'
        '#endtrack stack\n',
        r'instance bound min=-1 is looser than the class minimum 0',
        expected_line=1,
    )


def test_contradictory_instance_bounds_error_on_track_line(tmp_path):
    """An impossible effective interval is rejected directly on ``#track``."""
    _assert_flow_error(
        tmp_path,
        '#track stack init=4 min=5 max=4\n'
        'nop\n'
        '#endtrack stack\n',
        (
            'flow counter instance bounds are contradictory: '
            'effective minimum 5 exceeds effective maximum 4'
        ),
        expected_line=1,
    )


def test_instance_bound_contradicting_class_bound_errors_on_track_line(tmp_path):
    """A tightened instance minimum may not cross the class maximum."""
    _assert_flow_error(
        tmp_path,
        '#track stack init=33 min=33\n'
        'nop\n'
        '#endtrack stack\n',
        (
            'flow counter instance bounds are contradictory: '
            'effective minimum 33 exceeds effective maximum 32'
        ),
        expected_line=1,
    )


def test_instance_max_enforced_alone_on_class_without_max(tmp_path):
    """Case 91: on a class with no declared bound (``cycles`` has no
    ``max_value``), the instance bound is simply enforced.
    """
    _assert_flow_error(
        tmp_path,
        '#track cycles max=3\n'
        'push\n'
        'push\n'
        '#endtrack cycles\n',
        'flow counter "cycles" overflow: value 4 exceeds maximum 3',
        expected_line=3,
    )


def test_instance_bounds_enforced_at_set(tmp_path):
    """Case 92: ``#set`` beyond the instance bound errors even though the
    value is within the class bound.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack max=4\n'
        '#set stack = 5\n'
        'nop\n'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 5 exceeds maximum 4',
        expected_line=2,
    )


def test_instance_bounds_enforced_at_resume(tmp_path):
    """Case 92: ``#resume`` beyond the instance bound errors even though the
    value is within the class bound.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack max=4\n'
        '#suspend stack\n'
        'nop\n'
        '#resume stack = 5\n'
        'nop\n'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 5 exceeds maximum 4',
        expected_line=4,
    )


def test_instance_bounds_enforced_at_entry_root(tmp_path):
    """Case 92: an ``#entry`` root value beyond the instance bound errors at
    the ``#entry`` line (graph-mode root creation), even though the value is
    within the class bound.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack max=4\n'
        'jmp main\n'
        '#entry stack value=6\n'
        'alternate:\n'
        'pop\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 6 exceeds maximum 4',
        config_path=M5_CONFIG_PATH,
        expected_line=3,
    )


def test_instance_bounds_enforced_at_resolved_init(tmp_path):
    """Case 92: a resolved ``init=`` beyond the instance bound errors at the
    ``#track`` line itself.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack init=6 max=4\n'
        'nop\n'
        '#endtrack stack\n',
        'flow counter "stack" overflow: value 6 exceeds maximum 4',
        expected_line=1,
    )


def test_concurrent_instances_report_against_their_own_bounds(tmp_path):
    """Case 92: two concurrent instances of one class with different ``max=``
    values each report against their own bound — the third push overflows only
    the narrow instance while the wide one (at the same value) stays legal.
    """
    _assert_flow_error(
        tmp_path,
        '#track stack as=wide max=6\n'
        '#track stack as=narrow max=2\n'
        'push\n'
        'push\n'
        'push\n'
        'pop\npop\npop\n'
        '#endtrack narrow\n'
        '#endtrack wide\n',
        'flow counter "narrow" overflow: value 3 exceeds maximum 2',
        expected_line=5,
    )

    # positive half: after the narrow window closes, the wide instance may use
    # the depth the narrow bound forbade
    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        '#track stack as=wide max=6\n'
        '#track stack as=narrow max=2\n'
        'push\n'
        'push\n'
        'pop\n'
        'pop\n'
        '#endtrack narrow\n'
        'push\npush\npush\n'
        'pop\npop\npop\n'
        '#endtrack wide\n',
    )
    assert bytecode == bytes(
        [0x10, 0x10, 0x11, 0x11, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11]
    )


def test_instance_bound_violated_on_one_branch_of_a_diamond(tmp_path):
    """Cases 90/92 (graph mode): an instance ``max=`` violated on one branch
    of a diamond errors at the offending line, through the graph analyzer's
    per-path state handling. The identical source without the instance bound
    assembles cleanly against the class bound of 32.
    """
    diamond = (
        '#track stack{bound}\n'
        'routine:\n'
        'push\n'
        'jz .else_path\n'
        'push\n'
        'push\n'
        'pop\n'
        'pop\n'
        '.else_path:\n'
        'pop\n'
        '#endtrack stack\n'
    )
    _assert_flow_error(
        tmp_path,
        diamond.format(bound=' max=2'),
        'flow counter "stack" overflow: value 3 exceeds maximum 2',
        config_path=M5_CONFIG_PATH,
        expected_line=6,
    )

    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        diamond.format(bound=''),
        config_path=M5_CONFIG_PATH,
    )
    assert bytecode


def test_disabled_checks_do_not_enforce_instance_bounds(tmp_path):
    """Case 93: under ``--no-flow-checks`` instance bounds are not enforced.

    Even unresolvable values remain unused in annotation-only source, which
    assembles byte-identically to the stripped source with no flow diagnostics.
    """
    annotated, bytecode = _assemble(
        tmp_path,
        '#track stack min=UNDEFINED_LOW max=UNDEFINED_HIGH - ALSO_UNDEFINED\n'
        'push\n'
        'pop\n'
        '#endtrack stack\n',
        flow_checks=False,
        output_name='annotated-bounds.bin',
    )
    SymbolScope._global_scope = None
    _, stripped = _assemble(
        tmp_path,
        'push\n'
        'pop\n',
        flow_checks=False,
        output_name='stripped-bounds.bin',
    )
    assert bytecode == stripped == bytes([0x10, 0x11])
    assert not any(
        diagnostic.category == 'flow'
        for diagnostic in annotated.model.diagnostic_reporter.diagnostics
    )
