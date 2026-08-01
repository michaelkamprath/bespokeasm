import copy
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.control_flow import ControlFlowGraph
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M5_DIR = PROJECT_ROOT / 'test' / 'flow_harnesses' / 'm5'
M5_CONFIG = M5_DIR / 'flow-counters-m5.yaml'
INTEL_8085_CONFIG = PROJECT_ROOT / 'examples' / 'intel-8085' / 'intel-8085.yaml'
MINIMAL_64X4_CONFIG = (
    PROJECT_ROOT
    / 'examples'
    / 'slu4-minimal-64x4'
    / 'slu4-minimal-64x4.yaml'
)


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config_path: Path = M5_CONFIG,
    pretty: bool = False,
    warnings_as_errors: bool = False,
    flow_checks: bool = True,
) -> Assembler:
    source_path = tmp_path / 'm5.asm'
    source_path.write_text(source)
    return Assembler(
        source_file=str(source_path),
        config_file=str(config_path),
        generate_binary=True,
        output_file=str(tmp_path / 'm5.bin'),
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=pretty,
        pretty_print_format='listing' if pretty else None,
        pretty_print_output='stdout' if pretty else None,
        is_verbose=0,
        include_paths=[str(tmp_path)],
        predefined=[],
        warnings_as_errors=warnings_as_errors,
        flow_checks=flow_checks,
    )


def _assemble(
    tmp_path: Path,
    source: str,
    **assembler_kwargs,
) -> tuple[Assembler, bytes]:
    assembler = _assembler(tmp_path, source, **assembler_kwargs)
    assembler.assemble_bytecode()
    return assembler, (tmp_path / 'm5.bin').read_bytes()


def _flow_error(tmp_path: Path, source: str, expected: str):
    assembler = _assembler(tmp_path, source)
    with pytest.raises(SystemExit, match=expected):
        assembler.assemble_bytecode()
    assert assembler.model.diagnostic_reporter.diagnostics[-1].category == 'flow'


def test_m5_branching_sample_has_separate_balanced_exits():
    assembler = Assembler(
        source_file=str(M5_DIR / 'branching-stack.asm'),
        config_file=str(M5_CONFIG),
        generate_binary=False,
        output_file=None,
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=False,
        pretty_print_format=None,
        pretty_print_output=None,
        is_verbose=0,
        include_paths=[],
        predefined=[],
        flow_checks=True,
    )
    assembler.assemble_bytecode()


def test_no_flow_checks_resolves_offset_without_listing_column(
    tmp_path,
    capsys,
):
    _, bytecode = _assemble(
        tmp_path,
        'function:\n'
        '#track stack\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        '.byte .slot\n'
        'pop\n'
        '#endtrack stack\n',
        pretty=True,
        flow_checks=False,
    )
    listing = capsys.readouterr().out

    assert bytecode == bytes([0x10, 0x01, 0x11])
    assert '| flow ' not in listing
    assert 'stack=' not in listing


def test_no_flow_checks_suppresses_assertion_and_exit_verification(
    tmp_path,
):
    _, bytecode = _assemble(
        tmp_path,
        'function:\n'
        '#track stack exit=0\n'
        'push\n'
        '.byte COUNTER(stack)\n'
        '#assert stack == 999 "verification-only failure"\n'
        '#endtrack stack\n',
        flow_checks=False,
    )

    assert bytecode == bytes([0x10, 0x01])


def test_m5_sample_tracks_different_counter_classes_concurrently(
    tmp_path,
    capsys,
):
    source = (
        M5_DIR
        / 'concurrent-counters.asm'
    ).read_text()
    assembler = _assembler(tmp_path, source, pretty=True)
    assembler.assemble_bytecode()
    bytecode = (tmp_path / 'm5.bin').read_bytes()
    listing = capsys.readouterr().out

    assert bytecode[6] == 3
    assert bytecode[10] == 2
    listing_rows = [
        line.split('|')
        for line in listing.splitlines()
        if '|' in line
    ]
    push_index = next(
        index for index, row in enumerate(listing_rows)
        if len(row) > 3 and row[3].strip() == 'push'
    )
    assert listing_rows[push_index][4].strip() == 'stack=0 → 1'
    writes_row = listing_rows[push_index + 1]
    assert all(not field.strip() for field in writes_row[:4])
    assert writes_row[4].strip() == 'writes=0 → 1'
    assert not writes_row[5].strip()


def test_m5_sample_aggregates_macro_constituent_transitions(
    tmp_path,
    capsys,
):
    source = (
        M5_DIR
        / 'macro-stack.asm'
    ).read_text()
    assembler = _assembler(tmp_path, source, pretty=True)
    assembler.assemble_bytecode()
    listing = capsys.readouterr().out

    assert (tmp_path / 'm5.bin').read_bytes() == bytes([
        0x10, 0x10, 0x10,
        0x11, 0x11, 0x11,
        0x69,
    ])
    listing_rows = [
        line.split('|')
        for line in listing.splitlines()
        if line.startswith(' ') and '|' in line
    ]
    macro_row = next(
        row for row in listing_rows
        if 'push_three' in row[3]
    )
    assert macro_row[4].strip() == 'stack=0 → 3'


def test_m5_listing_shares_byte_and_flow_continuation_row(
    tmp_path,
    capsys,
):
    source = (
        M5_DIR
        / 'macro-shared-continuation.asm'
    ).read_text()
    assembler = _assembler(tmp_path, source, pretty=True)
    assembler.assemble_bytecode()
    listing_rows = [
        line.split('|')
        for line in capsys.readouterr().out.splitlines()
        if '|' in line
    ]

    macro_index = next(
        index for index, row in enumerate(listing_rows)
        if len(row) > 3 and row[3].strip() == 'push_seven'
    )
    macro_row = listing_rows[macro_index]
    continuation_row = listing_rows[macro_index + 1]
    assert macro_row[2].strip() == '10 10 10 10 10 10'
    assert macro_row[4].strip() == 'stack=0 → 7'
    assert not continuation_row[0].strip()
    assert not continuation_row[1].strip()
    assert continuation_row[2].strip() == '10'
    assert not continuation_row[3].strip()
    assert continuation_row[4].strip() == 'writes=0 → 7'
    assert not continuation_row[5].strip()


def test_m5_sample_counts_equal_clock_cycles_across_branch(tmp_path):
    source = (
        M5_DIR
        / 'cycle-counting.asm'
    ).read_text()
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([
        0x30, 0x05,
        0x00,
        0x31, 0x08,
        0x00, 0x00, 0x00,
        0x69,
    ])


