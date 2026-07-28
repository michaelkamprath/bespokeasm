import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.control_flow import ControlFlowGraph
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M5_CONFIG = PROJECT_ROOT / 'dev' / 'flow-counters-m5' / 'flow-counters-m5.yaml'


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
    static_analysis: bool = True,
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
        static_analysis=static_analysis,
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
        source_file=str(PROJECT_ROOT / 'dev' / 'flow-counters-m5' / 'branching-stack.asm'),
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
        static_analysis=True,
    )
    assembler.assemble_bytecode()


def test_m5_sample_tracks_different_counter_classes_concurrently(
    tmp_path,
    capsys,
):
    source = (
        PROJECT_ROOT
        / 'dev'
        / 'flow-counters-m5'
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
        PROJECT_ROOT
        / 'dev'
        / 'flow-counters-m5'
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
        PROJECT_ROOT
        / 'dev'
        / 'flow-counters-m5'
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
        PROJECT_ROOT
        / 'dev'
        / 'flow-counters-m5'
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
        'depth OFFSET(.argument)\n'
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
        'depth OFFSET(argument)\n'
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
        'depth OFFSET(argument)\n'
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
        static_analysis=False,
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
        'depth OFFSET(.slot)\n'
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
        'depth OFFSET(.argument)\n'
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
        if 'OFFSET(.argument)' in row[3]
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
    """A revisited expression records one diagnostic before emission stops."""
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
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'jz alternate\n'
        'jmp join\n'
        'alternate:\n'
        'nop\n'
        'join:\n'
        'depth OFFSET(.ghost)\n'
        'rts\n'
        '#endtrack stack\n',
    )

    with pytest.raises(
        RuntimeError,
        match='deferred flow expression reached numeric evaluation',
    ):
        assembler.assemble_bytecode()
    diagnostics = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if 'OFFSET(.ghost)' in diagnostic.message
    ]
    assert len(diagnostics) == 1


def test_m5_harness_is_runnable():
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    result = subprocess.run(
        [
            sys.executable,
            str(
                PROJECT_ROOT
                / 'dev'
                / 'flow-counters-m5'
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
