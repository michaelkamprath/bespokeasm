import importlib.resources as pkg_resources
import unittest
from unittest.mock import patch

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor

from test import config_files
from test import test_code


class TestPreprocessorPrint(unittest.TestCase):
    def _load_file(self, asm_filename: str, log_verbosity: int):
        fp = pkg_resources.files(config_files).joinpath('test_compilation_control.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )
        label_scope = GlobalLabelScope(isa_model.registers)
        preprocessor = Preprocessor()

        asm_fp = pkg_resources.files(test_code).joinpath(asm_filename)
        asm_obj = AssemblyFile(asm_fp, label_scope)

        return asm_obj.load_line_objects(
            isa_model,
            [],
            memzone_mngr,
            preprocessor,
            log_verbosity,
        )

    def _model_and_state(self):
        fp = pkg_resources.files(config_files).joinpath('test_compilation_control.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )
        label_scope = GlobalLabelScope(isa_model.registers)
        preprocessor = Preprocessor()
        return isa_model, memzone_mngr, label_scope, preprocessor

    def test_print_basic_always(self):
        with patch('click.echo') as mock_echo:
            self._load_file('test_preprocessor_print_basic.asm', log_verbosity=0)
            calls = [c.args[0] for c in mock_echo.call_args_list if isinstance(c.args[0], str)]
            self.assertIn('hello world', calls, 'should print once at any verbosity')

    def test_print_min_verbosity_gated(self):
        with patch('click.echo') as mock_echo_low:
            self._load_file('test_preprocessor_print_min_verbosity.asm', log_verbosity=1)
            calls_low = [c.args[0] for c in mock_echo_low.call_args_list if isinstance(c.args[0], str)]
            self.assertNotIn('level two', calls_low, 'should not print when verbosity < minimum')
        with patch('click.echo') as mock_echo_high:
            self._load_file('test_preprocessor_print_min_verbosity.asm', log_verbosity=2)
            calls_high = [c.args[0] for c in mock_echo_high.call_args_list if isinstance(c.args[0], str)]
            self.assertIn('level two', calls_high, 'should print when verbosity >= minimum')

    def test_print_suppressed_in_false_condition(self):
        with patch('click.echo') as mock_echo:
            self._load_file('test_preprocessor_print_condition.asm', log_verbosity=3)
            calls = [c.args[0] for c in mock_echo.call_args_list if isinstance(c.args[0], str)]
            self.assertNotIn('should not print', calls, 'should not print inside inactive conditional')

    def test_print_suppressed_when_muted(self):
        with patch('click.echo') as mock_echo:
            self._load_file('test_preprocessor_print_mute.asm', log_verbosity=3)
            # before and after should print, middle should be muted
            calls = [c.args[0] for c in mock_echo.call_args_list if isinstance(c.args[0], str)]
            self.assertIn('before', calls)
            self.assertIn('after', calls)
            self.assertNotIn('muted', calls)

    def test_print_malformed_raises(self):
        with self.assertRaises(SystemExit):
            with patch('click.echo') as mock_echo:
                self._load_file('test_preprocessor_print_malformed.asm', log_verbosity=3)
                calls = [c.args[0] for c in mock_echo.call_args_list if isinstance(c.args[0], str)]
                self.assertEqual(calls.count('unterminated'), 0, 'no printing should occur when malformed')

    def test_print_line_object_parsing_basic(self):
        isa_model, memzone_mngr, label_scope, preprocessor = self._model_and_state()
        lineid = LineIdentifier(10, 'test_print_line_object_parsing_basic')
        with patch('click.echo') as mock_echo:
            objs = LineOjectFactory.parse_line(
                lineid,
                '#print "inline"',
                isa_model,
                label_scope,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                # a fresh condition stack defaults to active and unmuted
                __import__('bespokeasm.assembler.preprocessor.condition_stack', fromlist=['ConditionStack']).ConditionStack(),
                0,
            )
            self.assertEqual(len(objs), 1, 'one line object should be produced')
            self.assertIsInstance(objs[0], PreprocessorLine, 'should be a preprocessor line object')
            calls = [c.args[0] for c in mock_echo.call_args_list if isinstance(c.args[0], str)]
            self.assertIn('inline', calls)

    def test_print_line_object_parsing_min_verbosity(self):
        isa_model, memzone_mngr, label_scope, preprocessor = self._model_and_state()
        lineid = LineIdentifier(11, 'test_print_line_object_parsing_min_verbosity')
        # below threshold
        with patch('click.echo') as mock_echo_low:
            _ = LineOjectFactory.parse_line(
                lineid,
                '#print 3 "gated"',
                isa_model,
                label_scope,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                __import__('bespokeasm.assembler.preprocessor.condition_stack', fromlist=['ConditionStack']).ConditionStack(),
                2,
            )
            calls_low = [c.args[0] for c in mock_echo_low.call_args_list if isinstance(c.args[0], str)]
            self.assertNotIn('gated', calls_low, 'should not print below threshold')
        # at threshold
        with patch('click.echo') as mock_echo_high:
            _ = LineOjectFactory.parse_line(
                lineid,
                '#print 3 "gated"',
                isa_model,
                label_scope,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                __import__('bespokeasm.assembler.preprocessor.condition_stack', fromlist=['ConditionStack']).ConditionStack(),
                3,
            )
            calls_high = [c.args[0] for c in mock_echo_high.call_args_list if isinstance(c.args[0], str)]
            self.assertIn('gated', calls_high)

    def test_print_color_basic(self):
        with patch('click.secho') as mock_secho:
            self._load_file('test_preprocessor_print_color_basic.asm', log_verbosity=0)
            # ensure colored output used with correct fg
            self.assertTrue(any((args, kwargs)[1].get('fg') == 'red' and (args, kwargs)[0][0] == 'red message'
                                for args, kwargs in [(c.args, c.kwargs) for c in mock_secho.call_args_list]))

    def test_print_color_with_min_verbosity(self):
        # below threshold
        with patch('click.secho') as mock_secho_low:
            self._load_file('test_preprocessor_print_color_min_verbosity.asm', log_verbosity=1)
            self.assertEqual(len(mock_secho_low.call_args_list), 0, 'should not print below threshold')
        # at threshold
        with patch('click.secho') as mock_secho_high:
            self._load_file('test_preprocessor_print_color_min_verbosity.asm', log_verbosity=2)
            self.assertTrue(any(kwargs.get('fg') == 'yellow' and args[0] == 'level two yellow'
                                for args, kwargs in [(c.args, c.kwargs) for c in mock_secho_high.call_args_list]))

    def test_print_color_invalid_raises(self):
        with self.assertRaises(SystemExit):
            with patch('click.secho') as _:
                self._load_file('test_preprocessor_print_color_invalid.asm', log_verbosity=3)


if __name__ == '__main__':
    unittest.main()