def test_m5_join_mismatch_names_both_values(tmp_path):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz .alternate_path\n'
        'push\n'
        'jmp .join\n'
        '.alternate_path:\n'
        'nop\n'
        '.join:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    with pytest.raises(
        SystemExit,
        match=r'join mismatch.*1.*versus.*0|join mismatch.*0.*versus.*1',
    ):
        assembler.assemble_bytecode()
    message = assembler.model.diagnostic_reporter.diagnostics[-1].message
    assert 'line 5' in message
    assert 'line 7' in message


def test_m5_separate_terminal_path_detects_push_leak(tmp_path):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz .leak\n'
        'rts\n'
        '.leak:\n'
        'push\n'
        'rts\n'
        '#endtrack stack\n',
    )
    with pytest.raises(
        SystemExit,
        match=r'exit mismatch: expected 0, actual 1',
    ):
        assembler.assemble_bytecode()
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert 'branch at' in diagnostic.message
    assert 'line 3' in diagnostic.message
    assert '(taken)' in diagnostic.message


def test_m5_net_zero_and_net_positive_loops(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '.loop:\n'
        'push\n'
        'pop\n'
        'jz .loop\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode

    SymbolScope._global_scope = None
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '.loop:\n'
        'push\n'
        'jz .loop\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'join mismatch',
    )


def test_m5_unreachable_flow_value_after_jump_errors(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jmp .done\n'
        'depth COUNTER(stack)\n'
        '.done:\n'
        'rts\n'
        '#endtrack stack\n',
        'unreachable after flow counter "stack" terminated',
    )


def test_m5_call_summary_preserves_caller_visible_depth(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '.argument := COORDINATE(stack, 3)\n'
        'call callee\n'
        'depth .argument\n'
        'rts\n'
        '#endtrack stack\n'
        'callee:\n'
        'rts\n',
    )
    assert bytecode[3] == 3


def test_m5_call_without_summary_leaves_value_unresolved(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'call_unknown callee\n'
        'depth COUNTER(stack)\n'
        'rts\n'
        '#endtrack stack\n'
        'callee:\n'
        'rts\n',
        'no caller-visible summary',
    )


def test_m5_nonzero_target_independent_call_summary_is_applied(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        'push\n'
        'call_net_minus_one callee\n'
        'rts\n'
        '#endtrack stack\n'
        'callee:\n'
        'rts\n',
    )
    assert bytecode


def test_m5_call_to_external_address_uses_declared_summary(tmp_path):
    """A call target outside the assembled program is a legitimate external
    callee (e.g. a ROM routine named by a predefined constant): the declared
    ``flow_call_effects`` summary governs the caller-visible effect, and the
    callee body is not the analyzer's to verify."""
    _, bytecode = _assemble(
        tmp_path,
        'ROM_PRINT = $c0\n'
        '#track stack\n'
        'routine:\n'
        '.argument := COORDINATE(stack, 3)\n'
        'call ROM_PRINT\n'
        'depth .argument\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode[3] == 3


def test_m5_macro_argument_coordinate_resolves_at_invocation_entry(tmp_path):
    """A macro invocation behaves like a single instruction: a coordinate
    passed as a macro argument observes the stack as it stood at the call,
    for every constituent — even when the macro's own constituents move the
    counter in between (the ``phs4s``-style push-compensation pattern). The
    coordinate spelling must therefore emit exactly the bytes of the
    equivalent hand-written constant spelling."""
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    # Mirrors a real stack-copy macro: read a stack byte, push it, then read
    # the next byte whose spelled offset pre-compensates for that push.
    config['macros']['probe_pair'] = {
        'variants': [{
            'operands': {'count': 1, 'operand_sets': {'list': ['value']}},
            'instructions': [
                'depth @ARG(0)+1+0',
                'push',
                'depth @ARG(0)+0+1',
                'push',
            ],
        }],
    }
    config_path = tmp_path / 'macro-coordinate.yaml'
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)

    source_template = (
        '#track stack mode=called\n'
        'routine:\n'
        '.argument := COORDINATE(stack, 3)\n'
        'push\n'
        'probe_pair {operand}\n'
        'pop\n'
        'pop\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n'
    )
    _, coordinate_bytes = _assemble(
        tmp_path,
        source_template.format(operand='.argument'),
        config_path=config_path,
    )
    SymbolScope._global_scope = None
    _, constant_bytes = _assemble(
        tmp_path,
        source_template.format(operand='(3+1)'),
        config_path=config_path,
    )
    assert coordinate_bytes == constant_bytes
    # both depth constituents observe the invocation-entry offset (4) plus
    # the macro's own +1 compensation arithmetic; layout is
    # push, depth, operand, push, depth, operand, ...
    assert coordinate_bytes[2] == 5
    assert coordinate_bytes[5] == 5


def test_m5_call_to_hard_coded_in_program_address_is_valid(tmp_path):
    """A numeric call target inside the assembled program resolves to the
    instruction at that address exactly like a label target would — code
    lined up at a fixed address (an interrupt vector, say) may be called by
    its number. Layout: call(2) + depth(2) + rts(1) puts ``callee`` at 5."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '.argument := COORDINATE(stack, 3)\n'
        'call 5\n'
        'depth .argument\n'
        'rts\n'
        '#endtrack stack\n'
        'callee:\n'
        'rts\n',
    )
    assert bytecode[1] == 5
    assert bytecode[3] == 3


def test_m5_call_into_emitted_data_is_still_an_error(tmp_path):
    """An address the program does emit — but as data — remains an invalid
    call target; only content-free addresses are treated as external."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'call table\n'
        'rts\n'
        '#endtrack stack\n'
        'table:\n'
        '.byte 1, 2, 3\n',
        'enters emitted data',
    )


def test_m5_call_may_target_region_entry_but_not_its_interior(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        'caller:\n'
        'call callee\n'
        'rts\n'
        '#endtrack stack\n'
        '#track stack mode=called\n'
        'callee:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode

    SymbolScope._global_scope = None
    _flow_error(
        tmp_path,
        '#track stack mode=called\n'
        'caller:\n'
        'call middle\n'
        'rts\n'
        '#endtrack stack\n'
        '#track stack mode=called\n'
        'callee:\n'
        'push\n'
        'middle:\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'call target enters flow counter region "stack" at non-entry label',
    )


def test_m5_indirect_transfer_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'ijmp\n'
        '#endtrack stack\n',
        'indirect control transfer',
    )

    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '#suspend stack\n'
        '#endtrack stack\n'
        'ijmp\n',
    )
    assert bytecode


def test_m5_branch_cannot_cross_endtrack(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jmp outside\n'
        '#endtrack stack\n'
        'outside:\n'
        'nop\n',
        'control flow leaves flow counter region',
    )

    SymbolScope._global_scope = None
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jmp 2\n'
        '#endtrack stack\n'
        'nop\n',
        'control flow leaves flow counter region',
    )


