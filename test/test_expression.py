import unittest

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.expression import parse_expression


class TestExpression(unittest.TestCase):
    label_values = None

    @classmethod
    def setUpClass(cls):
        cls.label_values = GlobalLabelScope(set())
        cls.label_values.set_label_value('value_1', 12, 1)
        cls.label_values.set_label_value('the_8_ball', 8, 2)
        cls.label_values.set_label_value('MixedCase', 2, 3)
        cls.label_values.set_label_value('MAX_N', 20, 1)

    def test_expression_parsing(self):
        line_id = LineIdentifier(1212, 'test_expression_parsing')

        self.assertEqual(
            parse_expression(line_id, '1 + 2').get_value(TestExpression.label_values, 1),
            3, 'simple expression: 1+2'
        )
        self.assertEqual(
            parse_expression(line_id, '(value_1 - MixedCase)/5').get_value(TestExpression.label_values, 2),
            2, 'label expression: (value_1 - two)/5'
        )
        self.assertEqual(
            parse_expression(line_id, 'the_8_ball').get_value(TestExpression.label_values, 3),
            8, 'label expression: 8_ball'
        )
        self.assertEqual(
            parse_expression(line_id, '8675309').get_value(TestExpression.label_values, 4),
            8675309, 'numeric expression: 8675309'
        )
        self.assertEqual(
            parse_expression(line_id, 'value_1-2').get_value(TestExpression.label_values, 5),
            10, 'numeric expression: value_1-2'
        )
        self.assertEqual(
            parse_expression(line_id, '3+12/3').get_value(TestExpression.label_values, 6),
            7, 'test precedence order: 3+12/3 = 7'
        )
        self.assertEqual(
            parse_expression(line_id, '0-(3+7)').get_value(TestExpression.label_values, 7),
            -10, 'test handling of leading sign: -(3+7) = -10'
        )
        self.assertEqual(
            parse_expression(line_id, '8*( MAX_N + 1 )  ').get_value(TestExpression.label_values, 8),
            168, 'test handling of leading sign: 8*(MAX_N+1) = 168'
        )
        self.assertEqual(
            parse_expression(line_id, '(MAX_N + 3)%5').get_value(TestExpression.label_values, line_id),
            3, 'test handling of modulo: (MAX_N + 3)%5 = 3'
        )
        self.assertEqual(
            parse_expression(line_id, '(MAX_N + 3) % %101').get_value(TestExpression.label_values, line_id),
            3, 'test handling of modulo: (MAX_N + 3) % %101 = 3'
        )

        with self.assertRaises(SyntaxError, msg='only integer numeric values are supported'):
            parse_expression(1212, '(value_1/5)/2.4').get_value(TestExpression.label_values, 100)

    def test_expression_numeric_types(self):
        self.assertEqual(
            parse_expression(1212, '$100/0x80').get_value(TestExpression.label_values, 1),
            2, 'test hexadecimal math: $100/0x80'
        )
        self.assertEqual(
            parse_expression(1212, '%10000000/$2').get_value(TestExpression.label_values, 2),
            64, 'test binary math: %1000000/$2'
        )
        self.assertEqual(
            parse_expression(1212, '32/b10').get_value(TestExpression.label_values, 3),
            16, 'test binary math: 32/b10'
        )

    def test_expression_result_integer_casting(self):
        # resolved values are cast to an integer, truncating the fractional part
        self.assertEqual(
            parse_expression(1212, 'value_1/5').get_value(TestExpression.label_values, 1),
            2, 'test rounding: 12/5 = 2'
        )
        self.assertEqual(
            parse_expression(1212, '10/3/2').get_value(TestExpression.label_values, 2),
            1, 'test rounding: 10/3/2 = 1'
        )

    def test_bitwise_operators(self):
        self.assertEqual(
            parse_expression(111, 'b11110000&b10101010').get_value(TestExpression.label_values, 1),
            int('10100000', 2),
            'bitwise AND'
        )
        self.assertEqual(
            parse_expression(222, 'b11110000|b10101010').get_value(TestExpression.label_values, 2),
            int('11111010', 2), 'bitwise OR'
            )
        self.assertEqual(
            parse_expression(222, 'b11110000^b10101010').get_value(TestExpression.label_values, 3),
            int('01011010', 2), 'bitwise XOR'
            )
        # tests precendence order. + is of higher precednce than &
        self.assertEqual(
            parse_expression(111, 'b0000111&$01+$10').get_value(TestExpression.label_values, 4),
            0x01, 'test precedence order'
        )

    def test_register_detection(self):
        registers = {'a', 'b', 'sp', 'mar'}

        e1 = parse_expression(1212, '(label1+3)*5')
        self.assertFalse(e1.contains_register_labels(registers), 'does not contain registers')

        e2 = parse_expression(1212, 'sp+5')
        self.assertTrue(e2.contains_register_labels(registers), 'does contain registers')

        e3 = parse_expression(1212, 'label1*3 + sp + 5')
        self.assertTrue(e3.contains_register_labels(registers), 'does contain registers')

        e4 = parse_expression(1212, 'b')
        self.assertTrue(e4.contains_register_labels(registers), 'does contain registers, not binary prefix')

    def test_bit_shifting(self):
        self.assertEqual(
            parse_expression(111, '1 << 3').get_value(TestExpression.label_values, 1),
            8, '1 << 3 = 8'
        )
        self.assertEqual(
            parse_expression(111, '1 << MixedCase').get_value(TestExpression.label_values, 1),
            4, '1 << MixedCase = 4'
        )
        self.assertEqual(
            parse_expression(111, '(MAX_N + 2) >> 1').get_value(TestExpression.label_values, 1),
            11, '(MAX_N + 2) >> 1 = 11'
        )

        # test operation precedence
        self.assertEqual(
            parse_expression(111, '1 << 2 + 1').get_value(TestExpression.label_values, 1),
            8,
            '1 << 2 + 1 = 8 (+ takes precedence over <<)'
        )
        self.assertEqual(
            parse_expression(111, '(1 << 2) + 1').get_value(TestExpression.label_values, 1),
            5,
            '(1 << 2) + 1 = 5 (+ takes precedence over <<)'
        )

    def test_unary_byte_value_extractor(self):
        line_id = LineIdentifier(777, 'test_unary_byte_value_extractor')

        self.assertEqual(
            parse_expression(line_id, 'LSB( $1234 )').get_value(TestExpression.label_values, 1),
            0x34, 'LSB( $1234 ) = $34'
        )
        self.assertEqual(
            parse_expression(line_id, 'BYTE1( $1234 )').get_value(TestExpression.label_values, 1),
            0x12, 'BYTE1( $1234 ) = $12'
        )
        self.assertEqual(
            parse_expression(line_id, 'BYTE1( (MAX_N + 50)*value_1 )').get_value(TestExpression.label_values, 1),
            0x03, 'BYTE1( (MAX_N + 50)*value_1 ) = BYTE1( $0348 ) = $03'
        )
        self.assertEqual(
            parse_expression(line_id, '4*LSB( (MAX_N + 50)*value_1 )').get_value(TestExpression.label_values, 1),
            0x0120, '4*LSB( (MAX_N + 50)*value_1 ) = 4*LSB( $0348 ) = 4*$48 = $0120'
        )
        self.assertEqual(
            parse_expression(line_id, 'BYTE1( $1234 )').get_value(TestExpression.label_values, 1),
            0x12, 'BYTE1( $1234 ) = $12'
        )
        self.assertEqual(
            parse_expression(line_id, 'BYTE1( $12345678 )').get_value(TestExpression.label_values, 1),
            0x56, 'BYTE1( $12345678 ) = $56'
        )
        self.assertEqual(
            parse_expression(line_id, 'BYTE3( $12345678 )').get_value(TestExpression.label_values, 1),
            0x12, 'BYTE3( $12345678 ) = $12'
        )
        self.assertEqual(
            # this tests asks for a byte that exceeds the range of the value.
            parse_expression(line_id, 'BYTE4( $12345678 )').get_value(TestExpression.label_values, 1),
            0, 'BYTE4( $12345678 ) = $00'
        )
        self.assertEqual(
            parse_expression(line_id, 'BYTE2( MAX_N*MAX_N*MAX_N*MAX_N )').get_value(TestExpression.label_values, 1),
            2, 'BYTE2( MAX_N*MAX_N*MAX_N*MAX_N ) = BYTE2( 0x027100 ) = 2'
        )

        self.assertEqual(
            parse_expression(
                line_id,
                'BYTE0( -15 )'
            ).get_value(TestExpression.label_values, 1),
            0xF1,
            'BYTE0( -15 ) = BYTE0( 0xFFFFFFF1 ) = 0xF1'
        )
        self.assertEqual(
            parse_expression(
                line_id,
                'BYTE1( 1000 - 2000 )'
            ).get_value(TestExpression.label_values, 1),
            0xFC,
            'BYTE1( 1000 - 2000 ) = BYTE1( 0xFFFFFC18 ) = 0xFC'
        )

    def test_character_ordinals_in_expressions(self):
        line_id = LineIdentifier(888, 'test_character_ordinals_in_expressions')
        self.assertEqual(
            parse_expression(line_id, "'a'").get_value(TestExpression.label_values, 1),
            97, "'a' = 97"
        )
        self.assertEqual(
            parse_expression(line_id, "'A' + 32").get_value(TestExpression.label_values, 1),
            97, "'A' + 32 = 97"
        )
        self.assertEqual(
            parse_expression(line_id, "(' '*32)").get_value(TestExpression.label_values, 1),
            1024, "(' '*32) = 1024"
        )
        self.assertEqual(
            parse_expression(line_id, "(' ' + ' ')").get_value(TestExpression.label_values, 1),
            64, "(' ' + ' ') = 64"
        )

    def test_negative_values(self):
        line_id = LineIdentifier(1927, 'test_character_ordinals_in_expressions')

        self.assertEqual(
            parse_expression(line_id, "-21").get_value(TestExpression.label_values, 1),
            -21,
            "negative 21"
        )

        self.assertEqual(
            parse_expression(line_id, "5 * ( -6 )").get_value(TestExpression.label_values, 1),
            -30,
            "negative 30"
        )

        self.assertEqual(
            parse_expression(line_id, "10 + -(5*2)").get_value(TestExpression.label_values, 1),
            0,
            "0"
        )

        self.assertEqual(
            parse_expression(line_id, "-2*MAX_N").get_value(TestExpression.label_values, 1),
            -40,
            "negative label expression"
        )


if __name__ == '__main__':
    unittest.main()
