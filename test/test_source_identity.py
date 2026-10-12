"""Tests for the SourceIdentity class."""
import pytest
from bespokeasm.assembler.analysis import SourceIdentity
from bespokeasm.assembler.line_identifier import LineIdentifier


class TestSourceIdentity:
    """Test suite for SourceIdentity class."""

    def test_initialization_with_all_params(self):
        """Test SourceIdentity initialization with all parameters."""
        identity = SourceIdentity(
            filename='test.asm',
            line_number=42,
            line_object_ordinal=5,
            macro_path=(('push', 1), ('pop', 2)),
        )
        assert identity.filename == 'test.asm'
        assert identity.line_number == 42
        assert identity.line_object_ordinal == 5
        assert identity.macro_path == (('push', 1), ('pop', 2))

    def test_initialization_with_empty_macro_path(self):
        """Test SourceIdentity initialization with default empty macro_path."""
        identity = SourceIdentity(
            filename='test.asm',
            line_number=10,
            line_object_ordinal=0,
        )
        assert identity.filename == 'test.asm'
        assert identity.line_number == 10
        assert identity.line_object_ordinal == 0
        assert identity.macro_path == ()

    def test_initialization_with_none_filename(self):
        """Test SourceIdentity initialization with None filename."""
        identity = SourceIdentity(
            filename=None,
            line_number=100,
            line_object_ordinal=0,
        )
        assert identity.filename is None

    def test_from_line_id_with_line_identifier(self):
        """Test from_line_id() with a LineIdentifier."""
        line_id = LineIdentifier(50, 'test.asm')
        identity = SourceIdentity.from_line_id(line_id)
        assert identity.filename == 'test.asm'
        assert identity.line_number == 50
        assert identity.line_object_ordinal == 0

    def test_from_line_id_with_line_number_only(self):
        """Test from_line_id() with just a line number."""
        identity = SourceIdentity.from_line_id(75)
        assert identity.filename is None
        assert identity.line_number == 75

    def test_from_line_id_with_line_object_ordinal(self):
        """Test from_line_id() with line_object_ordinal parameter."""
        line_id = LineIdentifier(25, 'test.asm')
        identity = SourceIdentity.from_line_id(line_id, line_object_ordinal=3)
        assert identity.line_object_ordinal == 3

    def test_from_line_id_filename_none(self):
        """Test from_line_id() when line_id has no filename."""
        line_id = LineIdentifier(100)
        identity = SourceIdentity.from_line_id(line_id)
        assert identity.filename is None

    def test_macro_constituent_adds_to_path(self):
        """Test macro_constituent() adds an entry to the path."""
        initial_path = (('outer', 1),)
        identity = SourceIdentity(
            filename='test.asm',
            line_number=50,
            line_object_ordinal=0,
            macro_path=initial_path,
        )
        new_identity = identity.macro_constituent('inner', 2)
        assert new_identity.macro_path == (('outer', 1), ('inner', 2))

    def test_macro_constituent_returns_new_instance(self):
        """Test macro_constituent() returns a new instance."""
        identity = SourceIdentity(
            filename='test.asm',
            line_number=50,
            line_object_ordinal=0,
        )
        original_path = identity.macro_path
        new_identity = identity.macro_constituent('nested', 1)
        assert identity is not new_identity
        assert original_path == ()
        assert new_identity.macro_path == (('nested', 1),)

    def test_macro_constituent_preserves_other_fields(self):
        """Test macro_constituent() preserves other fields."""
        original = SourceIdentity(
            filename='test.asm',
            line_number=50,
            line_object_ordinal=3,
            macro_path=(('outer', 1),),
        )
        new = original.macro_constituent('inner', 2)
        assert new.filename == original.filename
        assert new.line_number == original.line_number
        assert new.line_object_ordinal == original.line_object_ordinal

    def test_macro_constituent_empty_initial_path(self):
        """Test macro_constituent() with empty initial path."""
        identity = SourceIdentity(
            filename='test.asm',
            line_number=50,
            line_object_ordinal=0,
        )
        new_identity = identity.macro_constituent('inner', 1)
        assert new_identity.macro_path == (('inner', 1),)

    def test_macro_constituent_multiple_calls_chain(self):
        """Test macro_constituent() can be called multiple times."""
        identity = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=0)
        new1 = identity.macro_constituent('level1', 1)
        new2 = new1.macro_constituent('level2', 2)
        new3 = new2.macro_constituent('level3', 3)
        assert new3.macro_path == (('level1', 1), ('level2', 2), ('level3', 3))

    def test_frozen_fields_immutability(self):
        """Test that SourceIdentity fields are immutable."""
        identity = SourceIdentity(
            filename='test.asm',
            line_number=50,
            line_object_ordinal=0,
        )
        with pytest.raises(AttributeError):
            identity.filename = 'new.asm'
        with pytest.raises(AttributeError):
            identity.line_number = 100

    def test_repr_string(self):
        """Test that repr() returns a reasonable string."""
        identity = SourceIdentity(
            filename='test.asm',
            line_number=50,
            line_object_ordinal=0,
        )
        repr_str = repr(identity)
        assert 'SourceIdentity' in repr_str
        assert 'test.asm' in repr_str

    def test_equality_same_values(self):
        """Test equality of instances with same values."""
        id1 = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=0)
        id2 = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=0)
        assert id1 == id2

    def test_inequality_different_values(self):
        """Test inequality of instances with different values."""
        id1 = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=0)
        id2 = SourceIdentity(filename='other.asm', line_number=50, line_object_ordinal=0)
        id3 = SourceIdentity(filename='test.asm', line_number=100, line_object_ordinal=0)
        id4 = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=1)
        assert id1 != id2
        assert id1 != id3
        assert id1 != id4

    def test_hash_equality(self):
        """Test that equal instances have the same hash."""
        id1 = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=0)
        id2 = SourceIdentity(filename='test.asm', line_number=50, line_object_ordinal=0)
        assert hash(id1) == hash(id2)
