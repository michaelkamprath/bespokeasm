"""Operand parsers and the forms an instruction writes in an enclosure, such as `(vec)`."""
import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand_parser import OperandParser
from bespokeasm.assembler.model.operand_parser import share_enclosed_forms
from bespokeasm.assembler.model.operand_set import OperandSetCollection

REGISTERS = {'x', 'y'}
BYTE = {'size': 8, 'word_align': True}
OPERAND_SETS = {
    'value': {'operand_values': {
        'abs': {'type': 'numeric', 'bytecode': {'value': 1, 'size': 8}, 'argument': BYTE},
    }},
    'indexed_indirect': {'operand_values': {
        'abs': {'type': 'numeric', 'bytecode': {'value': 1, 'size': 8}, 'argument': BYTE},
        'izx': {
            'type': 'indirect_indexed_numeric', 'enclosure': 'parentheses',
            'index_operands': {'x': {'type': 'register', 'register': 'x'}},
            'bytecode': {'value': 2, 'size': 8}, 'argument': BYTE,
        },
    }},
    'indirect': {'operand_values': {
        'ind': {'type': 'indirect_numeric', 'enclosure': 'parentheses', 'bytecode': {'value': 3, 'size': 8}, 'argument': BYTE},
    }},
    'indirect_or_deferred': {'operand_values': {
        'ind': {'type': 'indirect_numeric', 'enclosure': 'parentheses', 'bytecode': {'value': 3, 'size': 8}, 'argument': BYTE},
        'def': {'type': 'deferred_numeric', 'enclosure': 'parentheses', 'bytecode': {'value': 4, 'size': 8}, 'argument': BYTE},
    }},
    'bracketed': {'operand_values': {
        'ind': {'type': 'indirect_numeric', 'bytecode': {'value': 5, 'size': 8}, 'argument': BYTE},
    }},
    'y_register': {'operand_values': {'y': {'type': 'register', 'register': 'y'}}},
    'brace_indirect': {'operand_values': {
        'ind': {'type': 'indirect_numeric', 'enclosure': 'braces', 'bytecode': {'value': 6, 'size': 8}, 'argument': BYTE},
    }},
    'curly_relative': {'operand_values': {
        'rel': {'type': 'relative_address', 'use_curly_braces': True, 'bytecode': {'value': 7, 'size': 8},
                'argument': BYTE},
    }},
    'x_register': {'operand_values': {'x': {'type': 'register', 'register': 'x'}}},
}


@pytest.fixture
def make_parser():
    reporter = DiagnosticReporter()
    collection = OperandSetCollection(OPERAND_SETS, 'big', 'big', REGISTERS, 8, 8, reporter)

    def make(*operand_sets: str, specific: dict | None = None) -> OperandParser:
        config = {'count': len(operand_sets)}
        if operand_sets:
            config['operand_sets'] = {'list': list(operand_sets)}
        if specific is not None:
            config['specific_operands'] = specific
            config['count'] = len(next(iter(specific.values()))['list'])
        return OperandParser('op', config, collection, 'big', 'big', REGISTERS, 8, 8, reporter)
    return make


def _matched_ids(parser: OperandParser, *operands: str) -> list[str] | None:
    matched = parser.find_matching_operands(
        LineIdentifier(1, 'enclosures'), list(operands), REGISTERS, MemoryZoneManager(16, 0),
    )
    return None if matched is None else [parsed.operand.id for parsed in matched.operands]


def test_enclosed_forms_by_operand_count_and_position(make_parser):
    assert make_parser('value').enclosed_forms() == {}
    assert make_parser('indexed_indirect').enclosed_forms() == {(1, 0): {('parentheses', 1)}}
    assert make_parser('indirect_or_deferred', 'y_register').enclosed_forms() == {
        (2, 0): {('parentheses', 1), ('parentheses', 2)},
    }
    specific = {'pair': {'list': {
        'r': {'type': 'register', 'register': 'x'},
        'm': {'type': 'indirect_numeric', 'argument': BYTE},
    }}}
    assert make_parser(specific=specific).enclosed_forms() == {(2, 1): {('brackets', 1)}}


