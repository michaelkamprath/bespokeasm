import sys
import unittest

from bespokeasm.expression import parse_expression, ExpresionType

class TestExpression(unittest.TestCase):
    label_dict = {
            'value_1': 12,
            '8_ball': 8,
            'MixedCase': 2,
        }

    def test_expression_parsing(self):
        self.assertEqual(parse_expression(1212, '1 + 2').get_value(TestExpression.label_dict), 3, 'simple expression: 1+2')
        self.assertEqual(parse_expression(1212, '(value_1 - MixedCase)/5').get_value(TestExpression.label_dict), 2, 'label expression: (value_1 - two)/5')
        self.assertEqual(parse_expression(1212, '8_ball').get_value(TestExpression.label_dict), 8, 'label expression: 8_ball')
        self.assertEqual(parse_expression(1212, '8675309').get_value(TestExpression.label_dict), 8675309, 'numeric expression: 8675309')
        self.assertEqual(parse_expression(1212, 'value_1-2').get_value(TestExpression.label_dict), 10, 'numeric expression: value_1-2')
        self.assertEqual(parse_expression(1212, '3+12/3').get_value(TestExpression.label_dict), 7, 'test precedence order: 3+12/3 = 7')
        self.assertEqual(parse_expression(1212, '0-(3+7)').get_value(TestExpression.label_dict), -10, 'test handling of leading sign: -(3+7) = -10')

        with self.assertRaises(SystemExit, msg='only integer numeric values are supported'):
            value = parse_expression(1212, '(value_1/5)/2.4').get_value(TestExpression.label_dict)

    def test_expression_numeric_types(self):
        self.assertEqual(parse_expression(1212, '$100/0x80').get_value(TestExpression.label_dict), 2, 'test hexadecimal math: $100/0x80')
        self.assertEqual(parse_expression(1212, '%10000000/$2').get_value(TestExpression.label_dict), 64, 'test binary math: %1000000/$2')
        self.assertEqual(parse_expression(1212, '32/b10').get_value(TestExpression.label_dict), 16, 'test binary math: 32/b10')

    def test_expression_result_integer_casting(self):
        # resolved values are cast to an integer, truncating the fractional part
        self.assertEqual(parse_expression(1212, 'value_1/5').get_value(TestExpression.label_dict), 2, 'test rounding: 12/5 = 2')
        self.assertEqual(parse_expression(1212, '10/3/2').get_value(TestExpression.label_dict), 1, 'test rounding: 10/3/2 = 1')

    def test_bitwise_operators(self):
        self.assertEqual(parse_expression(111, 'b11110000&b10101010').get_value(TestExpression.label_dict), int('10100000', 2), 'bitwise AND')
        self.assertEqual(parse_expression(222, 'b11110000|b10101010').get_value(TestExpression.label_dict), int('11111010', 2), 'bitwise OR')
        self.assertEqual(parse_expression(222, 'b11110000^b10101010').get_value(TestExpression.label_dict), int('01011010', 2), 'bitwise XOR')
        # tests precendence order. + is of higher precednce than &
        self.assertEqual(parse_expression(111, 'b0000111&$01+$10').get_value(TestExpression.label_dict), 0x01, 'test precedence order')

if __name__ == '__main__':
    unittest.main()