def test_m5_explicit_entry_roots_an_unreachable_label(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'jmp main\n'
        '#entry stack value=1\n'
        'alternate:\n'
        'pop\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode


def test_m5_initial_value_entry_preserves_entry_coordinates(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'argument := COORDINATE(stack, 3)\n'
        'jmp main\n'
        '#entry stack value=0\n'
        'alternate:\n'
        'depth argument\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode[3] == 3


def test_m5_noninitial_entry_invalidates_prior_coordinates(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'argument := COORDINATE(stack, 3)\n'
        'jmp main\n'
        '#entry stack value=1\n'
        'alternate:\n'
        'depth argument\n'
        'pop\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
        'invalid because its saved position was crossed',
    )


def test_m5_disabled_analysis_strips_entry_declarations(tmp_path):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        '#entry stack value=UNRESOLVED_WHILE_DISABLED\n'
        'alternate:\n'
        'nop\n'
        '#endtrack stack\n',
        flow_checks=False,
    )
    assembler.assemble_bytecode()
    assert (tmp_path / 'm5.bin').read_bytes() == bytes([0])
    assert not assembler.model.diagnostic_reporter.diagnostics


def test_m5_value_less_entry_reuses_unique_incoming_value(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz alternate\n'
        'jmp done\n'
        '#entry stack\n'
        'alternate:\n'
        'nop\n'
        'done:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode


def test_m5_unreachable_value_less_entry_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jmp main\n'
        '#entry stack\n'
        'alternate:\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
        'is unreachable; value= is required',
    )


def test_m5_value_less_entry_rejects_conflicting_incoming_states(
    tmp_path,
):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jz alternate\n'
        'push\n'
        'jmp shared\n'
        'alternate:\n'
        'nop\n'
        '#entry stack\n'
        'shared:\n'
        'rts\n'
        '#endtrack stack\n',
        'join mismatch',
    )


def test_m5_value_less_entry_can_be_reached_from_explicit_entry(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'jmp main\n'
        '#entry stack value=0\n'
        'alternate:\n'
        'jmp shared\n'
        '#entry stack\n'
        'shared:\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode


def test_m5_grouped_entries_root_concurrent_counters(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        '#track cycles\n'
        'jmp main\n'
        '#entry stack value=0\n'
        '#entry cycles value=2\n'
        'alternate:\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack cycles\n'
        '#endtrack stack\n',
    )
    assert bytecode


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        (
            '#track stack\n'
            '#entry stack value=0\n'
            '#entry stack value=0\n'
            'alternate:\n'
            'rts\n',
            'duplicate #entry',
        ),
        (
            '#track stack\n'
            '#entry stack value=0\n'
            'nop\n'
            'alternate:\n'
            'rts\n',
            'followed by the next compilable address label',
        ),
        (
            '#track stack\n'
            '#entry stack value=0\n',
            'followed by the next compilable address label',
        ),
    ],
)
def test_m5_entry_group_validation(tmp_path, source, expected):
    _flow_error(tmp_path, source, expected)


def test_m5_entry_group_allows_blank_and_comment_lines_before_label(
    tmp_path,
):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'jmp main\n'
        '#entry stack value=0\n'
        '; the entry convention applies to the next compilable label\n'
        '\n'
        'alternate:\n'
        'rts\n'
        'main:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode


def test_m5_coordinate_invalid_on_one_path_stays_invalid_after_join(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'nop\n'
        'push\n'
        '.slot := COORDINATE(stack, 0)\n'
        'jz .preserve\n'
        'pop\n'
        'push\n'
        'jmp .join\n'
        '.preserve:\n'
        'nop\n'
        '.join:\n'
        'depth .slot\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'invalid because its saved position was crossed',
    )


def test_m5_suspended_runtime_length_loop_can_be_reanchored(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '#suspend stack\n'
        '.loop:\n'
        'push\n'
        'jz .loop\n'
        '#resume stack = 0\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode


def test_m5_suspended_paths_ignore_call_effects_at_join(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '#suspend stack\n'
        'jz .alternate\n'
        'call_unknown callee\n'
        'jmp .join\n'
        '.alternate:\n'
        'nop\n'
        '.join:\n'
        '#resume stack = 0\n'
        'rts\n'
        '#endtrack stack\n'
        'callee:\n'
        'rts\n',
    )
    assert bytecode


def test_m5_set_can_explicitly_reconcile_branch_states(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz .alternate\n'
        'push\n'
        '#set stack = 0\n'
        'jmp .join\n'
        '.alternate:\n'
        'nop\n'
        '.join:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode


def test_m5_fallthrough_into_data_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jz done\n'
        'nop\n'
        '.byte 0\n'
        'done:\n'
        'rts\n'
        '#endtrack stack\n',
        'fall-through.*enters emitted data',
    )


def test_m5_branch_free_fallthrough_into_data_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'push\n'
        '.byte $ee\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'fall-through.*enters emitted data',
    )


def test_m5_symbolic_branch_targeting_data_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jz table\n'
        'rts\n'
        'table:\n'
        '.byte $ee\n'
        '#endtrack stack\n',
        'target.*enters emitted data',
    )


def test_m5_ambiguous_same_address_fallthrough_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '.org 1\n'
        'nop\n'
        '.org 1\n'
        'nop\n'
        '.org 0\n'
        '#track stack\n'
        'nop\n'
        '#endtrack stack\n',
        'physical fall-through.*multiple executable nodes',
    )


def test_m5_label_or_number_branch_target_prefers_existing_label(
    tmp_path,
    monkeypatch,
):
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    config['general']['default_numeric_base'] = 'hex'
    config_path = tmp_path / 'hex-default.yaml'
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)

    resolved_labels = []
    original_label_named = ControlFlowGraph.label_named

    def recording_label_named(self, label, address):
        resolved_labels.append((label, address))
        return original_label_named(self, label, address)

    monkeypatch.setattr(
        ControlFlowGraph,
        'label_named',
        recording_label_named,
    )
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'jmp face\n'
        'face:\n'
        'rts\n'
        '#endtrack stack\n',
        config_path=config_path,
    )

    assert bytecode
    assert ('face', 2) in resolved_labels


def test_m5_branch_cannot_cross_an_org_closed_region(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jz done\n'
        'nop\n'
        '.org 10\n'
        'done:\n'
        'nop\n',
        'leaves flow counter region "stack"',
    )