def test_enclosure_requirements(make_parser):
    parser = make_parser('indirect_or_deferred')
    assert parser.enclosure_requirements(['((vec))']) == [('parentheses', 2)]
    assert parser.enclosure_requirements(['((vec)+1)']) == [('parentheses', 1)]
    assert parser.enclosure_requirements(['(vec)']) == [('parentheses', 1)]
    assert parser.enclosure_requirements(['vec']) == [None]
    assert parser.enclosure_requirements(['(a)+(b)']) == [None]
    # A position is read only by the forms configured there, for that operand count.
    assert parser.enclosure_requirements(['(vec)', 'y']) == [None, None]
    assert make_parser('value').enclosure_requirements(['($10)']) == [None]


def test_a_whole_operand_enclosure_selects_the_enclosed_form(make_parser):
    parser = make_parser('indexed_indirect')
    assert _matched_ids(parser, '($10,x)') == ['izx']
    assert _matched_ids(parser, '$10') == ['abs']
    assert _matched_ids(parser, '($10+1)*2') == ['abs']
    # `($10)` would be `abs`, but parentheses around the operand mean indirect here.
    assert _matched_ids(parser, '($10)') is None
    # Without an enclosed form at the position, parentheses are grouping.
    assert _matched_ids(make_parser('value'), '($10)') == ['abs']


def test_the_deepest_configured_enclosure_wins(make_parser):
    both = make_parser('indirect_or_deferred')
    assert _matched_ids(both, '((vec))') == ['def']
    assert _matched_ids(both, '((vec)+1)') == ['ind']
    assert _matched_ids(both, '(vec)') == ['ind']
    # With no deferred form, `((vec))` is indirect, with `(vec)` inside.
    assert _matched_ids(make_parser('indirect'), '((vec))') == ['ind']


def test_disallowed_pairs_see_the_form_the_enclosure_selects(make_parser):
    parser = make_parser('indirect_or_deferred', 'y_register')
    parser._operand_sets_model._config['disallowed_pairs'] = [['def', 'y']]
    line_id, memzone = LineIdentifier(1, 'disallowed'), MemoryZoneManager(16, 0)
    # `((5))` is the deferred form, so `((5)), y` is the disallowed pair, not `ind, y`.
    assert _matched_ids(parser, '((5))', 'y') is None
    assert parser.disallowed_combination(line_id, ['((5))', 'y'], REGISTERS, memzone) == ['def', 'y']
    assert _matched_ids(parser, '(5)', 'y') == ['ind', 'y']


def test_an_enclosed_relative_address_is_an_enclosed_form(make_parser):
    """A relative address in braces counts as a braces form, so another variant's `{vec}` form
    at the same position doesn't shut it out."""
    assert make_parser('curly_relative').enclosed_forms() == {(1, 0): {('braces', 1)}}
    indirect = make_parser('brace_indirect', 'y_register')
    relative = make_parser('curly_relative', 'x_register')
    share_enclosed_forms([indirect, relative])
    assert _matched_ids(indirect, '{5}', 'y') == ['ind', 'y']
    assert _matched_ids(relative, '{5}', 'x') == ['rel', 'x']


def test_brackets_are_unaffected(make_parser):
    parser = make_parser('bracketed')
    assert parser.enclosure_requirements(['[vec]']) == [('brackets', 1)]
    assert _matched_ids(parser, '[vec]') == ['ind']
    assert _matched_ids(parser, '(vec)') is None


def test_specific_operands_follow_the_rule(make_parser):
    specific = {'one': {'list': {
        'abs': {'type': 'numeric', 'bytecode': {'value': 1, 'size': 8}, 'argument': BYTE},
        'y': {'type': 'register', 'register': 'y'},
    }}}
    parser = make_parser(specific=specific)
    assert _matched_ids(parser, '($10)', 'y') == ['abs', 'y']
    parser.use_instruction_enclosed_forms({(2, 0): {('parentheses', 1)}})
    assert _matched_ids(parser, '($10)', 'y') is None
    assert _matched_ids(parser, '$10', 'y') == ['abs', 'y']


def test_variants_share_their_enclosed_forms(make_parser):
    """`lda ($10)` must not select `lda $10` from one variant when another variant gives
    parentheses a meaning at that position."""
    absolute = make_parser('value')
    indexed = make_parser('indexed_indirect')
    assert _matched_ids(absolute, '($10)') == ['abs']
    share_enclosed_forms([absolute, None, indexed])
    assert _matched_ids(absolute, '($10)') is None
    assert _matched_ids(absolute, '$10') == ['abs']
    assert _matched_ids(indexed, '($10,x)') == ['izx']
