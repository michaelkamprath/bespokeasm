import pytest
from bespokeasm.assembler.parsing import encloses_whole
from bespokeasm.assembler.parsing import enclosure_depth
from bespokeasm.assembler.parsing import split_operands
from bespokeasm.assembler.parsing import top_level_indexes


@pytest.mark.parametrize(('text', 'expected'), [
    ('a, b', ['a', 'b']),
    ('($10,x)', ['($10,x)']),
    ('($10),y', ['($10)', 'y']),
    ('[hl + 1], (a, b)', ['[hl + 1]', '(a, b)']),
    ("',', 2", ["','", '2']),
    ('', []),
])
def test_split_operands_keeps_enclosed_commas_together(text, expected):
    assert split_operands(text) == expected


@pytest.mark.parametrize(('text', 'expected'), [
    ('$1234 +[a+6]', [6]),
    ('1 + 2 + (3+4)', [2, 6]),
    ("'+' + {b+1}", [4]),
    ("'\\'' + 1", [5]),
    ('[a+1]', []),
])
def test_top_level_indexes_skip_quoted_and_enclosed_characters(text, expected):
    assert top_level_indexes(text, '+') == expected


@pytest.mark.parametrize(('text', 'expected'), [
    ('(vec)', True),
    ('((a+1)*2)', True),
    ('($10,x)', True),
    ("(')')", True),             # a quoted parenthesis doesn't count
    ('(a)+(b)', False),          # the first pair closes before the end
    ('(a+1)*2', False),
    ('(a', False),
    ('a)', False),
    ('()', True),
    ('(', False),
    ('vec', False),
])
def test_encloses_whole(text, expected):
    assert encloses_whole(text, '(', ')') is expected


def test_encloses_whole_takes_the_enclosure_to_check():
    assert encloses_whole('[vec]', '[', ']')
    assert not encloses_whole('[vec]', '(', ')')
    assert not encloses_whole('(vec)', '[', ']')


@pytest.mark.parametrize(('text', 'expected'), [
    ('((vec))', 2),
    ('( ( vec ) )', 2),
    ('((vec)+1)', 1),
    ('(vec)', 1),
    ('(a)+(b)', 0),
    ('vec', 0),
    ('  (vec)  ', 1),
])
def test_enclosure_depth(text, expected):
    assert enclosure_depth(text, '(', ')') == expected
