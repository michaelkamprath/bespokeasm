import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bespokeasm.__main__ import _build_main
from bespokeasm.cli import _default_completion_path
from click.testing import CliRunner


class TestInstallCompletion(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.main = _build_main()

    def _invoke(self, *extra_args, env=None, prog_name='bespokeasm'):
        # Pass --prog-name explicitly because under pytest sys.argv[0] is the test
        # runner path (e.g. '__main__.py'), not 'bespokeasm', which would otherwise
        # leak into the generated script's env-var and zstyle group names.
        args = ['install-completion']
        if prog_name is not None:
            args.extend(['--prog-name', prog_name])
        args.extend(extra_args)
        return self.runner.invoke(self.main, args, env=env, catch_exceptions=False)

    def _read(self, path):
        return Path(path).read_text()

    # ---- Happy paths per shell ----
    # Verify the install-completion command produces a usable shell-completion script
    # at the requested path and emits shell-appropriate post-install guidance.

    def test_bash_writes_file_with_completion_markers(self):
        """`install-completion --shell bash --path X` writes a Click-bash-style script and prints bash guidance."""
        with self.runner.isolated_filesystem() as tmp:
            dest = os.path.join(tmp, 'bespokeasm.bash')
            result = self._invoke('--shell', 'bash', '--path', dest)
            self.assertEqual(result.exit_code, 0, result.output)
            script = self._read(dest)
            # Click's bash completion script references the prog-name's completion env var.
            self.assertIn('_BESPOKEASM_COMPLETE', script, 'bash script wires Click completion env var')
            self.assertIn(f'Installed bash completions at {dest}', result.output)
            self.assertIn('bash-completion', result.output, 'bash-specific guidance shown')

    def test_zsh_injects_zstyle_block(self):
        """zsh output is augmented with bespokeasm-specific zstyle preferences (sort, list-packed, group-order)."""
        with self.runner.isolated_filesystem() as tmp:
            dest = os.path.join(tmp, '_bespokeasm')
            result = self._invoke('--shell', 'zsh', '--path', dest)
            self.assertEqual(result.exit_code, 0, result.output)
            script = self._read(dest)
            # zsh-specific tail injected by install_completion.
            self.assertIn('# bespokeasm completion preferences', script)
            self.assertIn("zstyle ':completion:*:*:bespokeasm:*' sort false", script)
            self.assertIn("zstyle ':completion:*:*:bespokeasm:*' list-packed true", script)
            self.assertIn('_BESPOKEASM_COMPLETE', script, 'click-generated zsh body present')
            self.assertIn('Installed zsh completions', result.output)
            self.assertIn('fpath', result.output, 'zsh-specific guidance shown')

    def test_fish_writes_file_and_emits_fish_guidance(self):
        """fish path writes a script and surfaces fish-specific post-install guidance."""
        with self.runner.isolated_filesystem() as tmp:
            dest = os.path.join(tmp, 'bespokeasm.fish')
            result = self._invoke('--shell', 'fish', '--path', dest)
            self.assertEqual(result.exit_code, 0, result.output)
            script = self._read(dest)
            self.assertIn('_BESPOKEASM_COMPLETE', script)
            self.assertIn('Installed fish completions', result.output)
            self.assertIn('fish', result.output.lower())

    # ---- Shell auto-detection ----
    # When --shell is omitted, the command falls back to _detect_shell() which
    # inspects the SHELL environment variable; these tests cover the resolution
    # paths and the two error branches (no shell detected; unsupported value).

    def test_auto_detect_uses_shell_env_var(self):
        """With SHELL=/bin/bash and no --shell flag, _detect_shell picks 'bash' for install."""
        with self.runner.isolated_filesystem() as tmp:
            dest = os.path.join(tmp, 'auto.bash')
            # SHELL=/bin/bash should let _detect_shell pick 'bash' without --shell.
            result = self._invoke('--path', dest, env={'SHELL': '/bin/bash'})
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn('Installed bash completions', result.output)

    def test_no_shell_detected_exits_with_error(self):
        """If --shell is omitted and SHELL/PSModulePath provide no signal, exit 1 with a helpful message."""
        result = self._invoke(env={'SHELL': '', 'PSModulePath': ''})
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Could not detect shell', result.output)

    def test_unsupported_detected_shell_exits_with_error(self):
        """Defensive guard: if _detect_shell ever returns an unsupported value, exit 1 with the supported list.

        _detect_shell currently filters to SUPPORTED_COMPLETION_SHELLS, so this
        branch is unreachable through normal flow. The mock locks in the safety
        net so a future detector change can't silently bypass the guard.
        """
        with patch('bespokeasm.cli._detect_shell', return_value='tcsh'):
            result = self._invoke()
        self.assertEqual(result.exit_code, 1)
        self.assertIn('not supported', result.output)
        self.assertIn('bash', result.output, 'error lists supported shells')

    # ---- Click completion-class fallback ----

    def test_missing_completion_class_exits_with_error(self):
        """If Click's get_completion_class returns None, exit 1 with 'unavailable' rather than crashing."""
        with patch('click.shell_completion.get_completion_class', return_value=None):
            result = self._invoke('--shell', 'bash')
        self.assertEqual(result.exit_code, 1)
        self.assertIn('unavailable', result.output)

    # ---- Default destination paths ----

    def test_default_completion_path_per_shell(self):
        """Lock per-shell default install paths so user-visible location changes require an explicit update."""
        bash_path = _default_completion_path('bash', 'myprog')
        self.assertEqual(bash_path.name, 'myprog')
        self.assertIn('bash-completion/completions', str(bash_path))

        zsh_path = _default_completion_path('zsh', 'myprog')
        self.assertEqual(zsh_path.name, '_myprog')
        self.assertIn('.zfunc', str(zsh_path))

        fish_path = _default_completion_path('fish', 'myprog')
        self.assertEqual(fish_path.name, 'myprog.fish')
        self.assertIn('fish/completions', str(fish_path))

    def test_default_completion_path_unsupported_shell_raises(self):
        """_default_completion_path raises ValueError for shells outside the supported set."""
        with self.assertRaises(ValueError):
            _default_completion_path('tcsh', 'myprog')

    # ---- Custom prog name ----

    def test_custom_prog_name_used_in_zstyle_block(self):
        """A custom --prog-name flows through to the completion env-var name (uppercased,
        dashes->underscores) and to the zstyle group context (verbatim)."""
        with self.runner.isolated_filesystem() as tmp:
            dest = os.path.join(tmp, '_customprog')
            result = self._invoke(
                '--shell', 'zsh', '--path', dest,
                prog_name='custom-prog',
            )
            self.assertEqual(result.exit_code, 0, result.output)
            script = self._read(dest)
            # prog-name is uppercased and dashes -> underscores for the env var.
            self.assertIn('_CUSTOM_PROG_COMPLETE', script)
            # The original (with dash) appears in the zstyle group context.
            self.assertIn("zstyle ':completion:*:*:custom-prog:*' sort false", script)


if __name__ == '__main__':
    unittest.main()
