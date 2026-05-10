import io
import unittest

from bespokeasm.assembler.bytecode.packed_bits import PackedBits
from bespokeasm.utilities import convert_disallowed_pairs_to_flow_style
from bespokeasm.utilities import dump_yaml_with_formatting
from bespokeasm.utilities import FlowStyleList
from bespokeasm.utilities import FormatPreservedInt
from bespokeasm.utilities import is_explicit_numeric_string
from bespokeasm.utilities import is_string_numeric
from bespokeasm.utilities import is_unprefixed_numeric_string
from bespokeasm.utilities import load_yaml_with_format_preservation
from bespokeasm.utilities import normalize_default_numeric_base
from bespokeasm.utilities import parse_numeric_string


class TestUtilities(unittest.TestCase):
    def test_parse_numeric_string(self):
        self.assertEqual(parse_numeric_string('1234'), 1234, 'straight integer test: 1234')
        self.assertEqual(parse_numeric_string('$4d2'), 1234, '$hex integer test: 1234')
        self.assertEqual(parse_numeric_string('0x4d2'), 1234, '0x hex integer test: 1234')
        self.assertEqual(parse_numeric_string('b0000010011010010'), 1234, 'binary integer test: 1234')
        self.assertEqual(parse_numeric_string('-1212'), -1212, 'signed interger: -1212')
        self.assertEqual(parse_numeric_string('%10011001'), 0x99, 'binary interger: 0x99')
        self.assertEqual(parse_numeric_string("'1'"), 49, 'character ordinal: \'1\' = 49')
        self.assertEqual(parse_numeric_string('b10011001'), 0x99, 'binary interger: 0x99')
        self.assertEqual(parse_numeric_string("' '"), 32, 'character ordinal: \' \' = 32')
        self.assertEqual(parse_numeric_string("'\\''"), 39, 'character ordinal: \'\\\'\' = 39')

        with self.assertRaises(ValueError, msg='only integer numeric values are supported'):
            parse_numeric_string('nan')
        with self.assertRaises(ValueError, msg='only integer numeric values are supported'):
            parse_numeric_string('')

    def test_is_string_numeric(self):
        self.assertTrue(is_string_numeric('8675309'), 'string is numeric')
        self.assertTrue(is_string_numeric('0x845FED'), 'string is numeric')
        self.assertTrue(is_string_numeric('$845FED'), 'string is numeric')
        self.assertTrue(is_string_numeric('b10000100111111101101'), 'string is numeric')
        self.assertFalse(is_string_numeric('Jenny'), 'string is not numeric')
        self.assertFalse(is_string_numeric('test1'), 'string is not numeric')
        self.assertFalse(is_string_numeric(' '), 'string is not numeric')
        self.assertFalse(is_string_numeric('%01234567'), 'binary integers can only have 1s and 0s')
        self.assertFalse(is_string_numeric('b'), 'the prefix b alone is not numeric')
        self.assertFalse(is_string_numeric('$'), 'the prefix alon is not numeric')
        self.assertTrue(is_string_numeric('08FH'), 'string is numeric (hexadecimal)')
        self.assertTrue(is_string_numeric("'1'"), 'string is numeric (character ordinal)')
        self.assertTrue(is_string_numeric("'\\''"), 'escaped single quote ordinal is numeric')
        self.assertFalse(is_string_numeric("'12'"), 'character ordinal can only be one character long')
        self.assertFalse(is_string_numeric('0b10011001'), 'binary numbers do not strt with "0b"')

    def test_default_numeric_base_helpers(self):
        self.assertEqual(parse_numeric_string('f', 'hex'), 15, 'bare hex digit uses configured base')
        self.assertEqual(parse_numeric_string('1F', 'hex'), 31, 'multi-digit bare hex uses configured base')
        self.assertEqual(parse_numeric_string('face', 'hex'), 0xFACE, 'bare hex words use configured base')
        self.assertEqual(parse_numeric_string('17', 'octal'), 15, 'bare octal uses configured base')
        self.assertEqual(parse_numeric_string('1010', 'binary'), 10, 'bare binary uses configured base')
        self.assertEqual(parse_numeric_string('-f', 'hex'), -15, 'signed bare hex uses configured base')
        self.assertTrue(is_string_numeric('face', 'hex'), 'hex mode accepts bare hex words')
        self.assertFalse(is_string_numeric('8', 'octal'), 'octal mode rejects invalid octal digits')
        self.assertFalse(is_string_numeric('2', 'binary'), 'binary mode rejects invalid binary digits')

    def test_normalize_default_numeric_base(self):
        """Resolve base names/aliases: None->decimal, case-insensitive, aliases collapse, unknown raises."""
        self.assertEqual(normalize_default_numeric_base(None), 'decimal', 'None defaults to decimal')
        self.assertEqual(normalize_default_numeric_base('Hex'), 'hex', 'case-insensitive normalization')
        self.assertEqual(normalize_default_numeric_base('hexadecimal'), 'hex', 'aliases resolve to canonical name')
        self.assertEqual(normalize_default_numeric_base('  base16  '), 'hex', 'surrounding whitespace tolerated')
        with self.assertRaises(ValueError):
            normalize_default_numeric_base('bogus')

    def test_is_explicit_numeric_string_whitespace(self):
        """is_explicit_numeric_string treats whitespace-only and empty inputs as non-numeric."""
        self.assertFalse(is_explicit_numeric_string('   '), 'whitespace-only is not numeric')
        self.assertFalse(is_explicit_numeric_string(''), 'empty string is not explicit numeric')
        self.assertTrue(is_explicit_numeric_string('0xFF'), 'explicit hex is recognized')

    def test_is_unprefixed_numeric_string_whitespace(self):
        """is_unprefixed_numeric_string treats whitespace-only and empty inputs as non-numeric."""
        self.assertFalse(is_unprefixed_numeric_string('   '), 'whitespace-only is not numeric')
        self.assertFalse(is_unprefixed_numeric_string(''), 'empty string is not unprefixed numeric')
        self.assertTrue(is_unprefixed_numeric_string('123'), 'unprefixed decimal is recognized')

    def test_parse_numeric_string_error_paths(self):
        """parse_numeric_string raises ValueError for sign-only, multi-char ordinals, malformed literals, etc."""
        # Empty after stripping a sign character.
        with self.assertRaises(ValueError):
            parse_numeric_string('+')
        with self.assertRaises(ValueError):
            parse_numeric_string('-')
        # Multi-character "character ordinal" is invalid.
        with self.assertRaises(ValueError):
            parse_numeric_string("'ab'")
        # Malformed character literal that fails the regex (unterminated quote).
        with self.assertRaises(ValueError):
            parse_numeric_string("'a")
        # Empty character literal is invalid.
        with self.assertRaises(ValueError):
            parse_numeric_string("''")
        # Whitespace stripping still allows valid input.
        self.assertEqual(parse_numeric_string('  42  '), 42, 'leading/trailing whitespace tolerated')
        # Octal base via configured default.
        self.assertEqual(parse_numeric_string('17', 'octal'), 15, 'configured octal base parses bare digits')

    def test_FormatPreservedInt_from_string(self):
        """Constructing from a string parses the numeric value and uses that string for repr/str."""
        v = FormatPreservedInt('0xFF')
        self.assertEqual(int(v), 255, 'parsed value matches numeric content')
        self.assertEqual(repr(v), '0xFF', 'repr returns the original string')
        self.assertEqual(str(v), '0xFF', 'str returns the original string')

    def test_FormatPreservedInt_from_int(self):
        """Constructing from an int with no original_str falls back to str(value) for display."""
        v = FormatPreservedInt(42)
        self.assertEqual(int(v), 42)
        self.assertEqual(str(v), '42', 'str fallback uses str(value) when no original_str provided')

    def test_FormatPreservedInt_explicit_original_str(self):
        """An explicit original_str kwarg overrides the default display string on both code paths."""
        v_str = FormatPreservedInt('0xff', '0xFF')
        self.assertEqual(int(v_str), 255)
        self.assertEqual(str(v_str), '0xFF', 'explicit original_str overrides string value')

        v_int = FormatPreservedInt(255, '0xff')
        self.assertEqual(int(v_int), 255)
        self.assertEqual(str(v_int), '0xff', 'explicit original_str overrides default str(int)')

    def test_FormatPreservedInt_mismatch_raises(self):
        """ValueError fires if value and original_str parse to different integers (drift guard)."""
        with self.assertRaises(ValueError):
            FormatPreservedInt(255, '0xfe')
        with self.assertRaises(ValueError):
            FormatPreservedInt('0xff', '0xfe')
        # Different formattings of the same value are accepted.
        v = FormatPreservedInt('255', '0xff')
        self.assertEqual(int(v), 255)
        self.assertEqual(str(v), '0xff', 'matching values across formats are allowed')

    def test_FormatPreservedInt_arithmetic_loses_format(self):
        """Arithmetic operations on a FormatPreservedInt return a plain int (format isn't propagated)."""
        v = FormatPreservedInt('0x10')
        self.assertEqual(v + 1, 17)
        self.assertNotIsInstance(v + 1, FormatPreservedInt)

    def test_convert_disallowed_pairs_to_flow_style_basic(self):
        """A top-level 'disallowed_pairs' list gets each inner list wrapped in FlowStyleList; siblings untouched."""
        input_dict = {
            'disallowed_pairs': [['a', 'b'], ['c', 'd']],
            'other': 'value',
        }
        result = convert_disallowed_pairs_to_flow_style(input_dict)
        self.assertIsInstance(result['disallowed_pairs'][0], FlowStyleList)
        self.assertIsInstance(result['disallowed_pairs'][1], FlowStyleList)
        self.assertEqual(list(result['disallowed_pairs'][0]), ['a', 'b'])
        self.assertEqual(result['other'], 'value', 'sibling values are preserved unchanged')

    def test_convert_disallowed_pairs_to_flow_style_nested(self):
        """Recursion descends through nested dicts, finding disallowed_pairs at any depth."""
        input_dict = {'instructions': {'add': {'disallowed_pairs': [['x', 'y']]}}}
        result = convert_disallowed_pairs_to_flow_style(input_dict)
        self.assertIsInstance(result['instructions']['add']['disallowed_pairs'][0], FlowStyleList)

    def test_convert_disallowed_pairs_to_flow_style_passthrough(self):
        """Non-collection values (scalars, None) and plain lists pass through unchanged."""
        self.assertEqual(convert_disallowed_pairs_to_flow_style(42), 42)
        self.assertEqual(convert_disallowed_pairs_to_flow_style('hello'), 'hello')
        self.assertIsNone(convert_disallowed_pairs_to_flow_style(None))
        # Plain lists (not under disallowed_pairs) recurse but are not converted.
        self.assertEqual(convert_disallowed_pairs_to_flow_style([1, 2, 3]), [1, 2, 3])

    def test_convert_disallowed_pairs_non_list_value(self):
        """A 'disallowed_pairs' value that isn't a list (defensive case) falls through to normal recursion."""
        input_dict = {'disallowed_pairs': 'not-a-list'}
        result = convert_disallowed_pairs_to_flow_style(input_dict)
        self.assertEqual(result['disallowed_pairs'], 'not-a-list')

    # ---- YAML format preservation round-trip tests ----
    # Use case: configgen loads a template YAML, modifies fields, and re-emits it.
    # Number formats (esp. binary) must survive the round-trip so the generated
    # config remains human-readable.

    def _yaml_dump_str(self, obj):
        buf = io.StringIO()
        dump_yaml_with_formatting(obj, buf)
        return buf.getvalue()

    def test_yaml_round_trip_preserves_quoted_binary(self):
        """Quoted binary like '0b1010' is parsed as int 10 but re-emitted in original binary form (not decimal)."""
        src = "key: '0b1010'\n"
        loaded = load_yaml_with_format_preservation(src)
        self.assertIsInstance(loaded['key'], FormatPreservedInt)
        self.assertEqual(int(loaded['key']), 10)
        out = self._yaml_dump_str(loaded)
        self.assertIn('0b1010', out, 'binary format survives round-trip')
        self.assertNotIn(': 10', out, 'value is not re-emitted as decimal')

    def test_yaml_round_trip_preserves_quoted_hex_0x(self):
        """Quoted '0xFF' round-trips in `0x`-prefix form (not decimal 255)."""
        loaded = load_yaml_with_format_preservation("key: '0xFF'\n")
        self.assertEqual(int(loaded['key']), 255)
        self.assertIn('0xFF', self._yaml_dump_str(loaded))

    def test_yaml_round_trip_preserves_dollar_hex(self):
        """Quoted '$ff' round-trips in `$`-prefix hex form."""
        loaded = load_yaml_with_format_preservation("key: '$ff'\n")
        self.assertEqual(int(loaded['key']), 255)
        self.assertIn('$ff', self._yaml_dump_str(loaded))

    def test_yaml_round_trip_preserves_h_suffix_hex(self):
        """Quoted '1234H' round-trips in `H`-suffix hex form (assembler-style)."""
        loaded = load_yaml_with_format_preservation("key: '1234H'\n")
        self.assertEqual(int(loaded['key']), 0x1234)
        self.assertIn('1234H', self._yaml_dump_str(loaded))

    def test_yaml_round_trip_preserves_quoted_decimal(self):
        """A quoted decimal string is wrapped as FormatPreservedInt and round-trips unchanged."""
        loaded = load_yaml_with_format_preservation("key: '42'\n")
        self.assertIsInstance(loaded['key'], FormatPreservedInt)
        self.assertEqual(int(loaded['key']), 42)
        self.assertIn('42', self._yaml_dump_str(loaded))

    def test_yaml_round_trip_recurses_into_nested_maps(self):
        """Format preservation reaches values nested inside sub-maps, not just top-level keys."""
        src = "outer:\n  inner: '0b1010'\n"
        loaded = load_yaml_with_format_preservation(src)
        self.assertIsInstance(loaded['outer']['inner'], FormatPreservedInt)
        out = self._yaml_dump_str(loaded)
        self.assertIn('0b1010', out)

    def test_yaml_round_trip_converts_sequence_items(self):
        """Sequence (list) items get the same format-preservation treatment as map values."""
        src = "values:\n  - '0b1010'\n  - '0xFF'\n  - '42'\n"
        loaded = load_yaml_with_format_preservation(src)
        for item in loaded['values']:
            self.assertIsInstance(item, FormatPreservedInt)
        out = self._yaml_dump_str(loaded)
        self.assertIn('0b1010', out)
        self.assertIn('0xFF', out)
        self.assertIn('42', out)

    def test_yaml_disallowed_pairs_emit_flow_style(self):
        """A disallowed_pairs block list is re-emitted with each inner pair in flow style ([a, b])."""
        src = 'disallowed_pairs:\n  - - a\n    - b\n  - - c\n    - d\n'
        loaded = load_yaml_with_format_preservation(src)
        out = self._yaml_dump_str(loaded)
        self.assertIn('[a, b]', out, 'inner pair emitted as flow sequence')
        self.assertIn('[c, d]', out)

    def test_yaml_bare_prefix_strings_pass_through(self):
        """Regression: bare-prefix strings ('b', 'H', '$', '0x', '0b') must not be misclassified as numeric.

        Pre-fix, the prefix-detection branches used `all(c in '01' for c in '')` which is vacuously True
        for empty digit-tails, so single-character recognized prefixes were wrapped as
        FormatPreservedInt and then crashed inside parse_numeric_string. Now they pass through as strings.
        """
        for token in ('b', 'H', '$', '0x', '0b'):
            src = f"name: '{token}'\n"
            loaded = load_yaml_with_format_preservation(src)
            self.assertEqual(loaded['name'], token, f'bare prefix {token!r} preserved as string')
            self.assertNotIsInstance(loaded['name'], FormatPreservedInt)

    def test_yaml_dump_preserves_comments(self):
        """Block and inline YAML comments survive a load/dump round-trip (ruamel.yaml capability)."""
        src = (
            '# top comment\n'
            "key: '0b1010'  # inline\n"
            'other: value\n'
        )
        loaded = load_yaml_with_format_preservation(src)
        out = self._yaml_dump_str(loaded)
        self.assertIn('# top comment', out, 'block comment preserved')
        self.assertIn('# inline', out, 'inline comment preserved')

    def test_yaml_dump_accepts_plain_dict(self):
        """dump_yaml_with_formatting works on plain Python dicts (not just ruamel CommentedMap),
        still applying disallowed_pairs flow style."""
        plain = {
            'name': 'test',
            'disallowed_pairs': [['a', 'b'], ['c', 'd']],
        }
        out = self._yaml_dump_str(plain)
        self.assertIn('name: test', out)
        self.assertIn('[a, b]', out)
        self.assertIn('[c, d]', out)

    def test_yaml_unparseable_strings_pass_through(self):
        """Free-form strings that don't match any numeric prefix/suffix pattern remain plain strings."""
        loaded = load_yaml_with_format_preservation("name: 'hello world'\n")
        self.assertNotIsInstance(loaded['name'], FormatPreservedInt)
        self.assertEqual(loaded['name'], 'hello world')

    def test_PackedBits(self):
        ib1 = PackedBits()
        ib1.append_bits(0xd, 4, False, 'big')
        ib1.append_bits(0xe, 4, False, 'big')
        ib1.append_bits(0xad, 8, False, 'big')
        self.assertEqual(ib1.get_bytes(), bytearray([0xde, 0xad]))

        ib2 = PackedBits()
        ib2.append_bits(0xd, 4, False, 'big')
        ib2.append_bits(0xe, 4, byte_aligned=True, endian='big')
        ib2.append_bits(0xad, 8, byte_aligned=True, endian='big')
        self.assertEqual(ib2.get_bytes(), bytearray([0xd0, 0xe0, 0xad]))

        ib3 = PackedBits()
        ib3.append_bits(0x3, 2, False, endian='big')
        ib3.append_bits(0x5, 3, False, endian='big')
        ib3.append_bits(0xf, 4, byte_aligned=True, endian='big')
        self.assertEqual(ib3.get_bytes(), bytearray([0xe8, 0xf0]))

        ib4 = PackedBits()
        ib4.append_bits(0x1, 4, False, endian='big')
        ib4.append_bits(0xDEAD, 16, byte_aligned=True, endian='big')
        self.assertEqual(ib4.get_bytes(), bytearray([0x10, 0xde, 0xad]))

        ib5 = PackedBits()
        ib5.append_bits(0x1, 4, False, endian='big')
        ib5.append_bits(0xDEAD, 16, byte_aligned=True, endian='little')
        self.assertEqual(ib5.get_bytes(), bytearray([0x10, 0xad, 0xde]))

        ib6 = PackedBits()
        ib6.append_bits(0xBAD, 12, byte_aligned=True, endian='little')
        self.assertEqual(ib6.get_bytes(), bytearray([0xAD, 0xB0]))
        ib7 = PackedBits()
        ib7.append_bits(0xBAD, 12, byte_aligned=True, endian='big')
        self.assertEqual(ib7.get_bytes(), bytearray([0xBA, 0xD0]))

        ib8 = PackedBits()
        ib8.append_bits(1020, 10, byte_aligned=True, endian='big')
        ib8.append_bits(0xF, 4, byte_aligned=False, endian='big')
        self.assertEqual(ib8.get_bytes(), bytearray([0xFF, 0x3C]))


if __name__ == '__main__':
    unittest.main()
