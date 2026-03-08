import importlib.resources as pkg_resources
import os
import tempfile
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.label_scope.named_scope_manager import ActiveNamedScopeList
from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack

from test import config_files


class TestAssemblerEngine(unittest.TestCase):
    def setUp(self):
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None
        self.diagnostic_reporter = DiagnosticReporter()

    def test_generate_bytes_from_line_objects_8bit_words(self):
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('a_const', 40, 1)
        preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)
        condition_stack = ConditionStack(self.diagnostic_reporter)
        line_objects: list[LineObject] = []

        # this should generate the following bytes: 0x00
        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_8bit_words'),
                'nop ; do nothing',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # this should generate the following bytes: 0x88
        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(1, 'test_generate_bytes_from_line_objects_8bit_words'),
                'the_byte: .byte 0x88 ; label and instruction',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # this should generate the following bytes: 0b01000110 0x01 0x00
        # assuming the address of the_byte is 0x0001 (16-bit address space)
        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(2, 'test_generate_bytes_from_line_objects_8bit_words'),
                'the_instr: mov a, [the_byte] ; label and instruction',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # "assemble" the line objects to a dictionary
        line_dict: dict[int, LineObject] = {}
        active_named_scopes = ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter))
        for lobj in line_objects:
            lobj.set_start_address(lobj.memory_zone.current_address)
            lobj.memory_zone.current_address = lobj.address + lobj.word_count
            lobj.label_scope = label_values
            lobj.active_named_scopes = active_named_scopes
            if isinstance(lobj, LabelLine) and not lobj.is_constant:
                lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
            line_dict[lobj.address] = lobj

        line_objects.sort(key=lambda x: x.address)
        max_generated_address = line_objects[-1].address

        for lobj in line_objects:
            if isinstance(lobj, LineWithWords):
                lobj.generate_words()
        # generate the bytecode
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            Word(0, 8, 8, 'big'),
            memzone_mngr.global_zone.start,
            None,
            2,
        )

        # now see if the right bytes were generated
        self.assertEqual(
            bytecode,
            bytearray([0, 0x88, 0b01000110, 1, 0]),
            'the bytecode should match',
        )

    def test_generate_bytes_from_line_objects_16bit_words(self):
        fp = pkg_resources.files(config_files).joinpath('test_16bit_data_words.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('a_const', 40, 1)
        preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)
        condition_stack = ConditionStack(self.diagnostic_reporter)
        line_objects: list[LineObject] = []

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'nop ; do nothing',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'mov [$1234], [$8899] ; move it',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'my_label: push [$1234] ; push it real good',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'jmp my_label ; get out of here',
                isa_model,
                label_values,
                ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter)),
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # "assemble" the line objects to a dictionary
        line_dict: dict[int, LineObject] = {}
        active_named_scopes = ActiveNamedScopeList(NamedScopeManager(self.diagnostic_reporter))
        for lobj in line_objects:
            lobj.set_start_address(lobj.memory_zone.current_address)
            lobj.memory_zone.current_address = lobj.address + lobj.word_count
            lobj.label_scope = label_values
            lobj.active_named_scopes = active_named_scopes
            if isinstance(lobj, LabelLine) and not lobj.is_constant:
                lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
            line_dict[lobj.address] = lobj

        line_objects.sort(key=lambda x: x.address)
        max_generated_address = line_objects[-1].address
        for lobj in line_objects:
            if isinstance(lobj, LineWithWords):
                lobj.generate_words()
        # generate the bytecode
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            Word(0, 16, 16, 'big'),
            memzone_mngr.global_zone.start,
            None,
            2,
        )

        # now see if the right bytes were generated
        self.assertEqual(
            bytecode,
            bytearray([
                0, 0,  # address 0
                8, 0x22, 0x88, 0x99, 0x12, 0x34,  # address 1, 2, 3
                0x04, 0x02, 0x12, 0x34,  # address 4, 5
                0x80, 0x01, 0x00, 0x04,  # address 6, 7
            ]),
            'the bytecode should match',
        )

    def test_generate_bytes_from_line_objects_4bit_words(self):
        # Simulate a 4-bit word ISA: two 4-bit words should be packed into one byte
        class DummyLineWithWords(LineWithWords):
            def __init__(self, address, words):
                self._address = address
                self._words = words
                self._memory_zone = type('mz', (), {'current_address': address})
                self._line_id = f'line_{address}'
                self.is_muted = False

            def get_words(self):
                return self._words

            @property
            def word_count(self):
                return len(self._words)

            @property
            def compilable(self):
                return True
        # Create two lines, each with two 4-bit words
        line1 = DummyLineWithWords(0, [Word(0xA, 4, 4), Word(0xB, 4, 4)])  # 0xA, 0xB
        line2 = DummyLineWithWords(2, [Word(0xC, 4, 4), Word(0xD, 4, 4)])  # 0xC, 0xD
        line_dict = {0: line1, 2: line2}
        max_generated_address = 2
        fill_word = Word(0x0, 4, 4)
        # Should produce: 0xAB, 0xCD
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            fill_word,
            0,
            None,
            2,
        )
        self.assertEqual(bytecode, bytearray([0xAB, 0xCD]), '4-bit words should be packed into bytes correctly')

    def test_address_overlap_is_fatal(self):
        """Doc: Memory Zones - overlapping bytecode at the same absolute address is a fatal error."""
        fp = pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')
        config_path = str(fp)
        asm_source = '\n'.join([
            '.org $00',
            '.byte $01',
            '.org $00',
            '.byte $02',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'overlap.asm')
            with open(asm_path, 'w') as handle:
                handle.write(asm_source)

            assembler = Assembler(
                source_file=asm_path,
                config_file=config_path,
                generate_binary=False,
                output_file=None,
                binary_start=None,
                binary_end=None,
                binary_fill_value=0,
                enable_pretty_print=False,
                pretty_print_format=None,
                pretty_print_output=None,
                is_verbose=0,
                include_paths=[temp_dir],
                predefined=[],
            )
            with self.assertRaises(SystemExit) as ctx:
                assembler.assemble_bytecode()
            self.assertIn('overlaps', str(ctx.exception))

    def test_generate_bytes_from_line_objects_4bit_words_with_fill(self):
        # Simulate a 4-bit word ISA with a gap, so fill_word is used and must be packed
        class DummyLineWithWords(LineWithWords):
            def __init__(self, address, words):
                self._address = address
                self._words = words
                self._memory_zone = type('mz', (), {'current_address': address})
                self._line_id = f'line_{address}'
                self.is_muted = False

            def get_words(self):
                return self._words

            @property
            def word_count(self):
                return len(self._words)

            @property
            def compilable(self):
                return True
        # Address 0: 0xA, Address 2: 0xB (address 1 missing, should be filled)
        line1 = DummyLineWithWords(0, [Word(0xA, 4, 4)])
        line2 = DummyLineWithWords(2, [Word(0xB, 4, 4)])
        line_dict = {0: line1, 2: line2}
        max_generated_address = 2
        fill_word = Word(0xF, 4, 4)  # Use 0xF as fill
        # Should produce: 0xAF (0xA from addr 0, 0xF fill for addr 1), 0xB0 (0xB from addr 2, 0x0 fill for addr 3)
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            fill_word,
            0,
            None,
            2,
        )
        self.assertEqual(bytecode, bytearray([0xAF, 0xB0]), 'fill_word should be packed with real words correctly')

    def test_operand_label_scope_prefix_behavior(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_labels.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        global_scope = GlobalLabelScope(isa_model.registers)
        file_scope = LabelScope(LabelScopeType.FILE, global_scope, 'scope_test.asm')
        local_scope = LabelScope(LabelScopeType.LOCAL, file_scope, 'anchor')

        named_scope_manager = NamedScopeManager(self.diagnostic_reporter)
        named_scope_manager.create_scope('lib', 'lib_', LineIdentifier(1, 'scope_test.asm'))
        active_named_scopes = ActiveNamedScopeList(named_scope_manager)
        active_named_scopes.activate_named_scope('lib')

        local_instr = InstructionLine.factory(
            LineIdentifier(2, 'scope_test.asm'),
            'nword @.local_op:$1001',
            '',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        self.assertIsInstance(local_instr, InstructionLine)
        local_instr.set_start_address(0)
        local_instr.label_scope = local_scope
        local_instr.active_named_scopes = active_named_scopes
        local_instr.register_operand_labels(named_scope_manager)
        self.assertEqual(
            local_scope.get_label_value('.local_op', LineIdentifier(2, 'scope_test.asm')),
            1,
            'local operand label should resolve in local scope',
        )

        file_instr = InstructionLine.factory(
            LineIdentifier(3, 'scope_test.asm'),
            'nword @_file_op:$1002',
            '',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        self.assertIsInstance(file_instr, InstructionLine)
        file_instr.set_start_address(2)
        file_instr.label_scope = local_scope
        file_instr.active_named_scopes = active_named_scopes
        file_instr.register_operand_labels(named_scope_manager)
        self.assertEqual(
            file_scope.get_label_value('_file_op', LineIdentifier(3, 'scope_test.asm')),
            3,
            'file-scope operand label should resolve in file scope',
        )

        global_instr = InstructionLine.factory(
            LineIdentifier(4, 'scope_test.asm'),
            'nword @global_op:$1003',
            '',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        self.assertIsInstance(global_instr, InstructionLine)
        global_instr.set_start_address(4)
        global_instr.label_scope = local_scope
        global_instr.active_named_scopes = active_named_scopes
        global_instr.register_operand_labels(named_scope_manager)
        self.assertEqual(
            global_scope.get_label_value('global_op', LineIdentifier(4, 'scope_test.asm')),
            5,
            'global operand label should resolve in global scope',
        )

        named_instr = InstructionLine.factory(
            LineIdentifier(5, 'scope_test.asm'),
            'nword @lib_op:$1004',
            '',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        self.assertIsInstance(named_instr, InstructionLine)
        named_instr.set_start_address(6)
        named_instr.label_scope = local_scope
        named_instr.active_named_scopes = active_named_scopes
        named_instr.register_operand_labels(named_scope_manager)

        named_scope = named_scope_manager.get_scope_definition('lib')
        self.assertIsNotNone(named_scope)
        self.assertEqual(
            named_scope.get_label_value('lib_op', LineIdentifier(5, 'scope_test.asm')),
            7,
            'named-scope operand label should resolve in named scope when prefix matches',
        )

    def test_operand_label_duplicate_definition_uses_existing_duplicate_error(self):
        fp = pkg_resources.files(config_files).joinpath('test_operand_labels.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        named_scope_manager = NamedScopeManager(self.diagnostic_reporter)
        active_named_scopes = ActiveNamedScopeList(named_scope_manager)
        global_scope = GlobalLabelScope(isa_model.registers)
        file_scope = LabelScope(LabelScopeType.FILE, global_scope, 'dupe.asm')
        local_scope = LabelScope(LabelScopeType.LOCAL, file_scope, 'anchor')

        first = InstructionLine.factory(
            LineIdentifier(1, 'dupe.asm'),
            'nword @dupe:$1234',
            '',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        self.assertIsInstance(first, InstructionLine)
        first.set_start_address(0)
        first.label_scope = local_scope
        first.active_named_scopes = active_named_scopes
        first.register_operand_labels(named_scope_manager)

        second = InstructionLine.factory(
            LineIdentifier(2, 'dupe.asm'),
            'nword @dupe:$5678',
            '',
            isa_model,
            memzone_mngr.global_zone,
            memzone_mngr,
        )
        self.assertIsInstance(second, InstructionLine)
        second.set_start_address(2)
        second.label_scope = local_scope
        second.active_named_scopes = active_named_scopes

        with self.assertRaises(SystemExit) as duplicate_error:
            second.register_operand_labels(named_scope_manager)
        self.assertIn('defined multiple times', str(duplicate_error.exception))
