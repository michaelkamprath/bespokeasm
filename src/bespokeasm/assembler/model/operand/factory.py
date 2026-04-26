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
        diagnostic_reporter,
        default_numeric_base: str = 'decimal',
    ) -> Operand:
        type_str = arg_config_dict['type']
        operand: Operand
        if type_str == 'numeric':
            operand = numeric_expression.NumericExpressionOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'register':
            operand = register.RegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'indexed_register':
            operand = indexed_register.IndexedRegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'indirect_register':
            operand = indirect_register.IndirectRegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'indirect_indexed_register':
            operand = indirect_indexed_register.IndirectIndexedRegisterOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'indirect_numeric':
            operand = indirect_numeric.IndirectNumericOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'deferred_numeric':
            operand = deferred_numeric.DeferredNumericOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'enumeration':
            operand = enumeration_operand.EnumerationOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'numeric_enumeration':
            operand = numeric_enumeration.NumericEnumerationOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'numeric_bytecode':
            operand = numeric_bytecode.NumericBytecode(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'address':
            operand = address.AddressOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'relative_address':
            operand = relative_address.RelativeAddressOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        elif type_str == 'empty':
            operand = empty.EmptyOperand(
                operand_id,
                arg_config_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
        else:
            sys.exit(f'ERROR - Operand {operand_id} was configured with unknown type "{type_str}"')
        operand.default_numeric_base = default_numeric_base
        return operand
