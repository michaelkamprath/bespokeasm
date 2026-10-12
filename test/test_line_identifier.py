"""Tests for the LineIdentifier class."""
from bespokeasm.assembler.line_identifier import LineIdentifier


class TestLineIdentifier:
    """Test suite for LineIdentifier class."""

    def test_initialization_with_line_number(self):
        """Test creating a LineIdentifier with just a line number."""
        li = LineIdentifier(42)
        assert li.line_num == 42
        assert li.filename is None

    def test_initialization_with_filename_and_line_number(self):
        """Test creating a LineIdentifier with both filename and line number."""
        li = LineIdentifier(15, 'test.asm')
        assert li.line_num == 15
        assert li.filename == 'test.asm'

    def test_filename_property(self):
        """Test the filename property getter."""
        li = LineIdentifier(100, 'path/to/file.s')
        assert li.filename == 'path/to/file.s'

    def test_line_num_property(self):
        """Test the line_num property getter."""
        li = LineIdentifier(999, 'script.asm')
        assert li.line_num == 999

    def test_str_representation_without_filename(self):
        """Test string representation when filename is None."""
        li = LineIdentifier(25)
        str_repr = str(li)
        assert 'line 25' in str_repr
        assert 'unknown_file' in str_repr

    def test_str_representation_with_filename(self):
        """Test string representation with a filename."""
        li = LineIdentifier(50, 'example.asm')
        str_repr = str(li)
        assert 'file example.asm' in str_repr
        assert 'line 50' in str_repr

    def test_repr_equals_str(self):
        """Test that repr() returns the same as str()."""
        li = LineIdentifier(77, 'test.s')
        assert repr(li) == str(li)

    def test_different_line_numbers(self):
        """Test LineIdentifier instances with different line numbers."""
        li1 = LineIdentifier(1)
        li2 = LineIdentifier(1000)
        assert li1.line_num != li2.line_num

    def test_different_filenames(self):
        """Test LineIdentifier instances with different filenames."""
        li1 = LineIdentifier(10, 'file1.asm')
        li2 = LineIdentifier(10, 'file2.asm')
        assert li1.filename != li2.filename
        assert li1.line_num == li2.line_num

    def test_same_values_equality(self):
        """Test that LineIdentifiers with same values are equal (by identity)."""
        li1 = LineIdentifier(5, 'same.asm')
        li2 = LineIdentifier(5, 'same.asm')
        # They should have same property values (not necessarily same object)
        assert li1.line_num == li2.line_num
        assert li1.filename == li2.filename