def test_m5_org_auto_closes_balanced_region_with_flow_warning(tmp_path):
    assembler, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'push\n'
        'pop\n'
        '.org 10\n'
        'nop\n',
    )

    assert bytecode
    warnings = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.level == 'warning'
    ]
    assert len(warnings) == 1
    assert '.org auto-closes flow counter region "stack"' in warnings[0].message
    assert warnings[0].category == 'flow'


def test_m5_branch_free_fallthrough_uses_physical_not_source_order(
    tmp_path,
):
    _flow_error(
        tmp_path,
        '.org 2\n'
        'outside_region:\n'
        'nop\n'
        '.org 0\n'
        '#track stack\n'
        'push\n'
        'nop\n'
        '#endtrack stack\n',
        'leaves flow counter region "stack"',
    )


def test_m5_live_graph_path_reaching_eof_is_rejected(tmp_path):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jz done\n'
        'nop\n'
        'done:\n'
        'nop\n',
        'reaches EOF without a flow terminal or #endtrack',
    )


def test_m5_graph_mode_flow_value_after_endtrack_reports_inactive(
    tmp_path,
):
    _flow_error(
        tmp_path,
        '#track stack\n'
        'jz done\n'
        'done:\n'
        '#endtrack stack\n'
        'depth COUNTER(stack)\n',
        'COUNTER\\(stack\\) references inactive flow counter "stack"',
    )


def test_m5_branch_cannot_enter_after_track(tmp_path):
    _flow_error(
        tmp_path,
        'jmp inside\n'
        '#track stack\n'
        'inside:\n'
        'rts\n'
        '#endtrack stack\n',
        'enters flow counter region "stack" after #track stack',
    )


def test_m5_balanced_tail_call_closes_before_jump(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        'push\n'
        'pop\n'
        '#endtrack stack exit=0\n'
        'jmp callee\n'
        'callee:\n'
        'rts\n',
    )
    assert bytecode

    SymbolScope._global_scope = None
    _flow_error(
        tmp_path,
        '#track stack mode=called\n'
        'push\n'
        '#endtrack stack exit=0\n'
        'jmp callee\n'
        'callee:\n'
        'rts\n',
        'exit mismatch',
    )


def test_m5_terminal_paths_may_end_at_eof_without_endtrack(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz .alternate\n'
        'rts\n'
        '.alternate:\n'
        'rts\n',
    )
    assert bytecode


def test_m5_external_label_warning_and_lexical_endtrack_suppression(
    tmp_path,
):
    assembler, _ = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'rts\n'
        'next_routine:\n'
        'nop\n',
    )
    warnings = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.level == 'warning'
    ]
    assert len(warnings) == 1
    assert 'unreachable potential entry' in warnings[0].message
    assert warnings[0].category == 'flow'

    SymbolScope._global_scope = None
    assembler, _ = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'rts\n'
        '#endtrack stack\n'
        'next_routine:\n'
        'nop\n',
    )
    assert not assembler.model.diagnostic_reporter.diagnostics


def test_m5_external_label_warning_escalates(tmp_path):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        'middle:\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        warnings_as_errors=True,
    )
    with pytest.raises(SystemExit, match='potential external entry'):
        assembler.assemble_bytecode()


def test_m5_listing_shows_transitions_and_omits_unchanged_state(
    tmp_path,
    capsys,
):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'nop\n'
        'push\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        pretty=True,
    )
    assembler.assemble_bytecode()
    listing = capsys.readouterr().out
    assert ' flow ' in listing
    assert 'stack=entry → 0' in listing
    assert 'stack=0 → 1' in listing
    assert 'stack=1 → 0' in listing
    assert 'stack=0 → exit' in listing

    listing_rows = [
        line.split('|')
        for line in listing.splitlines()
        if line.startswith(' ') and '|' in line
    ]
    nop_row = next(row for row in listing_rows if 'nop' in row[3])
    assert not nop_row[4].strip()


def test_m5_listing_omits_flow_column_when_analysis_is_disabled(
    tmp_path,
    capsys,
):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'push\n'
        'pop\n'
        '#endtrack stack\n',
        pretty=True,
        flow_checks=False,
    )
    assembler.assemble_bytecode()
    listing = capsys.readouterr().out

    header = next(
        line
        for line in listing.splitlines()
        if 'line' in line and 'instruction' in line and 'comment' in line
    )
    assert 'flow' not in header
    assert 'stack=' not in listing


def test_m5_listing_omits_flow_column_for_source_without_flow_use(
    tmp_path,
    capsys,
    monkeypatch,
):
    """A flow-capable ISA compiling source that never uses flow counters
    behaves like --no-flow-checks: the analysis pass does not run at all and
    the listing retains the pre-feature layout with no flow column."""
    from bespokeasm.assembler.flow_analysis import FlowGraphAnalyzer

    def unexpected_run(self, line_objects):
        raise AssertionError(
            'flow analysis ran for source with no flow constructs'
        )

    monkeypatch.setattr(FlowGraphAnalyzer, 'run', unexpected_run)
    assembler = _assembler(
        tmp_path,
        'routine:\n'
        'push\n'
        'pop\n'
        'rts\n',
        pretty=True,
    )
    assembler.assemble_bytecode()
    listing = capsys.readouterr().out

    header = next(
        line
        for line in listing.splitlines()
        if 'line' in line and 'instruction' in line and 'comment' in line
    )
    assert 'flow' not in header
    assert 'stack=' not in listing


def test_m5_listing_shows_declared_and_resolved_coordinate_offsets(
    tmp_path,
    capsys,
):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        '.argument := COORDINATE(stack, 3)\n'
        'push\n'
        'depth .argument\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        pretty=True,
    )
    assembler.assemble_bytecode()
    listing_rows = [
        line.split('|')
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(' ') and '|' in line
    ]

    declaration_row = next(
        row for row in listing_rows
        if 'COORDINATE(stack, 3)' in row[3]
    )
    offset_row = next(
        row for row in listing_rows
        if 'depth .argument' in row[3]
    )
    assert declaration_row[4].strip() == '.argument=3'
    assert offset_row[4].strip() == '.argument=4'


