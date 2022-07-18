import sys

from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand.types import empty, numeric_expression, indirect_register, \
                                                     indirect_numeric, register, indirect_indexed_register, \
                                                     deferred_numeric, numeric_bytecode, enumeration_operand, \
                                                     numeric_enumeration, relative_address


class OperandFactory:

    @classmethod
    def factory(cls, operand_id: str, arg_config_dict: dict, default_endian: str, registers: set[str]) -> Operand:
        type_str = arg_config_dict['type']
        if type_str == 'numeric':
            return numeric_expression.NumericExpressionOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'register':
            return register.RegisterOperand(operand_id, arg_config_dict, default_endian, registers)
        elif type_str == 'indirect_register':
            return indirect_register.IndirectRegisterOperand(operand_id, arg_config_dict, default_endian, registers)
        elif type_str == 'indirect_indexed_register':
            return indirect_indexed_register.IndirectIndexedRegisterOperand(
                operand_id,
                arg_config_dict,
                default_endian,
                registers
            )
        elif type_str == 'indirect_numeric':
            return indirect_numeric.IndirectNumericOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'deferred_numeric':
            return deferred_numeric.DeferredNumericOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'enumeration':
            return enumeration_operand.EnumerationOperand(operand_id, arg_config_dict, default_endian, registers)
        elif type_str == 'numeric_enumeration':
            return numeric_enumeration.NumericEnumerationOperand(operand_id, arg_config_dict, default_endian, registers)
        elif type_str == 'numeric_bytecode':
            return numeric_bytecode.NumericBytecode(operand_id, arg_config_dict, default_endian)
        elif type_str == 'relative_address':
            return relative_address.RelativeAddressOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'empty':
            return empty.EmptyOperand(operand_id, arg_config_dict, default_endian)
        else:
            sys.exit(f'ERROR - Operand {operand_id} was configured with unknown type "{type_str}"')
