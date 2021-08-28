from bespokeasm.assembler.line_object import LineObject
import json
import sys
import yaml

from bespokeasm.assembler.byte_code.assembled import AssembledInstruction
from bespokeasm.assembler.model.instruction_set import InstructionSet
from bespokeasm.assembler.model.operand_set import OperandSet, OperandSetCollection
from bespokeasm.assembler.line_object.directive_line import DirectiveLine
class AssemblerModel:
    def __init__(self, config_file_path: str):
        if config_file_path.endswith('.json'):
            with open(config_file_path, 'r') as json_file:
                config_dict = json.load(json_file)
        elif config_file_path.endswith('.yaml'):
            with open(config_file_path, 'r') as yaml_file:
                try:
                    config_dict = yaml.safe_load(yaml_file)
                except yaml.YAMLError as exc:
                    sys.exit(f'ERROR: {exc}')
        else:
            sys.exit('ERROR: unknown ISA config file type')

        self._config = config_dict
        registers = self._config['general'].get('registers', [])
        self._registers = set(registers if registers is not None else [])
        if len(self._registers.intersection(DirectiveLine.DIRECTIVE_SET)) > 0:
            sys.exit(f'ERROR: the instruction set configuration file specified unallowed register names: {self._registers.intersection(DirectiveLine.DIRECTIVE_SET)}')
        self._operand_sets = OperandSetCollection(self._config['operand_sets'], self.endian)
        self._instructions = InstructionSet(self._config['instructions'], self._operand_sets)

    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        if 'description' in self._config:
            desc_str = self._config['description']
            return f'AssemblerModel("{desc_str}")'
        else:
            return 'AssemblerModel(*Undefined*)'

    @property
    def endian(self) -> str:
        if 'endian' in self._config['general']:
            return self._config['general']['endian']
        else:
            return 'big'
    @property
    def address_size(self) -> int:
        return self._config['general']['address_size']
    @property
    def registers(self) -> set[str]:
        return self._registers

    @property
    def instruction_mnemonics(self) -> list[str]:
        return list(self._instructions.keys())
    def get_operand_set(self, operand_set_name: str) -> OperandSet:
        return self._operand_sets.get_operand_set(operand_set_name)

    def parse_instruction(self, line_num: int, instruction: str) -> AssembledInstruction:
        instr_parts = instruction.strip().split(' ', 1)
        mnemonic = instr_parts[0].lower()
        if len(instr_parts) > 1:
            operands = instr_parts[1]
        else:
            operands = ''

        instr_obj = self._instructions.get(mnemonic)
        if instr_obj is None:
            sys.exit(f'ERROR: line {line_num} - Unrecognized mnemonic "{mnemonic}"')
        return instr_obj.generate_bytecode_parts(line_num, mnemonic, operands, self.endian)