def test_m5_many_balanced_diamonds_do_not_enumerate_paths(tmp_path):
    diamonds = []
    for index in range(40):
        diamonds.extend([
            f'jz .alternate_{index}',
            'nop',
            f'jmp .join_{index}',
            f'.alternate_{index}:',
            'nop',
            f'.join_{index}:',
        ])
    source = (
        '#track stack\n'
        'routine:\n'
        + '\n'.join(diamonds)
        + '\nrts\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode


def test_m5_graph_error_paths_survive_a_nonfatal_diagnostic_reporter(
    tmp_path,
    monkeypatch,
):
    """Graph diagnostics must guard invalid state even if reporting returns."""
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

    original_error = DiagnosticReporter.error

    def nonfatal_error(
        self,
        line_id,
        message,
        category='user',
        color=None,
    ):
        try:
            original_error(
                self,
                line_id,
                message,
                category=category,
                color=color,
            )
        except SystemExit:
            pass

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)

    scenarios = [
        (
            'duplicate-region',
            '#track stack\n'
            '#track stack\n'
            'rts\n'
            '#endtrack stack\n',
        ),
        (
            'orphan-endtrack',
            '#endtrack stack\n'
            'nop\n',
        ),
        (
            'entry-without-label',
            '#track stack\n'
            '#entry stack value=0\n'
            'nop\n'
            '#endtrack stack\n',
        ),
        (
            'unreachable-value-less-entry',
            '#track stack\n'
            'jmp main\n'
            '#entry stack\n'
            'alternate:\n'
            'rts\n'
            'main:\n'
            'rts\n'
            '#endtrack stack\n',
        ),
        (
            'invalid-entry-value',
            '#track stack\n'
            'jmp main\n'
            '#entry stack value=UNKNOWN\n'
            'alternate:\n'
            'rts\n'
            'main:\n'
            'rts\n'
            '#endtrack stack\n',
        ),
        (
            'symbolic-data-target',
            '#track stack\n'
            'jz table\n'
            'rts\n'
            'table:\n'
            '.byte $ee\n'
            '#endtrack stack\n',
        ),
        (
            # Acceptance 94: contradictory effective instance bounds error
            # directly on the #track line and must guard-and-return without
            # opening a half-initialized region.
            'contradictory-instance-bounds',
            '#track stack min=10 max=5\n'
            'nop\n'
            '#endtrack stack\n',
        ),
        (
            # Acceptance 95: a precise read after a watched write reports
            # the invalidation and analysis continues to the #resume.
            'read-after-watched-write',
            '#track stack\n'
            'push\n'
            'write_addr 255\n'
            '#assert stack == 1\n'
            '#resume stack = 1\n'
            'pop\n'
            'rts\n'
            '#endtrack stack\n',
        ),
    ]
    for name, source in scenarios:
        SymbolScope._global_scope = None
        assembler = _assembler(tmp_path, source)
        assembler.assemble_bytecode()
        assert any(
            diagnostic.category == 'flow'
            and diagnostic.level == 'error'
            for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        ), f'scenario {name} recorded no flow error'


def test_m5_nonfatal_worklist_reports_unresolved_offset_once(
    tmp_path,
    monkeypatch,
):
    """A revisited coordinate reference records one diagnostic, not one per path."""
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

    original_error = DiagnosticReporter.error

    def nonfatal_error(
        self,
        line_id,
        message,
        category='user',
        color=None,
    ):
        try:
            original_error(
                self,
                line_id,
                message,
                category=category,
                color=color,
            )
        except SystemExit:
            pass

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)
    # `ghost` belongs to the first, ended tracking instance; the reference at
    # the join is reached from both branch paths, so the worklist visits the
    # node twice and must still report the stale-instance error once.
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'first:\n'
        'push\n'
        'ghost := COORDINATE(stack, 1)\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n'
        '#track stack\n'
        'routine:\n'
        'jz alternate\n'
        'jmp join\n'
        'alternate:\n'
        'nop\n'
        'join:\n'
        'depth ghost\n'
        'rts\n'
        '#endtrack stack\n',
    )

    assembler.assemble_bytecode()
    diagnostics = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if 'earlier tracking instance' in diagnostic.message
    ]
    assert len(diagnostics) == 1


def test_watched_write_address_makes_counter_indeterminate(tmp_path, capsys):
    """A real instruction selected through a macro invalidates its counter."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        'reset_stack\n'
        '#resume stack = 0\n'
        '#assert stack == 0\n'
        '#endtrack stack\n',
        pretty=True,
    )
    listing = capsys.readouterr().out

    assert bytecode == bytes([0x10, 0x13, 0xff])
    reset_row = next(
        row
        for row in listing.splitlines()
        if 'reset_stack' in row
    )
    assert 'stack=1 → ?' in reset_row


def test_nonwatched_write_address_keeps_counter_precise(tmp_path):
    """A compile-time write proven not to alias the anchor changes no state."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'push\n'
        'write_addr 254\n'
        '#assert stack == 1\n'
        'pop\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10, 0x13, 0xfe, 0x11])


def test_runtime_write_address_conservatively_invalidates_counter(tmp_path):
    """A run-time write target may alias the watched anchor address."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'push\n'
        'write_runtime_addr pointer\n'
        '#resume stack = 0\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10, 0x14, 0x00])


def test_direct_instruction_invalidation_requires_explicit_resume(
    tmp_path,
    capsys,
):
    """An instruction can replace an anchor without a memory-write target."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        'reset_stack_direct\n'
        '#resume stack = 0\n'
        '#assert stack == 0\n'
        '#endtrack stack\n',
        pretty=True,
    )
    listing = capsys.readouterr().out

    assert bytecode == bytes([0x10, 0x15])
    reset_row = next(
        row
        for row in listing.splitlines()
        if 'reset_stack_direct' in row
    )
    assert 'stack=1 → ?' in reset_row


def test_direct_instruction_invalidation_blocks_precise_read(tmp_path):
    """Acceptance 95/99: the direct form blocks reads and names its cause."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'push\n'
        'replace_stack_anchor\n'
        '#assert stack == 1\n'
        '#endtrack stack\n',
        'indeterminate since instruction "replace_stack_anchor" at file .*, '
        'line 3',
    )


def test_direct_invalidation_counts_as_counter_metadata_producer(tmp_path):
    """A class used only by ``flow_invalidates`` is not falsely inert."""
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    config['flow_counters']['reset_only'] = {
        'unknown_instructions': 'error',
        'exit_policy': 'balanced',
    }
    config['instructions']['replace_stack_anchor']['flow_invalidates'].append(
        'reset_only'
    )
    config_path = tmp_path / 'direct-producer.yaml'
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)

    _, bytecode = _assemble(
        tmp_path,
        '#track reset_only\n'
        'replace_stack_anchor\n'
        '#endtrack reset_only\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0x15])


@pytest.mark.parametrize(
    ('instruction', 'expected_bytes'),
    [
        ('lxi sp, 0xf000', bytes([0xc5, 0x31, 0x00, 0xf0])),
        ('sphl', bytes([0xc5, 0xf9])),
    ],
)
def test_intel_8085_stack_pointer_replacement_can_be_reanchored(
    tmp_path,
    capsys,
    instruction,
    expected_bytes,
):
    """The real 8085 SP-replacement forms implement direct invalidation."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'probe:\n'
        'push b\n'
        f'{instruction}\n'
        '#resume stack = 0\n'
        '#endtrack stack\n',
        config_path=INTEL_8085_CONFIG,
        pretty=True,
    )
    listing = capsys.readouterr().out

    assert bytecode == expected_bytes
    instruction_row = next(
        row
        for row in listing.splitlines()
        if instruction in row
    )
    assert 'stack=2 → ?' in instruction_row


