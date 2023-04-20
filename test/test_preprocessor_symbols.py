import importlib.resources as pkg_resources
import unittest

from test import config_files

from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition import IfPreprocessorCondition, IfdefPreprocessorCondition
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_object.preprocessor_line.define_symbol import DefineSymbolLine


class TestPreprocessorSymbols(unittest.TestCase):
    def setUp(self):
        pass

    def test_proprocessor_resolve_symbols(self):
        preprocessor = Preprocessor()
        preprocessor.create_symbol('s1', '57')
        preprocessor.create_symbol('s2', 's1*2')

        t1 = preprocessor.resolve_symbols('s1')
        self.assertEqual(t1, '57', 's1 should resolve to 57')

        t2 = preprocessor.resolve_symbols('s2')
        self.assertEqual(t2, '57*2', 's2 should resolve to 57*2')

        t3 = preprocessor.resolve_symbols('s1 + s2 + label1')
        self.assertEqual(t3, '57 + 57*2 + label1', 's1 + s2 should resolve to 57 + 57*2')

    def test_preprocessor_comparisons(self):
        preprocessor = Preprocessor()
        preprocessor.create_symbol('s1', '57')
        preprocessor.create_symbol('s2', 's1*2')
        preprocessor.create_symbol('s3', '57')
        preprocessor.create_symbol('s4', 'string_value1')
        preprocessor.create_symbol('s5', 'string_value2')
        preprocessor.create_symbol('s6', 's4')
        preprocessor.create_symbol('s7', '0x10')

        c1 = IfPreprocessorCondition('#if s1 == s2', LineIdentifier('test_preprocessor_comparisons', 1))
        self.assertFalse(c1.evaluate(preprocessor), 's1 == s2 should be false')

        c2 = IfPreprocessorCondition('#if s1 == s3', LineIdentifier('test_preprocessor_comparisons', 2))
        self.assertTrue(c2.evaluate(preprocessor), 's1 == s3 should be true')

        c3 = IfPreprocessorCondition('#if s4 == s5', LineIdentifier('test_preprocessor_comparisons', 3))
        self.assertFalse(c3.evaluate(preprocessor), 's4 == s5 should be false')

        c4 = IfPreprocessorCondition('#if s4 == s6', LineIdentifier('test_preprocessor_comparisons', 4))
        self.assertTrue(c4.evaluate(preprocessor), 's4 == s6 should be true')

        c5 = IfPreprocessorCondition('#if s1 < s2', LineIdentifier('test_preprocessor_comparisons', 5))
        self.assertTrue(c5.evaluate(preprocessor), 's1 < s2 should be true')

        c6 = IfPreprocessorCondition('#if s4 < s5', LineIdentifier('test_preprocessor_comparisons', 6))
        self.assertTrue(c6.evaluate(preprocessor), 's4 < s5 should be true')

        c7 = IfPreprocessorCondition('#if s5 == "string_value2"', LineIdentifier('test_preprocessor_comparisons', 7))
        self.assertTrue(c7.evaluate(preprocessor), 's5 == "string_value2" should be true')

        c8 = IfPreprocessorCondition('#if s7 == 1<<4', LineIdentifier('test_preprocessor_comparisons', 8))
        self.assertTrue(c8.evaluate(preprocessor), 's7 == 1<<4 should be true')

        # test implied != 0 comparison
        c9 = IfPreprocessorCondition('#if s7', LineIdentifier('test_preprocessor_comparisons', 9))
        self.assertTrue(c9.evaluate(preprocessor), 's7 should be true')

        # test expression on LHS
        c10 = IfPreprocessorCondition('#if 1<<4 == s7', LineIdentifier('test_preprocessor_comparisons', 10))
        self.assertTrue(c10.evaluate(preprocessor), '1<<4 == s7 should be true')

        # test #ifdef
        c11 = IfdefPreprocessorCondition('#ifdef s7', LineIdentifier('test_preprocessor_comparisons', 11))
        self.assertTrue(c11.evaluate(preprocessor), 's7 should be defined')

        c12 = IfdefPreprocessorCondition('#ifdef s8', LineIdentifier('test_preprocessor_comparisons', 12))
        self.assertFalse(c12.evaluate(preprocessor), 's8 should not be defined')

        c13 = IfdefPreprocessorCondition('#ifndef s7', LineIdentifier('test_preprocessor_comparisons', 11))
        self.assertFalse(c13.evaluate(preprocessor), 's7 should be defined')

        c14 = IfdefPreprocessorCondition('#ifndef s8', LineIdentifier('test_preprocessor_comparisons', 12))
        self.assertTrue(c14.evaluate(preprocessor), 's8 should not be defined')

    def test_define_symbol_line_objects(self):
        with pkg_resources.path(config_files, 'test_instructions_with_variants.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
            memzone_mngr = MemoryZoneManager(
                isa_model.address_size,
                isa_model.default_origin,
                isa_model.predefined_memory_zones,
            )

        global_scope = GlobalLabelScope(set())
        lineid = LineIdentifier(12, 'test_define_symbol_line_objects')
        preprocessor = Preprocessor()

        l1: LineObject = LineOjectFactory.parse_line(
            lineid,
            "#define TEST_SYMBOL 0x1234",
            isa_model,
            global_scope,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            0,
        )[0]
        self.assertTrue(isinstance(l1, DefineSymbolLine), 'l1 should be a DefineSymbolLine')
        dsl1: DefineSymbolLine = l1
        self.assertEqual(dsl1.symbol.name, 'TEST_SYMBOL', 'symbol name should be TEST_SYMBOL')
        self.assertEqual(dsl1.symbol.value, '0x1234', 'symbol value should be 0x1234')
        self.assertEqual(dsl1.symbol.value_numeric, 0x1234, 'symbol value should be 0x1234')
        self.assertEqual(dsl1.symbol.created_line_id, lineid, 'symbol created line id should be lineid')
        self.assertTrue(preprocessor.get_symbol('TEST_SYMBOL') is not None, 'TEST_SYMBOL should be defined')
        self.assertEqual(preprocessor.get_symbol('TEST_SYMBOL').value, '0x1234', 'symbol value should be 0x1234')

        l2: LineObject = LineOjectFactory.parse_line(
            lineid,
            '#define MY_NAME "George Washington!"',
            isa_model,
            global_scope,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            0,
        )[0]
        self.assertTrue(isinstance(l2, DefineSymbolLine), 'l1 should be a DefineSymbolLine')
        dsl2: DefineSymbolLine = l2
        self.assertEqual(dsl2.symbol.name, 'MY_NAME', 'symbol name should be MY_NAME')
        self.assertEqual(dsl2.symbol.value, '"George Washington!"', 'symbol value should be "George Washington!"')
        self.assertEqual(dsl2.symbol.created_line_id, lineid, 'symbol created line id should be lineid')
        self.assertTrue(preprocessor.get_symbol('MY_NAME') is not None, 'MY_NAME should be defined')
        self.assertEqual(
            preprocessor.get_symbol('MY_NAME').value,
            '"George Washington!"',
            'symbol value should be "George Washington!"'
        )

        l3: LineObject = LineOjectFactory.parse_line(
            lineid,
            '#define WITH_COMMENT (13 + 27) ; my comment',
            isa_model,
            global_scope,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            0,
        )[0]
        self.assertTrue(isinstance(l3, DefineSymbolLine), 'l1 should be a DefineSymbolLine')
        self.assertEqual(l3.comment, 'my comment', 'comment should be "my comment"')
        dsl3: DefineSymbolLine = l3
        self.assertEqual(dsl3.symbol.name, 'WITH_COMMENT', 'symbol name should be WITH_COMMENT')
        self.assertEqual(dsl3.symbol.value, '(13 + 27)', 'symbol value should be (13 + 27)')
        self.assertEqual(dsl3.symbol.created_line_id, lineid, 'symbol created line id should be lineid')
        self.assertTrue(preprocessor.get_symbol('WITH_COMMENT') is not None, 'WITH_COMMENT should be defined')
        self.assertEqual(
            preprocessor.get_symbol('WITH_COMMENT').value,
            '(13 + 27)',
            'symbol value should be (13 + 27)'
        )
