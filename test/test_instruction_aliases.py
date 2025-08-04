import importlib.resources as pkg_resources
import os
import tempfile
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack
from ruamel.yaml import YAML


class TestInstructionAliases(unittest.TestCase):
    """Test cases for instruction alias functionality"""

    @classmethod
    def setUpClass(cls):
        """Create a temporary config file with instruction aliases"""
        cls.config_data = {
            "general": {
                "min_version": "0.5.1",
                "word_size": 8,
                "address_size": 16,
                "registers": ["a", "b", "x", "y", "sp", "pc"],
            },
            "instructions": {
                # Jump to subroutine with multiple aliases
                "jsr": {
                    "aliases": ["call", "jump_to_subroutine"],
                    "bytecode": {"size": 8, "value": 0x20},
                    "operands": [
                        {
                            "type": "numeric",
                            "size": 16,
                        }
                    ],
                },
                # Move instruction with common aliases
                "mov": {
                    "aliases": ["move", "mv"],
                    "bytecode": {"size": 8, "value": 0x10},
                    "operands": [
                        {
                            "type": "register",
                            "register_set": "general",
                        },
                        {
                            "type": "register", 
                            "register_set": "general",
                        }
                    ],
                },
                # Return instruction with single alias
                "ret": {
                    "aliases": ["rts"],
                    "bytecode": {"size": 8, "value": 0x60},
                },
                # No operation - no aliases
                "nop": {
                    "bytecode": {"size": 8, "value": 0xEA},
                },
                # Load accumulator with various addressing modes
                "lda": {
                    "aliases": ["load_a", "ld_a"],
                    "operands": [
                        {
                            "type": "numeric",
                            "size": 8,
                        }
                    ],
                    "bytecode": {"size": 8, "value": 0xA9},
                },
                # Store accumulator
                "sta": {
                    "aliases": ["store_a", "st_a"],
                    "operands": [
                        {
                            "type": "numeric",
                            "size": 16,
                        }
                    ],
                    "bytecode": {"size": 8, "value": 0x8D},
                },
            },
            "operand_sets": {
                "general": ["a", "b", "x", "y"],
            },
        }
        
        # Create temporary config file
        cls.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml = YAML()
        yaml.dump(cls.config_data, cls.temp_file)
        cls.temp_file.close()
        cls.config_file_path = cls.temp_file.name

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary config file"""
        if hasattr(cls, 'temp_file'):
            try:
                os.unlink(cls.config_file_path)
            except:
                pass

    def setUp(self):
        """Set up test fixtures"""
        self.isa_model = AssemblerModel(self.config_file_path, 0)
        self.memzone_mngr = MemoryZoneManager(
            self.isa_model.address_size,
            self.isa_model.default_origin,
            self.isa_model.predefined_memory_zones,
        )
        self.label_scope = GlobalLabelScope(self.isa_model.registers)
        self.label_scope.set_label_value('test_label', 0x1234, LineIdentifier(1, 'test'))
        self.label_scope.set_label_value('start', 0x8000, LineIdentifier(1, 'test'))
        self.preprocessor = Preprocessor()
        self.condition_stack = ConditionStack()

    def test_instruction_set_contains_aliases(self):
        """Test that InstructionSet contains both canonical and alias mnemonics"""
        instr_set = self.isa_model.instructions
        
        # Check canonical instructions
        self.assertIn('jsr', instr_set)
        self.assertIn('mov', instr_set)
        self.assertIn('ret', instr_set)
        self.assertIn('nop', instr_set)
        
        # Check aliases
        self.assertIn('call', instr_set)
        self.assertIn('jump_to_subroutine', instr_set)
        self.assertIn('move', instr_set)
        self.assertIn('mv', instr_set)
        self.assertIn('rts', instr_set)
        
        # Verify aliases point to same instruction object
        self.assertIs(instr_set['call'], instr_set['jsr'])
        self.assertIs(instr_set['jump_to_subroutine'], instr_set['jsr'])
        self.assertIs(instr_set['move'], instr_set['mov'])
        self.assertIs(instr_set['mv'], instr_set['mov'])
        self.assertIs(instr_set['rts'], instr_set['ret'])

    def test_operation_mnemonics_includes_aliases(self):
        """Test that operation_mnemonics property includes all aliases"""
        mnemonics = set(self.isa_model.operation_mnemonics)
        
        # Should include all canonical instructions
        for canonical in ['jsr', 'mov', 'ret', 'nop', 'lda', 'sta']:
            self.assertIn(canonical, mnemonics)
        
        # Should include all aliases
        for alias in ['call', 'jump_to_subroutine', 'move', 'mv', 'rts', 'load_a', 'ld_a', 'store_a', 'st_a']:
            self.assertIn(alias, mnemonics)

    def test_parse_jsr_with_aliases(self):
        """Test parsing JSR instruction using different aliases"""
        test_cases = [
            ('jsr', 'jsr test_label', 'canonical mnemonic'),
            ('call', 'call test_label', 'common alias'),
            ('jump_to_subroutine', 'jump_to_subroutine test_label', 'verbose alias'),
        ]
        
        for mnemonic, code_line, description in test_cases:
            with self.subTest(mnemonic=mnemonic, description=description):
                lineid = LineIdentifier(10, f'test_{mnemonic}')
                objs = LineOjectFactory.parse_line(
                    lineid,
                    code_line,
                    self.isa_model,
                    self.label_scope,
                    self.memzone_mngr.global_zone,
                    self.memzone_mngr,
                    self.preprocessor,
                    self.condition_stack,
                    0,
                )
                
                self.assertEqual(len(objs), 1, f'Should parse one instruction for {mnemonic}')
                self.assertIsInstance(objs[0], InstructionLine)
                
                instr = objs[0]
                instr.set_start_address(0x100)
                instr.label_scope = self.label_scope
                instr.generate_words()
                
                # All should generate same bytecode
                words = instr.get_words()
                self.assertEqual(len(words), 3, f'{mnemonic} should generate 3 bytes')
                self.assertEqual(words[0].value, 0x20, f'{mnemonic} opcode should be 0x20')
                self.assertEqual(words[1].value, 0x34, f'{mnemonic} low byte of address')
                self.assertEqual(words[2].value, 0x12, f'{mnemonic} high byte of address')

    def test_parse_mov_with_aliases(self):
        """Test parsing MOV instruction using different aliases"""
        test_cases = [
            ('mov', 'mov a, b'),
            ('move', 'move a, b'),
            ('mv', 'mv a, b'),
        ]
        
        for mnemonic, code_line in test_cases:
            with self.subTest(mnemonic=mnemonic):
                lineid = LineIdentifier(20, f'test_{mnemonic}')
                objs = LineOjectFactory.parse_line(
                    lineid,
                    code_line,
                    self.isa_model,
                    self.label_scope,
                    self.memzone_mngr.global_zone,
                    self.memzone_mngr,
                    self.preprocessor,
                    self.condition_stack,
                    0,
                )
                
                self.assertEqual(len(objs), 1)
                self.assertIsInstance(objs[0], InstructionLine)
                
                instr = objs[0]
                instr.set_start_address(0x200)
                instr.label_scope = self.label_scope
                instr.generate_words()
                
                words = instr.get_words()
                self.assertEqual(len(words), 1)
                self.assertEqual(words[0].value, 0x10, f'{mnemonic} should have opcode 0x10')

    def test_parse_ret_with_alias(self):
        """Test parsing RET instruction and its RTS alias"""
        for mnemonic in ['ret', 'rts']:
            with self.subTest(mnemonic=mnemonic):
                lineid = LineIdentifier(30, f'test_{mnemonic}')
                objs = LineOjectFactory.parse_line(
                    lineid,
                    mnemonic,
                    self.isa_model,
                    self.label_scope,
                    self.memzone_mngr.global_zone,
                    self.memzone_mngr,
                    self.preprocessor,
                    self.condition_stack,
                    0,
                )
                
                self.assertEqual(len(objs), 1)
                self.assertIsInstance(objs[0], InstructionLine)
                
                instr = objs[0]
                instr.set_start_address(0x300)
                instr.label_scope = self.label_scope
                instr.generate_words()
                
                words = instr.get_words()
                self.assertEqual(len(words), 1)
                self.assertEqual(words[0].value, 0x60)

    def test_instruction_without_aliases(self):
        """Test that instructions without aliases still work correctly"""
        lineid = LineIdentifier(40, 'test_nop')
        objs = LineOjectFactory.parse_line(
            lineid,
            'nop',
            self.isa_model,
            self.label_scope,
            self.memzone_mngr.global_zone,
            self.memzone_mngr,
            self.preprocessor,
            self.condition_stack,
            0,
        )
        
        self.assertEqual(len(objs), 1)
        self.assertIsInstance(objs[0], InstructionLine)
        
        instr = objs[0]
        instr.set_start_address(0x400)
        instr.label_scope = self.label_scope
        instr.generate_words()
        
        words = instr.get_words()
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].value, 0xEA)

    def test_aliases_in_complex_lines(self):
        """Test aliases in lines with labels and multiple instructions"""
        # Test label with aliased instruction
        lineid = LineIdentifier(50, 'test_label_with_alias')
        objs = LineOjectFactory.parse_line(
            lineid,
            'loop_start: call start',
            self.isa_model,
            self.label_scope,
            self.memzone_mngr.global_zone,
            self.memzone_mngr,
            self.preprocessor,
            self.condition_stack,
            0,
        )
        
        self.assertEqual(len(objs), 2)
        self.assertIsInstance(objs[0], LabelLine)
        self.assertIsInstance(objs[1], InstructionLine)
        self.assertEqual(objs[0].get_label(), 'loop_start')
        
        # Generate bytecode for the instruction
        objs[1].set_start_address(0x500)
        objs[1].label_scope = self.label_scope
        objs[1].generate_words()
        words = objs[1].get_words()
        self.assertEqual(words[0].value, 0x20)  # JSR opcode

        # Test multiple instructions with aliases on same line
        lineid = LineIdentifier(60, 'test_multiple_aliases')
        objs = LineOjectFactory.parse_line(
            lineid,
            'mv a, b rts',
            self.isa_model,
            self.label_scope,
            self.memzone_mngr.global_zone,
            self.memzone_mngr,
            self.preprocessor,
            self.condition_stack,
            0,
        )
        
        self.assertEqual(len(objs), 2)
        self.assertIsInstance(objs[0], InstructionLine)
        self.assertIsInstance(objs[1], InstructionLine)
        
        # Check first instruction (mv -> mov)
        objs[0].set_start_address(0x600)
        objs[0].label_scope = self.label_scope
        objs[0].generate_words()
        self.assertEqual(objs[0].get_words()[0].value, 0x10)  # MOV opcode
        
        # Check second instruction (rts -> ret)
        objs[1].set_start_address(0x601)
        objs[1].label_scope = self.label_scope
        objs[1].generate_words()
        self.assertEqual(objs[1].get_words()[0].value, 0x60)  # RET opcode

    def test_case_insensitive_aliases(self):
        """Test that aliases are case-insensitive"""
        test_cases = [
            ('CALL test_label', 'uppercase alias'),
            ('Call test_label', 'mixed case alias'),
            ('CaLl test_label', 'random case alias'),
        ]
        
        for code_line, description in test_cases:
            with self.subTest(description=description):
                lineid = LineIdentifier(70, f'test_case_{description}')
                objs = LineOjectFactory.parse_line(
                    lineid,
                    code_line,
                    self.isa_model,
                    self.label_scope,
                    self.memzone_mngr.global_zone,
                    self.memzone_mngr,
                    self.preprocessor,
                    self.condition_stack,
                    0,
                )
                
                self.assertEqual(len(objs), 1)
                self.assertIsInstance(objs[0], InstructionLine)
                
                instr = objs[0]
                instr.set_start_address(0x700)
                instr.label_scope = self.label_scope
                instr.generate_words()
                
                self.assertEqual(instr.get_words()[0].value, 0x20)  # JSR opcode

    def test_lda_sta_aliases(self):
        """Test load and store aliases with operands"""
        # Test LDA aliases
        for mnemonic in ['lda', 'load_a', 'ld_a']:
            with self.subTest(mnemonic=mnemonic):
                lineid = LineIdentifier(80, f'test_{mnemonic}')
                objs = LineOjectFactory.parse_line(
                    lineid,
                    f'{mnemonic} $42',
                    self.isa_model,
                    self.label_scope,
                    self.memzone_mngr.global_zone,
                    self.memzone_mngr,
                    self.preprocessor,
                    self.condition_stack,
                    0,
                )
                
                self.assertEqual(len(objs), 1)
                instr = objs[0]
                instr.set_start_address(0x800)
                instr.label_scope = self.label_scope
                instr.generate_words()
                
                words = instr.get_words()
                self.assertEqual(len(words), 2)
                self.assertEqual(words[0].value, 0xA9)  # LDA immediate opcode
                self.assertEqual(words[1].value, 0x42)  # operand value

        # Test STA aliases
        for mnemonic in ['sta', 'store_a', 'st_a']:
            with self.subTest(mnemonic=mnemonic):
                lineid = LineIdentifier(90, f'test_{mnemonic}')
                objs = LineOjectFactory.parse_line(
                    lineid,
                    f'{mnemonic} test_label',
                    self.isa_model,
                    self.label_scope,
                    self.memzone_mngr.global_zone,
                    self.memzone_mngr,
                    self.preprocessor,
                    self.condition_stack,
                    0,
                )
                
                self.assertEqual(len(objs), 1)
                instr = objs[0]
                instr.set_start_address(0x900)
                instr.label_scope = self.label_scope
                instr.generate_words()
                
                words = instr.get_words()
                self.assertEqual(len(words), 3)
                self.assertEqual(words[0].value, 0x8D)  # STA absolute opcode

    def test_unknown_alias_fails(self):
        """Test that unknown mnemonics (not aliases) still fail"""
        lineid = LineIdentifier(100, 'test_unknown')
        
        with self.assertRaises(SystemExit, msg='Unknown mnemonic should fail'):
            LineOjectFactory.parse_line(
                lineid,
                'unknown_instruction $42',
                self.isa_model,
                self.label_scope,
                self.memzone_mngr.global_zone,
                self.memzone_mngr,
                self.preprocessor,
                self.condition_stack,
                0,
            )


if __name__ == '__main__':
    unittest.main()