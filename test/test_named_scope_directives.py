import unittest

from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line.create_scope import CreateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.deactivate_scope import DeactivateScopeLine
from bespokeasm.assembler.line_object.preprocessor_line.use_scope import UseScopeLine
from bespokeasm.assembler.memory_zone import MemoryZone


class TestNamedScopeDirectives(unittest.TestCase):

    def setUp(self):
        self.named_scope_manager = NamedScopeManager()
        self.line_id = LineIdentifier(1, 'test.asm')
        self.memzone = MemoryZone(16, 0, 1000, 'test')  # address_bits, start, end, name
        # Create a minimal ISA model for testing
        self.isa_model = None  # We'll mock this as needed

    def test_create_scope_line_basic(self):
        """Test CreateScopeLine with basic syntax."""
        instruction = '#create-scope "test_scope" prefix="ts_"'

        line = CreateScopeLine(
            self.line_id,
            instruction,
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            0
        )

        self.assertEqual(line.scope_name, 'test_scope')
        self.assertEqual(line.prefix, 'ts_')

        # Verify it was added to the manager
        definition = self.named_scope_manager.get_scope_definition('test_scope')
        self.assertIsNotNone(definition)
        self.assertEqual(definition.prefix, 'ts_')

    def test_create_scope_line_default_prefix(self):
        """Test CreateScopeLine with default prefix."""
        instruction = '#create-scope "test_scope"'

        line = CreateScopeLine(
            self.line_id,
            instruction,
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            0
        )

        self.assertEqual(line.scope_name, 'test_scope')
        self.assertEqual(line.prefix, '_')

    def test_create_scope_line_invalid_syntax(self):
        """Test CreateScopeLine with invalid syntax."""
        instruction = '#create-scope invalid syntax'

        with self.assertRaises(SystemExit):
            CreateScopeLine(
                self.line_id,
                instruction,
                '',
                self.memzone,
                self.isa_model,
                self.named_scope_manager,
                0
            )

    def test_create_scope_line_empty_name(self):
        """Test CreateScopeLine with empty scope name."""
        instruction = '#create-scope ""'

        with self.assertRaises(SystemExit):
            CreateScopeLine(
                self.line_id,
                instruction,
                '',
                self.memzone,
                self.isa_model,
                self.named_scope_manager,
                0
            )

    def test_create_scope_line_period_prefix_error(self):
        """Test CreateScopeLine with period prefix is rejected."""
        instruction = '#create-scope "bad_scope" prefix=".invalid"'

        with self.assertRaises(SystemExit):
            CreateScopeLine(
                self.line_id,
                instruction,
                '',
                self.memzone,
                self.isa_model,
                self.named_scope_manager,
                0
            )

    def test_use_scope_line_basic(self):
        """Test UseScopeLine with defined scope."""
        # First create the scope
        self.named_scope_manager.create_scope('test_scope', 'ts_', self.line_id)

        instruction = '#use-scope "test_scope"'

        line = UseScopeLine(
            self.line_id,
            instruction,
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            'test.asm',
            0
        )

        self.assertEqual(line.scope_name, 'test_scope')
        self.assertEqual(line.filename, 'test.asm')

    def test_use_scope_line_invalid_syntax(self):
        """Test UseScopeLine with invalid syntax."""
        instruction = '#use-scope invalid'

        with self.assertRaises(SystemExit):
            UseScopeLine(
                self.line_id,
                instruction,
                '',
                self.memzone,
                self.isa_model,
                self.named_scope_manager,
                'test.asm',
                0
            )

    def test_deactivate_scope_line_basic(self):
        """Test DeactivateScopeLine with active scope."""
        # Create and activate scope
        self.named_scope_manager.create_scope('test_scope', 'ts_', self.line_id)

        instruction = '#deactivate-scope "test_scope"'

        line = DeactivateScopeLine(
            self.line_id,
            instruction,
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            'test.asm',
            0
        )

        self.assertEqual(line.scope_name, 'test_scope')

    def test_deactivate_scope_line_invalid_syntax(self):
        """Test DeactivateScopeLine with invalid syntax."""
        instruction = '#deactivate-scope invalid'

        with self.assertRaises(SystemExit):
            DeactivateScopeLine(
                self.line_id,
                instruction,
                '',
                self.memzone,
                self.isa_model,
                self.named_scope_manager,
                'test.asm',
                0
            )

    def test_complete_workflow(self):
        """Test a complete workflow with all three directives."""
        # Create scope
        CreateScopeLine(
            self.line_id,
            '#create-scope "graphics" prefix="gfx_"',
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            0
        )

        # Use scope
        UseScopeLine(
            LineIdentifier(2, 'test.asm'),
            '#use-scope "graphics"',
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            'test.asm',
            0
        )

        # Deactivate scope
        DeactivateScopeLine(
            LineIdentifier(3, 'test.asm'),
            '#deactivate-scope "graphics"',
            '',
            self.memzone,
            self.isa_model,
            self.named_scope_manager,
            'test.asm',
            0
        )

        # But scope definition should still exist
        definition = self.named_scope_manager.get_scope_definition('graphics')
        self.assertIsNotNone(definition)
        self.assertEqual(definition.prefix, 'gfx_')

    def test_multiple_active_scopes_precedence(self):
        """Test that when multiple scopes are active, most recently activated takes precedence.

        This test validates the precedence behavior when multiple scopes are active.
        If a label could match multiple scope prefixes, the most recently activated
        scope's prefix is checked first due to the order in the active scope list.
        """
        from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
        from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList

        # Create two scopes with different prefixes
        self.named_scope_manager.create_scope('scope_a', 'a_', LineIdentifier(1, 'test.asm'))
        self.named_scope_manager.create_scope('scope_b', 'b_', LineIdentifier(2, 'test.asm'))

        # Create active scope list
        active_scopes = ActiveNamedScopeList(self.named_scope_manager)

        # Activate both scopes (scope_b activated second, so it should be first in list)
        active_scopes.activate_named_scope('scope_a')
        active_scopes.activate_named_scope('scope_b')

        # Verify scope_b is first in the list (most recent activation)
        self.assertEqual(active_scopes[0], 'scope_b')
        self.assertEqual(active_scopes[1], 'scope_a')

        # Set label values in each scope
        scope_a_def = self.named_scope_manager.get_scope_definition('scope_a')
        scope_b_def = self.named_scope_manager.get_scope_definition('scope_b')

        scope_a_def.set_label_value('a_label', 100, LineIdentifier(3, 'test.asm'), LabelScopeType.NAMED)
        scope_b_def.set_label_value('b_label', 200, LineIdentifier(4, 'test.asm'), LabelScopeType.NAMED)

        # Create a dummy current scope for fallback
        current_scope = LabelScope(LabelScopeType.GLOBAL, None, 'global')

        # Get label value for b_label - should return value from scope_b
        value = self.named_scope_manager.get_label_value(
            'b_label',
            current_scope,
            active_scopes,
            LineIdentifier(5, 'test.asm')
        )

        self.assertEqual(value, 200, 'Label with b_ prefix should be found in scope_b')

        # Get label value for a_label - should return value from scope_a
        value = self.named_scope_manager.get_label_value(
            'a_label',
            current_scope,
            active_scopes,
            LineIdentifier(6, 'test.asm')
        )

        self.assertEqual(value, 100, 'Label with a_ prefix should be found in scope_a')

        # Re-activate scope_a to move it to the front
        active_scopes.activate_named_scope('scope_a')

        # Now scope_a should be first
        self.assertEqual(active_scopes[0], 'scope_a')
        self.assertEqual(active_scopes[1], 'scope_b')

        # Labels should still be found correctly based on their prefix
        value = self.named_scope_manager.get_label_value(
            'a_label',
            current_scope,
            active_scopes,
            LineIdentifier(7, 'test.asm')
        )

        self.assertEqual(value, 100, 'Label lookup should still work after re-activation')


if __name__ == '__main__':
    unittest.main()
