import pytest
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line.factory import (
    PreprocessorLineFactory,
)


@pytest.mark.parametrize(
    'instruction',
    [
        '#TRACK stack',
        '#ENDTRACK stack',
        '#ASSERT 1',
        '#SET stack = 0',
        '#SUSPEND stack',
        '#RESUME stack = 0',
        '#CREATE-SCOPE name',
        '#USE-SCOPE name',
        '#DEACTIVATE-SCOPE name',
        '#REQUIRE __LANGUAGE_VERSION_MAJOR__ >= 1',
        '#ERROR message',
        '#CREATE_MEMZONE name 0 1',
        '#DEFINE FLAG',
        '#PRINT "message"',
        '#IF 1',
        '#IFDEF FLAG',
        '#IFNDEF FLAG',
        '#ELIF 1',
        '#ELSE',
        '#ENDIF',
        '#MUTE',
        '#EMIT',
        '#UNMUTE',
    ],
)
def test_preprocessor_directive_dispatch_is_case_sensitive(instruction):
    line_objects = PreprocessorLineFactory.parse_line(
        LineIdentifier(1, 'case-sensitive-directive'),
        instruction,
        '',
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        0,
        '',
    )

    assert line_objects == []


def test_preprocessor_directive_dispatch_matches_complete_keyword():
    line_objects = PreprocessorLineFactory.parse_line(
        LineIdentifier(1, 'complete-directive-keyword'),
        '#elsewhere',
        '',
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        0,
        '',
    )

    assert line_objects == []