def test_minimal_64x4_flow_stack_demo_compiles():
    """The original Minimal 64x4 example exercises its real stack contract."""
    assembler = Assembler(
        source_file=str(
            PROJECT_ROOT
            / 'examples'
            / 'slu4-minimal-64x4'
            / 'software'
            / 'flow-stack-demo.min64x4'
        ),
        config_file=str(MINIMAL_64X4_CONFIG),
        generate_binary=False,
        output_file=None,
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=False,
        pretty_print_format=None,
        pretty_print_output=None,
        is_verbose=0,
        include_paths=[],
        predefined=[],
        flow_checks=True,
    )

    assembler.assemble_bytecode()


def test_minimal_64x4_spinit_macro_invalidates_and_can_be_reanchored(
    tmp_path,
    capsys,
):
    """The SP-initialization macro inherits its concrete watched write."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'phs\n'
        'spinit\n'
        '#resume stack = 0\n'
        '#endtrack stack\n',
        config_path=MINIMAL_64X4_CONFIG,
        pretty=True,
    )
    listing = capsys.readouterr().out

    assert bytecode == bytes([0x6a, 0x83, 0xfe, 0xff, 0xff])
    spinit_row = next(
        row
        for row in listing.splitlines()
        if '|' in row and 'spinit' in row
    )
    assert 'stack=1 → ?' in spinit_row


def test_watched_write_requires_resume_before_precise_read(tmp_path):
    """Acceptance 95: a read after a watched write names the write as cause."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'push\n'
        'reset_stack\n'
        '#assert stack == 1\n'
        '#endtrack stack\n',
        'indeterminate since the write to 0xff at file .*, line 3; '
        '#resume with a known value is required',
    )


def test_watched_write_permanently_invalidates_existing_coordinates(tmp_path):
    """Re-anchoring cannot resurrect slots from before a watched write."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        'reset_stack\n'
        '#resume stack = 0\n'
        'observe .slot\n'
        '#endtrack stack\n',
        'counter coordinate ".slot" is invalid',
    )


def test_graph_invalidation_on_one_branch_is_a_join_mismatch(tmp_path):
    """Acceptance 95: a diamond invalidated on one arm cannot join cleanly.

    The invalidated arm arrives suspended while the clean arm arrives with a
    precise value, which is exactly a join mismatch.
    """
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz .alternate\n'
        'write_addr 255\n'
        'jmp .join\n'
        '.alternate:\n'
        'nop\n'
        '.join:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    with pytest.raises(SystemExit, match='join mismatch'):
        assembler.assemble_bytecode()
    message = assembler.model.diagnostic_reporter.diagnostics[-1].message
    assert 'suspended' in message
    assert '0' in message


def test_graph_invalidation_on_both_branches_joins_cleanly(tmp_path):
    """Acceptance 95: both arms invalidated join cleanly; #resume then works.

    The two arms carry different invalidation provenance (different source
    lines); the join must still be clean and pick one deterministically.
    """
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        'jz .alternate\n'
        'write_addr 255\n'
        'jmp .join\n'
        '.alternate:\n'
        'write_addr 255\n'
        '.join:\n'
        '#resume stack = 1\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([
        0x10,
        0x30, 0x07,
        0x13, 0xff,
        0x31, 0x09,
        0x13, 0xff,
        0x11,
        0x69,
    ])


def test_graph_macro_watched_write_invalidates_inside_branch(tmp_path):
    """Acceptance 95/97: a macro-expanded watched write invalidates one arm.

    The macro carries no flow metadata of its own; its constituent watched
    write must have the same graph-mode result as writing the instruction
    directly, observed here as a join mismatch against the clean arm.
    """
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'jz .alternate\n'
        'reset_stack\n'
        'jmp .join\n'
        '.alternate:\n'
        'nop\n'
        '.join:\n'
        'rts\n'
        '#endtrack stack\n',
    )
    with pytest.raises(SystemExit, match='join mismatch'):
        assembler.assemble_bytecode()


def test_graph_resume_then_redeclared_coordinate_resolves(tmp_path):
    """Acceptance 95: after #resume a fresh coordinate declaration works."""
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.old := COORDINATE(stack, 1)\n'
        'write_addr 255\n'
        '#resume stack = 1\n'
        '.new := COORDINATE(stack, 1)\n'
        'depth .new\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10, 0x13, 0xff, 0x20, 0x01, 0x11, 0x69])


def test_graph_resume_then_redeclaration_leaves_old_coordinate_dead(tmp_path):
    """Acceptance 95: redeclaring at the same depth resurrects nothing."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.old := COORDINATE(stack, 1)\n'
        'write_addr 255\n'
        '#resume stack = 1\n'
        '.new := COORDINATE(stack, 1)\n'
        'observe .old\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'counter coordinate ".old" is invalid',
    )


def test_case_99_invalidates_every_active_instance_of_the_class(
    tmp_path,
    capsys,
):
    """Acceptance 99: both ``as=`` instances of the class become indeterminate.

    An active instance of a different class tracked over the same
    instructions stays precise through the invalidation.
    """
    assembler, bytecode = _assemble(
        tmp_path,
        '#track stack as=first\n'
        '#track stack as=second\n'
        '#track cycles\n'
        'routine:\n'
        'push\n'
        'replace_stack_anchor\n'
        '#assert cycles == 4\n'
        '#resume first = 0\n'
        '#resume second = 0\n'
        'nop\n'
        '#endtrack cycles\n'
        '#endtrack second\n'
        '#endtrack first\n',
        pretty=True,
    )
    listing = capsys.readouterr().out

    assert bytecode == bytes([0x10, 0x15, 0x00])
    assert 'first=1 → ?' in listing
    assert 'second=1 → ?' in listing
    assert 'cycles=2 → 4' in listing
    assert not [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.category == 'flow'
    ]


def test_operations_on_invalidated_counter_report_provenance(tmp_path):
    """Acceptance 95: every indeterminate-state diagnostic names the cause.

    ``#suspend`` keeps its explicit-suspension wording; these sites fire only
    when the indeterminacy was caused by invalidation, so each diagnostic
    must identify the invalidating write (or instruction) and its line.
    """
    provenance = 'indeterminate since the write to 0xff at file .*, line 3'
    scenarios = [
        (
            'counter-read',
            'depth COUNTER(stack)\n',
            f'COUNTER\\(stack\\) cannot be resolved while flow counter '
            f'"stack" is {provenance}',
        ),
        (
            'coordinate-declaration',
            '.slot := COORDINATE(stack, 1)\n',
            f'COORDINATE\\(stack, ...\\) cannot declare a coordinate while '
            f'the counter is {provenance}',
        ),
        (
            'set-directive',
            '#set stack = 0\n',
            f'flow counter "stack" is {provenance}; '
            '#resume with a known value is required',
        ),
        (
            'terminal',
            'rts\n',
            f'flow terminal "rts" cannot reconcile flow counter "stack": '
            f'{provenance}',
        ),
    ]
    for name, operation, expected in scenarios:
        SymbolScope._global_scope = None
        _flow_error(
            tmp_path,
            '#track stack\n'
            'routine:\n'
            'reset_stack\n'
            + operation
            + '#resume stack = 0\n'
            'rts\n'
            '#endtrack stack\n',
            expected,
        ), f'scenario {name}'


def test_suspend_on_invalidated_counter_reports_already_indeterminate(
    tmp_path,
):
    """Acceptance 95: ``#suspend`` after invalidation names the true cause."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        'reset_stack\n'
        '#suspend stack\n'
        '#resume stack = 0\n'
        'rts\n'
        '#endtrack stack\n',
        'flow counter "stack" is already indeterminate since the write to '
        '0xff at file .*, line 4',
    )


