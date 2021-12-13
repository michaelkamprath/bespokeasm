




from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand.types import empty, numeric_expression, indirect_register, indirect_numeric, register

class OperandFactory:

    @classmethod
    def factory(cls, operand_id: str, arg_config_dict: dict, default_endian: str) -> Operand:
        type_str = arg_config_dict['type']
        if type_str == 'numeric':
            return numeric_expression.NumericExpressionOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'register':
            return register.RegisterOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'indirect_register':
            return indirect_register.IndirectRegisterOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'indirect_numeric':
            return indirect_numeric.IndirectNumericOperand(operand_id, arg_config_dict, default_endian)
        elif type_str == 'empty':
            return empty.EmptyOperand(operand_id, arg_config_dict, default_endian)
        else:
            return None
