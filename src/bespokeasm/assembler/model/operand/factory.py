import sys

from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand.types import address
from bespokeasm.assembler.model.operand.types import deferred_numeric
from bespokeasm.assembler.model.operand.types import empty
from bespokeasm.assembler.model.operand.types import enumeration_operand
from bespokeasm.assembler.model.operand.types import indexed_register
from bespokeasm.assembler.model.operand.types import indirect_indexed_register
from bespokeasm.assembler.model.operand.types import indirect_numeric
from bespokeasm.assembler.model.operand.types import indirect_register
from bespokeasm.assembler.model.operand.types import numeric_bytecode
from bespokeasm.assembler.model.operand.types import numeric_enumeration
from bespokeasm.assembler.model.operand.types import numeric_expression
from bespokeasm.assembler.model.operand.types import register
from bespokeasm.assembler.model.operand.types import relative_address


class OperandFactory:

    @classmethod
    def factory(
        cls,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        registers: set[str],
        word_size: int,
        word_segment_size: int,
    ) -> Operand:
        type_str = arg_config_dict['type']
        if type_str == 'numeric':
            return numeric_expression.NumericExpressionOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        elif type_str == 'register':
            return register.RegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size
            )
        elif type_str == 'indexed_register':
            return indexed_register.IndexedRegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
            )
        elif type_str == 'indirect_register':
            return indirect_register.IndirectRegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
            )
        elif type_str == 'indirect_indexed_register':
            return indirect_indexed_register.IndirectIndexedRegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
            )
        elif type_str == 'indirect_numeric':
            return indirect_numeric.IndirectNumericOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        elif type_str == 'deferred_numeric':
            return deferred_numeric.DeferredNumericOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        elif type_str == 'enumeration':
            return enumeration_operand.EnumerationOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
            )
        elif type_str == 'numeric_enumeration':
            return numeric_enumeration.NumericEnumerationOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
            )
        elif type_str == 'numeric_bytecode':
            return numeric_bytecode.NumericBytecode(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        elif type_str == 'address':
            return address.AddressOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        elif type_str == 'relative_address':
            return relative_address.RelativeAddressOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        elif type_str == 'empty':
            return empty.EmptyOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
            )
        else:
            sys.exit(f'ERROR - Operand {operand_id} was configured with unknown type "{type_str}"')
