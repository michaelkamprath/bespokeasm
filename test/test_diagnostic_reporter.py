"""Tests for the DiagnosticReporter class."""
import pytest
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.diagnostic_reporter import InternalAssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier


class TestDiagnosticReporter:
    """Test suite for DiagnosticReporter class."""

    def test_initialization_defaults(self):
        """Test DiagnosticReporter initialization with default values."""
        reporter = DiagnosticReporter()
        assert reporter.warnings_as_errors is False
        assert reporter.verbosity == 0
        assert reporter.diagnostics == ()

    def test_initialization_with_custom_values(self):
        """Test DiagnosticReporter initialization with custom values."""
        reporter = DiagnosticReporter(
            warnings_as_errors=True,
            verbosity=2,
            categories_elevated={'custom'},
        )
        assert reporter.warnings_as_errors is True
        assert reporter.verbosity == 2
        assert reporter._categories_elevated == {'custom'}

    def test_initialization_with_none_categories(self):
        """Test DiagnosticReporter initialization with None categories."""
        reporter = DiagnosticReporter(categories_elevated=None)
        # Default should be {'user', 'flow'}
        assert 'user' in reporter._categories_elevated
        assert 'flow' in reporter._categories_elevated

    def test_diagnostics_property_returns_tuple(self):
        """Test that diagnostics property returns a tuple."""
        reporter = DiagnosticReporter()
        assert isinstance(reporter.diagnostics, tuple)

    def test_diagnostics_empty_initially(self):
        """Test that diagnostics list is empty initially."""
        reporter = DiagnosticReporter()
        assert len(reporter.diagnostics) == 0

    def test_warn_adds_diagnostic(self):
        """Test that warn() adds a diagnostic."""
        reporter = DiagnosticReporter()
        line_id = LineIdentifier(10, 'test.asm')
        reporter.warn(line_id, 'This is a warning')
        diagnostics = reporter.diagnostics
        assert len(diagnostics) == 1
        diag = diagnostics[0]
        assert diag.level == 'warning'
        assert diag.line_id == line_id
        assert diag.message == 'This is a warning'
        assert diag.category == 'user'

    def test_warn_default_category(self):
        """Test warn() uses default 'user' category."""
        reporter = DiagnosticReporter()
        reporter.warn(None, ' warning message')
        assert reporter.diagnostics[0].category == 'user'

    def test_warn_custom_category(self):
        """Test warn() with custom category."""
        reporter = DiagnosticReporter()
        reporter.warn(None, 'warning', category='flow')
        assert reporter.diagnostics[0].category == 'flow'

    def test_warn_with_line_id_none(self):
        """Test warn() with line_id=None."""
        reporter = DiagnosticReporter()
        reporter.warn(None, 'error without line id')
        assert reporter.diagnostics[0].line_id is None

    def test_warn_emits_to_stderr(self, capsys):
        """Test that warn() emits to stderr."""
        reporter = DiagnosticReporter()
        reporter.warn(None, 'warning message')
        captured = capsys.readouterr()
        assert 'WARNING' in captured.err
        assert 'warning message' in captured.err

    def test_warn_writes_to_stderr_format(self, capsys):
        """Test warn() stderr output format."""
        reporter = DiagnosticReporter()
        line_id = LineIdentifier(5, 'test.asm')
        reporter.warn(line_id, 'test warning')
        captured = capsys.readouterr()
        assert 'WARNING' in captured.err
        assert 'test.asm' in captured.err
        assert 'line 5' in captured.err

    def test_info_above_verbosity_threshold(self, capsys):
        """Test info() does nothing when below verbosity threshold."""
        reporter = DiagnosticReporter(verbosity=2)
        reporter.info(None, 'verbose message', min_verbosity=3)
        captured = capsys.readouterr()
        assert captured.err == ''

    def test_info_at_verbosity_threshold(self, capsys):
        """Test info() outputs when at verbosity threshold."""
        reporter = DiagnosticReporter(verbosity=2)
        reporter.info(None, 'message', min_verbosity=2)
        captured = capsys.readouterr()
        assert 'INFO' in captured.err
        assert 'message' in captured.err

    def test_info_above_verbosity_threshold_outputs(self, capsys):
        """Test info() outputs when above verbosity threshold."""
        reporter = DiagnosticReporter(verbosity=2)
        reporter.info(None, 'message', min_verbosity=1)
        captured = capsys.readouterr()
        assert 'INFO' in captured.err
        assert 'message' in captured.err

    def test_info_default_verbosity(self, capsys):
        """Test info() does not output when verbosity is 0 (default)."""
        reporter = DiagnosticReporter()  # default verbosity=0
        reporter.info(None, 'message', min_verbosity=1)
        captured = capsys.readouterr()
        assert captured.err == ''

    def test_info_custom_category(self, capsys):
        """Test info() with custom category."""
        reporter = DiagnosticReporter(verbosity=1)
        reporter.info(None, 'message', category='custom')
        captured = capsys.readouterr()
        assert 'INFO' in captured.err
        assert 'message' in captured.err

    def test_info_include_line_id(self, capsys):
        """Test info() includes line_id in output."""
        reporter = DiagnosticReporter(verbosity=1)
        line_id = LineIdentifier(100, 'source.asm')
        reporter.info(line_id, 'message')
        captured = capsys.readouterr()
        assert 'source.asm' in captured.err
        assert 'line 100' in captured.err

    def test_error_adds_diagnostic_before_exiting(self):
        """Test error() adds a diagnostic before exiting."""
        reporter = DiagnosticReporter()
        # Note: error() calls sys.exit() so we cannot capture stderr in tests.
        # Instead we verify the diagnostic is recorded before exit.
        with pytest.raises(SystemExit) as exc_info:
            reporter.error(None, 'error message')
        # Verify the diagnostic was added
        assert len(reporter._diagnostics) == 1
        diag = reporter._diagnostics[0]
        assert diag.level == 'error'
        assert diag.message == 'error message'
        assert diag.line_id is None
        assert diag.category == 'user'
        assert exc_info.value.code == 'ERROR: error message'

    def test_error_with_line_id(self):
        """Test error() with line_id."""
        reporter = DiagnosticReporter()
        line_id = LineIdentifier(50, 'error.asm')
        with pytest.raises(SystemExit):
            reporter.error(line_id, 'error at line 50')
        assert len(reporter._diagnostics) == 1
        diag = reporter._diagnostics[0]
        assert diag.line_id == line_id

    def test_error_with_color(self):
        """Test error() with color parameter."""
        reporter = DiagnosticReporter()
        with pytest.raises(SystemExit):
            reporter.error(None, 'colored error', color='red')
        assert len(reporter._diagnostics) == 1
        diag = reporter._diagnostics[0]
        assert diag.message == 'colored error'

    def test_warn_warnings_as_errors_elevates_to_error(self):
        """Test warn() elevates to error when warnings_as_errors=True."""
        reporter = DiagnosticReporter(warnings_as_errors=True)
        with pytest.raises(SystemExit) as exc_info:
            reporter.warn(None, 'warning becomes error', category='user')
        # Verify the diagnostic was added as error
        assert len(reporter._diagnostics) == 1
        diag = reporter._diagnostics[0]
        assert diag.level == 'error'
        assert diag.message == 'warning becomes error'
        assert exc_info.value.code == 'ERROR: warning becomes error'

    def test_warn_non_elevated_category_with_warnings_as_errors(self, capsys):
        """Test warn() does not elevate non-elevated category."""
        reporter = DiagnosticReporter(warnings_as_errors=True)
        reporter.warn(None, 'warning', category='info')
        captured = capsys.readouterr()
        assert 'WARNING' in captured.err
        assert 'warning' in captured.err

    def test_diagnostics_accumulate(self):
        """Test that diagnostics accumulate (warn and info only, error exits)."""
        reporter = DiagnosticReporter(verbosity=1)  # Set verbosity to see info
        reporter.warn(None, 'first')
        reporter.info(None, 'second', min_verbosity=1)
        reporter.warn(None, 'third')
        diagnostics = reporter.diagnostics
        assert len(diagnostics) == 3
        assert diagnostics[0].message == 'first'
        assert diagnostics[1].message == 'second'
        assert diagnostics[2].message == 'third'

    def test_diagnostics_does_not_include_info_below_verbosity(self):
        """Test that info() below verbosity does not accumulate."""
        reporter = DiagnosticReporter(verbosity=2)
        reporter.info(None, 'verbose', min_verbosity=3)
        reporter.info(None, 'visible', min_verbosity=1)
        diagnostics = reporter.diagnostics
        assert len(diagnostics) == 1
        assert diagnostics[0].message == 'visible'

    def test_diagnostics_level_values(self):
        """Test diagnostic level values (warn and info only, error exits)."""
        reporter = DiagnosticReporter(verbosity=1)  # Set verbosity to see info
        reporter.warn(None, 'warn message')
        reporter.info(None, 'info message', min_verbosity=1)
        diagnostics = reporter.diagnostics
        assert diagnostics[0].level == 'warning'
        assert diagnostics[1].level == 'info'

    def test_diagnostics_category_values(self):
        """Test diagnostic category values."""
        reporter = DiagnosticReporter()
        reporter.warn(None, 'message', category='custom')
        diagnostics = reporter.diagnostics
        assert diagnostics[0].category == 'custom'

    def test_diagnostics_line_id_values(self):
        """Test diagnostic line_id values."""
        reporter = DiagnosticReporter()
        line_id = LineIdentifier(25, 'test.asm')
        reporter.warn(line_id, 'message')
        diagnostics = reporter.diagnostics
        assert diagnostics[0].line_id is line_id

    def test_diagnostics_is_immutable_tuple(self):
        """Test that diagnostics property returns an immutable tuple."""
        reporter = DiagnosticReporter()
        reporter.warn(None, 'message')
        diagnostics = reporter.diagnostics
        # Check it's a tuple
        assert isinstance(diagnostics, tuple)
        # Check tuple immutability
        with pytest.raises(AttributeError):
            diagnostics.foo = 'bar'

    def test_reporting_errors_reports_assembler_error(self):
        """An AssemblerError is reported with its line id and category."""
        reporter = DiagnosticReporter()
        line_id = LineIdentifier(7, 'test.asm')
        with pytest.raises(SystemExit) as exc_info:
            with reporter.reporting_errors():
                raise AssemblerError(line_id, 'bad operand', category='flow')
        assert str(exc_info.value) == f'ERROR: {line_id} - bad operand'
        diagnostic = reporter.diagnostics[-1]
        assert (diagnostic.level, diagnostic.line_id, diagnostic.message, diagnostic.category) == (
            'error', line_id, 'bad operand', 'flow',
        )

    def test_reporting_errors_reports_internal_error_with_traceback(self, capsys):
        """An InternalAssemblerError is reported as a bug, with its line id and a traceback."""
        reporter = DiagnosticReporter()
        line_id = LineIdentifier(3, 'test.asm')
        with pytest.raises(SystemExit) as exc_info:
            with reporter.reporting_errors():
                raise InternalAssemblerError(line_id, 'invariant violated')
        message = str(exc_info.value)
        assert message.startswith(f'ERROR: {line_id} - INTERNAL: invariant violated')
        assert 'BespokeASM bug' in message
        assert reporter.diagnostics[-1].category == 'internal'
        assert reporter.diagnostics[-1].line_id == line_id
        assert 'Traceback' in capsys.readouterr().err

    def test_internal_error_is_not_an_assembler_error(self):
        """Handlers that discard AssemblerErrors from failed attempts must not swallow bugs."""
        assert not issubclass(InternalAssemblerError, AssemblerError)

    def test_reporting_errors_passes_other_exceptions(self):
        """Exceptions other than the assembler error types propagate unchanged."""
        reporter = DiagnosticReporter()
        with pytest.raises(KeyError):
            with reporter.reporting_errors():
                raise KeyError('x')
        assert reporter.diagnostics == ()