def test_endtrack_without_exit_on_invalidated_counter_warns(tmp_path):
    """Invalidation-caused indeterminacy at ``#endtrack`` is surfaced.

    An explicit ``#suspend`` before ``#endtrack`` is a deliberate programmer
    acknowledgement and stays silent, but a counter left indeterminate by an
    anchor invalidation has an unchecked exit contract the programmer never
    acknowledged, so the close receives a ``flow`` warning naming the cause.
    """
    assembler, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'push\n'
        'reset_stack\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10, 0x13, 0xff])
    warnings = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.level == 'warning' and diagnostic.category == 'flow'
    ]
    assert len(warnings) == 1
    assert re.search(
        'exit contract not checked: flow counter "stack" indeterminate '
        'since the write to 0xff at file .*, line 3',
        warnings[0].message,
    )


def test_endtrack_warning_on_invalidated_counter_escalates(tmp_path):
    """The invalidated-``#endtrack`` warning escalates under -w."""
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'push\n'
        'reset_stack\n'
        '#endtrack stack\n',
        warnings_as_errors=True,
    )
    with pytest.raises(
        SystemExit,
        match='exit contract not checked: flow counter "stack" indeterminate',
    ):
        assembler.assemble_bytecode()
    assert assembler.model.diagnostic_reporter.diagnostics[-1].category == 'flow'


def test_endtrack_after_explicit_suspend_stays_silent(tmp_path):
    """A deliberate ``#suspend`` before ``#endtrack`` produces no warning."""
    assembler, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        'push\n'
        '#suspend stack\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10])
    assert not [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.category == 'flow'
    ]


def test_endtrack_with_exit_on_invalidated_counter_still_errors(tmp_path):
    """``exit=`` on an indeterminate counter remains a hard error."""
    _flow_error(
        tmp_path,
        '#track stack\n'
        'push\n'
        'reset_stack\n'
        '#endtrack stack exit=0\n',
        'cannot check exit= while the counter is suspended',
    )


def test_watched_write_during_explicit_suspend_still_invalidates(tmp_path):
    """Acceptance 95: a watched write inside a ``#suspend`` span still counts.

    The counter is already indeterminate, so the write changes nothing the
    programmer can read immediately — but the invalidation must still be
    recorded (permanently invalid coordinates plus provenance) rather than
    early-returned past. The observable pinned here is the diagnostic for a
    read between the write and ``#resume``: it must identify the watched
    write as the cause instead of reporting only the explicit suspension.
    """
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.x := COORDINATE(stack, 1)\n'
        '#suspend stack\n'
        'write_addr 255\n'
        'depth .x\n'
        '#resume stack = 1\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'indeterminate since the write to 0xff at file',
    )


def test_watched_write_during_explicit_suspend_kills_coordinates_forever(
    tmp_path,
):
    """Acceptance 95: coordinates crossed by a suspended-span watched write die.

    Today this scenario also fails because ``#resume`` itself permanently
    invalidates every coordinate, so the test cannot distinguish the two
    paths end-to-end. It is pinned anyway as future-proofing: if ``#resume``
    ever gains a stronger slot-preservation contract that keeps coordinates
    alive, a watched write during the explicit suspension must still have
    marked them permanently invalid before that contract could apply.
    """
    _flow_error(
        tmp_path,
        '#track stack\n'
        'routine:\n'
        'push\n'
        '.x := COORDINATE(stack, 1)\n'
        '#suspend stack\n'
        'write_addr 255\n'
        '#resume stack = 1\n'
        'depth .x\n'
        'pop\n'
        'rts\n'
        '#endtrack stack\n',
        'counter coordinate ".x" is invalid',
    )


@pytest.mark.parametrize(
    ('mutation', 'expected'),
    [
        (
            lambda config: config['flow_counters']['stack'].__setitem__(
                'invalidate_on_write',
                '255',
            ),
            'invalidate_on_write must be a list of addresses',
        ),
        (
            lambda config: config['flow_counters']['stack'].__setitem__(
                'invalidate_on_write',
                [256],
            ),
            'invalidate_on_write address 256 is outside',
        ),
        (
            lambda config: config['flow_counters']['stack'].__setitem__(
                'invalidate_on_write',
                [255, 255],
            ),
            'invalidate_on_write contains duplicate address 255',
        ),
        (
            lambda config: config['instructions']['write_addr'].__setitem__(
                'flow_write_operands',
                [1],
            ),
            'flow_write_operands index 1 is outside',
        ),
        (
            lambda config: config['instructions']['write_addr'].__setitem__(
                'flow_write_operands',
                [0, 0],
            ),
            'flow_write_operands contains duplicate index 0',
        ),
        (
            lambda config: config['instructions']['replace_stack_anchor'].__setitem__(
                'flow_invalidates',
                'stack',
            ),
            'flow_invalidates must be a list of counter classes',
        ),
        (
            lambda config: config['instructions']['replace_stack_anchor'].__setitem__(
                'flow_invalidates',
                ['missing'],
            ),
            'flow_invalidates names undeclared counter "missing"',
        ),
        (
            lambda config: config['instructions']['replace_stack_anchor'].__setitem__(
                'flow_invalidates',
                ['stack', 'stack'],
            ),
            'flow_invalidates contains duplicate counter "stack"',
        ),
    ],
)
def test_watched_write_configuration_validation(
    tmp_path,
    mutation,
    expected,
):
    """Malformed watched-address metadata fails at configuration load."""
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    mutation(config)
    config_path = tmp_path / 'invalid-write-watch.yaml'
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)

    with pytest.raises(SystemExit, match=expected):
        _assembler(tmp_path, 'nop\n', config_path=config_path)


