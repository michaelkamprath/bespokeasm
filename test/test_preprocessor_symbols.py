import importlib.resources as pkg_resources
import unittest

from test import config_files
from test import test_code

from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition import \
    IfPreprocessorCondition, IfdefPreprocessorCondition, ElifPreprocessorCondition, \
    ElsePreprocessorCondition, EndifPreprocessorCondition, MutePreprocessorCondition, \
    UnmutePreprocessorCondition
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_object.preprocessor_line.define_symbol import DefineSymbolLine
from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


class TestPreprocessorSymbols(unittest.TestCase):
    def setUp(self):
        pass

    def test_proprocessor_resolve_symbols(self):
        preprocessor = Preprocessor()
        preprocessor.create_symbol('s1', '57')
        preprocessor.create_symbol('s2', 's1*2')

        line_id = LineIdentifier(1, 'test_preprocessor_resolve_symbols')

        t1 = preprocessor.resolve_symbols(line_id, 's1')
        self.assertEqual(t1, '57', 's1 should resolve to 57')

        t2 = preprocessor.resolve_symbols(line_id, 's2')
        self.assertEqual(t2, '57*2', 's2 should resolve to 57*2')

        t3 = preprocessor.resolve_symbols(line_id, 's1 + s2 + label1')
        self.assertEqual(t3, '57 + 57*2 + label1', 's1 + s2 should resolve to 57 + 57*2')

        # test infinite recursion detection
        preprocessor.create_symbol('s3', 's4')
        preprocessor.create_symbol('s4', '2*s5')
        preprocessor.create_symbol('s5', 's3')
        with self.assertRaises(SystemExit):
            preprocessor.resolve_symbols(line_id, 's3')

    def test_preprocessor_comparisons(self):
        class MockPreprocessorCondition_True(IfPreprocessorCondition):
            def __init__(self, line: LineIdentifier):
                super().__init__('#if true', line)

            def __repr__(self) -> str:
                return 'MockPreprocessorCondition_True'

            def evaluate(self, preprocessor: Preprocessor) -> bool:
                return True

        class MockPreprocessorCondition_False(IfPreprocessorCondition):
            def __init__(self, line: LineIdentifier):
                super().__init__('#if false', line)

            def __repr__(self) -> str:
                return 'MockPreprocessorCondition_False'

            def evaluate(self, preprocessor: Preprocessor) -> bool:
                return False

        preprocessor = Preprocessor()
        preprocessor.create_symbol('s1', '57')
        preprocessor.create_symbol('s2', 's1*2')
        preprocessor.create_symbol('s3', '57')
        preprocessor.create_symbol('s4', 'string_value1')
        preprocessor.create_symbol('s5', 'string_value2')
        preprocessor.create_symbol('s6', 's4')
        preprocessor.create_symbol('s7', '0x10')
        preprocessor.create_symbol('s8', '0')

        c1 = IfPreprocessorCondition('#if s1 == s2', LineIdentifier('test_preprocessor_comparisons', 1))
        self.assertFalse(c1.evaluate(preprocessor), 's1 == s2 should be false')

        c2 = IfPreprocessorCondition('#if s1 == s3', LineIdentifier('test_preprocessor_comparisons', 2))
        self.assertTrue(c2.evaluate(preprocessor), 's1 == s3 should be true')

        # string comparisons
        c3 = IfPreprocessorCondition('#if s4 == s5', LineIdentifier('test_preprocessor_comparisons', 3))
        self.assertFalse(c3.evaluate(preprocessor), 's4 == s5 should be false')

        c3b = IfPreprocessorCondition('#if s4 == "string_value1"', LineIdentifier('test_preprocessor_comparisons', 3))
        self.assertTrue(c3b.evaluate(preprocessor), 's4 == "string_value1" should be true')

        c3c = IfPreprocessorCondition('#if s4 == 42', LineIdentifier('test_preprocessor_comparisons', 3))
        self.assertFalse(c3c.evaluate(preprocessor), 's4 == 42 should be false (string != number)')

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

        c9b = IfPreprocessorCondition('#if (s7-16)', LineIdentifier('test_preprocessor_comparisons', 9))
        print(f'c9b = {c9b}')
        self.assertFalse(c9b.evaluate(preprocessor), 's7-16 should be false (equal to zero)')

        # test expression on LHS
        c10 = IfPreprocessorCondition('#if 1<<4 == s7', LineIdentifier('test_preprocessor_comparisons', 10))
        self.assertTrue(c10.evaluate(preprocessor), '1<<4 == s7 should be true')

        # test #ifdef
        c11 = IfdefPreprocessorCondition('#ifdef s7', LineIdentifier('test_preprocessor_comparisons', 11))
        self.assertTrue(c11.evaluate(preprocessor), 's7 should be defined')

        c12 = IfdefPreprocessorCondition('#ifdef s9', LineIdentifier('test_preprocessor_comparisons', 12))
        self.assertFalse(c12.evaluate(preprocessor), 's9 should not be defined')

        c13 = IfdefPreprocessorCondition('#ifndef s7', LineIdentifier('test_preprocessor_comparisons', 11))
        self.assertFalse(c13.evaluate(preprocessor), 's7 should be defined')

        c14 = IfdefPreprocessorCondition('#ifndef s100', LineIdentifier('test_preprocessor_comparisons', 12))
        self.assertTrue(c14.evaluate(preprocessor), 's100 should not be defined')

        # test #elif
        c15 = ElifPreprocessorCondition('#elif s7 == 1<<4', LineIdentifier('test_preprocessor_comparisons', 15))
        c15.parent = MockPreprocessorCondition_True(LineIdentifier('test_preprocessor_comparisons', 15))
        self.assertFalse(c15.evaluate(preprocessor), 's7 == 1<<4 should be false when parent is true')
        c15.parent = MockPreprocessorCondition_False(LineIdentifier('test_preprocessor_comparisons', 15))
        self.assertTrue(c15.evaluate(preprocessor), 's7 == 1<<4 should be true when parent is false')

        c16 = ElifPreprocessorCondition('#elif s8', LineIdentifier('test_preprocessor_comparisons', 16))
        c16.parent = MockPreprocessorCondition_True(LineIdentifier('test_preprocessor_comparisons', 16))
        self.assertFalse(c16.evaluate(preprocessor), 's8 != 0 should be false when parent is true')
        c16.parent = MockPreprocessorCondition_False(LineIdentifier('test_preprocessor_comparisons', 16))
        self.assertFalse(c16.evaluate(preprocessor), 's8 != 0 should be false when parent is false')

        c17 = ElifPreprocessorCondition('#elif ((s8)+(21))', LineIdentifier('test_preprocessor_comparisons', 17))
        c17.parent = MockPreprocessorCondition_True(LineIdentifier('test_preprocessor_comparisons', 17))
        self.assertFalse(c17.evaluate(preprocessor), 's8+21 != 0 should be false when parent is true')
        c17.parent = MockPreprocessorCondition_False(LineIdentifier('test_preprocessor_comparisons', 17))
        self.assertTrue(c17.evaluate(preprocessor), 's8+21 != 0 should be true when parent is false')

        # test #else
        c18 = ElsePreprocessorCondition('#else', LineIdentifier('test_preprocessor_comparisons', 18))
        c18.parent = MockPreprocessorCondition_True(LineIdentifier('test_preprocessor_comparisons', 18))
        self.assertFalse(c18.evaluate(preprocessor), 'else should be false when parent is true')
        c18.parent = MockPreprocessorCondition_False(LineIdentifier('test_preprocessor_comparisons', 18))
        self.assertTrue(c18.evaluate(preprocessor), 'else should be true when parent is false')

    def test_define_symbol_line_objects(self):
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
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
            '#define TEST_SYMBOL 0x1234',
            isa_model,
            global_scope,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConditionStack(),
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
            ConditionStack(),
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
            ConditionStack(),
            0,
        )[0]
        self.assertTrue(isinstance(l3, DefineSymbolLine), '3 should be a DefineSymbolLine')
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

        l4: LineObject = LineOjectFactory.parse_line(
            lineid,
            '#define CODE_SYMBOL push a  ; my comment',
            isa_model,
            global_scope,
            memzone_mngr.global_zone,
            memzone_mngr,
            preprocessor,
            ConditionStack(),
            0,
        )[0]
        self.assertTrue(isinstance(l4, DefineSymbolLine), 'l4 should be a DefineSymbolLine')
        self.assertEqual(l4.comment, 'my comment', 'comment should be "my comment"')
        dsl4: DefineSymbolLine = l4
        self.assertEqual(dsl4.symbol.name, 'CODE_SYMBOL', 'symbol name should be CODE_SYMBOL')
        self.assertEqual(dsl4.symbol.value, 'push a', 'symbol value should be: push a')
        self.assertEqual(dsl4.symbol.created_line_id, lineid, 'symbol created line id should be lineid')
        self.assertTrue(preprocessor.get_symbol('CODE_SYMBOL') is not None, 'CODE_SYMBOL should be defined')
        self.assertEqual(preprocessor.get_symbol('CODE_SYMBOL').value, 'push a', 'symbol value should be: push a')

    def test_compilation_control_and_symbol_replacement(self):
        fp = pkg_resources.files(config_files).joinpath('test_compilation_control.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        label_scope = GlobalLabelScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )
        preprocessor = Preprocessor()

        asm_fp = pkg_resources.files(test_code).joinpath('test_compilation_control.asm')
        asm_obj = AssemblyFile(asm_fp, label_scope)

        try:
            line_objs: list[LineObject] = asm_obj.load_line_objects(
                isa_model,
                [],
                memzone_manager,
                preprocessor,
                0,
            )
        except SystemExit:
            print(isa_model)
            print(f'  instructions = {isa_model.instructions}')
            raise

        # ensure file was assembled as expected
        #   there is one for each preprocessor statement, plus one for the label,
        #   plus one for each of the valid instructions inside the compilation control
        #   directives.
        self.assertEqual(len(line_objs), 28, '28 total code lines')
        self.assertEqual(len([lo for lo in line_objs if lo.compilable]), 23, '23 compilable code lines')

        expected_no_compile_lines = [9, 12, 18, 22, 26]
        actual_no_compile_lines = []
        for i in range(len(line_objs)):
            if not line_objs[i].compilable:
                actual_no_compile_lines.append(i)
        self.assertEqual(actual_no_compile_lines, expected_no_compile_lines, 'no compile lines should be 9, 12, 18, 22, 26')

        # symbol replacement
        #   line 16 is "mov a, SYMBOL2", should become "mov a, 0"
        #   line 18 is "mov a, SYMBOL1", should become "mov a, 1"

        self.assertEqual(line_objs[16].instruction, 'mov a, 0', 'line 16 should be "mov a, 0"')
        self.assertEqual(line_objs[18].instruction, 'mov a, 1', 'line 18 should be "mov a, 1"')

    def test_condition_stack(self):
        stack = ConditionStack()
        preprocessor = Preprocessor()
        preprocessor.create_symbol('s1', '57')
        preprocessor.create_symbol('s2', 's1*2')
        preprocessor.create_symbol('s3', '57')
        preprocessor.create_symbol('s4', 'string_value1')
        preprocessor.create_symbol('s5', 'string_value2')
        preprocessor.create_symbol('s6', 's4')
        preprocessor.create_symbol('s7', '0x10')
        preprocessor.create_symbol('s8', '0')

        self.assertEqual(stack.currently_active(preprocessor), True, 'initial condition should be True')

        # add an if condition that should be false
        c1 = IfPreprocessorCondition('#if s1 < 50', LineIdentifier('test_condition_stack', 1))
        stack.process_condition(c1, preprocessor)
        self.assertFalse(stack.currently_active(preprocessor), 'condition should be False')

        # add an elif condition that should be true
        c2 = ElifPreprocessorCondition('#elif s1 >= 55', LineIdentifier('test_condition_stack', 2))
        stack.process_condition(c2, preprocessor)
        self.assertTrue(stack.currently_active(preprocessor), 'condition should be True')

        # add an elif that could be true but is false because it follows a true elif
        c3 = ElifPreprocessorCondition('#elif s1 < 60', LineIdentifier('test_condition_stack', 3))
        stack.process_condition(c3, preprocessor)
        self.assertFalse(stack.currently_active(preprocessor), 'condition should be False')

        # add the else condition
        c4 = ElsePreprocessorCondition('#else', LineIdentifier('test_condition_stack', 4))
        stack.process_condition(c4, preprocessor)
        self.assertFalse(stack.currently_active(preprocessor), 'condition should be False')

        # add endif
        c5 = EndifPreprocessorCondition('#endif', LineIdentifier('test_condition_stack', 5))
        stack.process_condition(c5, preprocessor)
        self.assertTrue(stack.currently_active(preprocessor), 'condition should be True')

    def test_muting(self):
        stack = ConditionStack()
        preprocessor = Preprocessor()

        self.assertFalse(stack.is_muted, 'initial condition should be False')
        stack.process_condition(MutePreprocessorCondition('#mute', LineIdentifier('test_muting', 1)), preprocessor)
        self.assertTrue(stack.is_muted, 'condition should be True')
        stack.process_condition(UnmutePreprocessorCondition('#unmute', LineIdentifier('test_muting', 2)), preprocessor)
        self.assertFalse(stack.is_muted, 'condition should be False')
        stack.process_condition(MutePreprocessorCondition('#mute', LineIdentifier('test_muting', 3)), preprocessor)
        stack.process_condition(MutePreprocessorCondition('#mute', LineIdentifier('test_muting', 4)), preprocessor)
        stack.process_condition(MutePreprocessorCondition('#mute', LineIdentifier('test_muting', 5)), preprocessor)
        self.assertTrue(stack.is_muted, 'condition should be True')
        stack.process_condition(UnmutePreprocessorCondition('#unmute', LineIdentifier('test_muting', 6)), preprocessor)
        self.assertTrue(stack.is_muted, 'condition should be True')
        stack.process_condition(UnmutePreprocessorCondition('#unmute', LineIdentifier('test_muting', 7)), preprocessor)
        self.assertTrue(stack.is_muted, 'condition should be True')
        stack.process_condition(UnmutePreprocessorCondition('#unmute', LineIdentifier('test_muting', 8)), preprocessor)
        self.assertFalse(stack.is_muted, 'condition should be False')

    def test_conditional_muting(self):
        """Demonstrate that conditional compilation controls the mute/unmute preprocessor directives."""
        # if a #mute is inside a false condition, it should not mute
        stack = ConditionStack()
        preprocessor = Preprocessor()
        preprocessor.create_symbol('s1', '57')
        preprocessor.create_symbol('s2', 's1*2')

        self.assertTrue(stack.currently_active(preprocessor), 'condition should be True')
        self.assertFalse(stack.is_muted, 'mute should be False')

        c1 = IfPreprocessorCondition('#if s1 < 50', LineIdentifier('test_condition_stack', 1))
        stack.process_condition(c1, preprocessor)
        self.assertFalse(stack.currently_active(preprocessor), 'condition should be False')
        self.assertFalse(stack.is_muted, 'mute should be False')
        stack.process_condition(MutePreprocessorCondition('#mute', LineIdentifier('test_muting', 2)), preprocessor)
        self.assertFalse(stack.currently_active(preprocessor), 'condition should be False')
        self.assertFalse(stack.is_muted, 'mute should be False')

        # if a #mute is inside a true condition, it should mute
        c2 = ElsePreprocessorCondition('#else', LineIdentifier('test_condition_stack', 3))
        stack.process_condition(c2, preprocessor)
        self.assertTrue(stack.currently_active(preprocessor), 'condition should be True')
        self.assertFalse(stack.is_muted, 'mute should be False')
        stack.process_condition(MutePreprocessorCondition('#mute', LineIdentifier('test_muting', 4)), preprocessor)
        self.assertTrue(stack.currently_active(preprocessor), 'condition should be False')
        self.assertTrue(stack.is_muted, 'mute should be True')

        c3 = EndifPreprocessorCondition('#endif', LineIdentifier('test_condition_stack', 5))
        stack.process_condition(c3, preprocessor)
        self.assertTrue(stack.currently_active(preprocessor), 'condition should be True')
        self.assertTrue(stack.is_muted, 'mute should be True')
        stack.process_condition(UnmutePreprocessorCondition('#unmute', LineIdentifier('test_muting', 6)), preprocessor)
        self.assertTrue(stack.currently_active(preprocessor), 'condition should be True')
        self.assertFalse(stack.is_muted, 'mute should be False')
