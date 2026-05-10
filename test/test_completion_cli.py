import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from bespokeasm.cli import CommandHandlers
from bespokeasm.completion_cli import _noop
from bespokeasm.completion_cli import _NOOP_HANDLERS
from bespokeasm.completion_cli import completion_entry_point
from bespokeasm.completion_cli import entry_point


class TestCompletionCli(unittest.TestCase):
    def test_noop_returns_none(self):
        """_noop accepts arbitrary args/kwargs and unconditionally returns None."""
        self.assertIsNone(_noop())
        self.assertIsNone(_noop(1, 2, 3, foo='bar'))

    def test_noop_handlers_are_all_the_noop_callable(self):
        """Every slot of _NOOP_HANDLERS points to the same _noop function.

        Completion only needs the CLI's command/option surface, not real handler
        execution, so all five slots reuse one no-op callable.
        """
        for slot in CommandHandlers._fields:
            self.assertIs(getattr(_NOOP_HANDLERS, slot), _noop)

    def test_completion_entry_point_uses_noop_handlers_by_default(self):
        """When no handlers are passed, completion_entry_point builds the CLI with _NOOP_HANDLERS."""
        fake_main = MagicMock()
        with patch('bespokeasm.completion_cli.build_cli', return_value=fake_main) as build_cli_mock:
            completion_entry_point()
        build_cli_mock.assert_called_once_with(_NOOP_HANDLERS)
        fake_main.assert_called_once_with(auto_envvar_prefix='BESPOKEASM')

    def test_completion_entry_point_uses_provided_handlers(self):
        """When handlers are passed (the __main__ path), they replace the default _NOOP_HANDLERS."""
        custom = CommandHandlers(
            compile=lambda *a, **k: None,
            docs=lambda *a, **k: None,
            vscode=lambda *a, **k: None,
            sublime=lambda *a, **k: None,
            vim=lambda *a, **k: None,
        )
        fake_main = MagicMock()
        with patch('bespokeasm.completion_cli.build_cli', return_value=fake_main) as build_cli_mock:
            completion_entry_point(custom)
        build_cli_mock.assert_called_once_with(custom)
        fake_main.assert_called_once_with(auto_envvar_prefix='BESPOKEASM')

    def test_entry_point_delegates_to_completion_entry_point(self):
        """The legacy entry_point() is a thin alias forwarding to completion_entry_point()."""
        with patch('bespokeasm.completion_cli.completion_entry_point') as ep_mock:
            ep_mock.return_value = 'sentinel'
            result = entry_point()
        ep_mock.assert_called_once_with()
        self.assertEqual(result, 'sentinel')


if __name__ == '__main__':
    unittest.main()