def test_watched_write_configuration_is_validated_without_checks(tmp_path):
    """Disabling checks does not make an invalid ISA configuration valid."""
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    config['flow_counters']['stack']['invalidate_on_write'] = 'not a list'
    config['instructions']['write_addr']['flow_write_operands'] = 'not a list'
    config['instructions']['replace_stack_anchor']['flow_invalidates'] = 'not a list'
    config_path = tmp_path / 'ignored-write-watch.yaml'
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)

    with pytest.raises(SystemExit, match='must be a list of addresses'):
        _assembler(
            tmp_path,
            'nop\n',
            config_path=config_path,
            flow_checks=False,
        )


_WRITE_OPERAND_MUTATIONS = [
    (
        'non-list',
        lambda config: config['instructions']['write_addr'].__setitem__(
            'flow_write_operands',
            'not a list',
        ),
        'flow_write_operands must be a list of source operand indexes',
    ),
    (
        'negative-index',
        lambda config: config['instructions']['write_addr'].__setitem__(
            'flow_write_operands',
            [-1],
        ),
        'flow_write_operands index -1 is outside',
    ),
    (
        'boolean-entry',
        lambda config: config['instructions']['write_addr'].__setitem__(
            'flow_write_operands',
            [True],
        ),
        'flow_write_operands entries must be integer source operand indexes',
    ),
    (
        'operandless-instruction',
        lambda config: config['instructions']['push'].__setitem__(
            'flow_write_operands',
            [0],
        ),
        'flow_write_operands index 0 is outside',
    ),
]


def _mutated_m5_config(tmp_path: Path, mutation, name: str) -> Path:
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    mutation(config)
    config_path = tmp_path / name
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)
    return config_path


@pytest.mark.parametrize(
    ('mutation', 'expected'),
    [
        (mutation, expected)
        for _, mutation, expected in _WRITE_OPERAND_MUTATIONS
    ],
    ids=[name for name, _, _ in _WRITE_OPERAND_MUTATIONS],
)
def test_flow_write_operand_validation_fails_config_load_as_flow(
    tmp_path,
    monkeypatch,
    mutation,
    expected,
):
    """Acceptance 98: malformed ``flow_write_operands`` is a flow config error."""
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
    config_path = _mutated_m5_config(tmp_path, mutation, 'invalid.yaml')

    AssemblerModel(str(config_path), 0, DiagnosticReporter())

    assert any(
        expected in message and category == 'flow'
        for message, category in diagnostics
    ), diagnostics


@pytest.mark.parametrize(
    'mutation',
    [mutation for _, mutation, _ in _WRITE_OPERAND_MUTATIONS],
    ids=[name for name, _, _ in _WRITE_OPERAND_MUTATIONS],
)
def test_flow_write_operand_validation_remains_active_without_checks(
    tmp_path,
    mutation,
):
    """Disabling checks does not suppress flow metadata validation."""
    config_path = _mutated_m5_config(tmp_path, mutation, 'ignored.yaml')

    with pytest.raises(SystemExit, match='flow_write_operands'):
        _assembler(
            tmp_path,
            'nop\n',
            config_path=config_path,
            flow_checks=False,
        )


def test_watched_class_with_write_operand_producer_is_not_inert(tmp_path):
    """Acceptance 53/95: watched addresses plus any write-operand producer.

    A class whose only producer is its ``invalidate_on_write`` addresses
    paired with some instruction's ``flow_write_operands`` can genuinely be
    invalidated, so it is trackable rather than declared-but-inert.
    """
    config_path = _mutated_m5_config(
        tmp_path,
        lambda config: config['flow_counters'].__setitem__(
            'watch_only',
            {
                'invalidate_on_write': [254],
                'unknown_instructions': 'ignore',
                'exit_policy': 'balanced',
            },
        ),
        'watch-only.yaml',
    )

    _, bytecode = _assemble(
        tmp_path,
        '#track watch_only\n'
        'nop\n'
        '#endtrack watch_only\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0])


def test_watched_class_without_any_write_operand_producer_is_inert(tmp_path):
    """Acceptance 53: watched addresses alone cannot make a class trackable.

    With no instruction anywhere declaring ``flow_write_operands``, the
    watched addresses can never match a write, so the class has no producer
    and ``#track`` reports the declared-but-inert error.
    """
    def mutation(config):
        config['flow_counters']['watch_only'] = {
            'invalidate_on_write': [254],
            'unknown_instructions': 'ignore',
            'exit_policy': 'balanced',
        }
        for instruction_config in config['instructions'].values():
            instruction_config.pop('flow_write_operands', None)

    config_path = _mutated_m5_config(tmp_path, mutation, 'inert-watch.yaml')
    assembler = _assembler(
        tmp_path,
        '#track watch_only\n'
        'nop\n'
        '#endtrack watch_only\n',
        config_path=config_path,
    )

    with pytest.raises(
        SystemExit,
        match='flow counter class "watch_only" is inert',
    ):
        assembler.assemble_bytecode()
    assert assembler.model.diagnostic_reporter.diagnostics[-1].category == 'flow'


@pytest.mark.parametrize('metadata_key', ['flow_write_operands', 'flow_invalidates'])
def test_instruction_macro_cannot_declare_invalidation_metadata(
    tmp_path,
    metadata_key,
):
    """Macros derive invalidation only from their concrete expansion."""
    yaml = YAML(typ='safe')
    with M5_CONFIG.open() as config_file:
        config = copy.deepcopy(yaml.load(config_file))
    config['macros']['reset_stack'][metadata_key] = [0]
    config_path = tmp_path / 'macro-write-watch.yaml'
    writer = YAML()
    with config_path.open('w') as config_file:
        writer.dump(config, config_file)

    with pytest.raises(
        SystemExit,
        match=(
            'macros.reset_stack may not declare instruction flow metadata '
            f'"{metadata_key}"'
        ),
    ):
        _assembler(tmp_path, 'nop\n', config_path=config_path)


def test_m5_harness_is_runnable():
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    result = subprocess.run(
        [
            sys.executable,
            str(
                M5_DIR
                / 'verify_m5.py'
            ),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'M5 development acceptance: PASS' in result.stdout
