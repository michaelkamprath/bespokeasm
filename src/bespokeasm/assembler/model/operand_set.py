import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand import ParsedOperand
from bespokeasm.assembler.model.operand.factory import OperandFactory


class OperandSet:
    _ordered_operand_list: list[Operand]

    def __init__(
        self,
        name: str,
        config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        regsiters: set[str],
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
    ) -> None:
        self._name = name
        self._config = config_dict
        self._ordered_operand_list = []
        for arg_type_id, arg_type_conf in self._config['operand_values'].items():
            operand = OperandFactory.factory(
                arg_type_id,
                arg_type_conf,
                default_multi_word_endian,
                default_intra_word_endian,
                regsiters,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
            if operand.null_operand:
                # null operands not supported in operand sets. must use specific operand configuration.
                sys.exit(
                    f'ERROR: The configuration for operand set "{name}" contains unallowed null '
                    f'operand type named "{arg_type_id}".'
                )
            self._ordered_operand_list.append(operand)

        # Operands are sorted according to matching precedence order, which is set
        # by the enum value of the types. This allows matching to consider an operand
        # as a special register operand (for example) before just saying it's an expression
        self._ordered_operand_list.sort(key=lambda op: op.type.value, reverse=False)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        arg_type_ids = ','.join([str(id) for id in self._ordered_operand_list])
        return f'OperandSet<{self._name},[{arg_type_ids}]>'

    @property
    def default_bytecode_size(self) -> int:
        return self._config.get('bytecode_size', None)

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand_str: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand | None:
        for operand in self._ordered_operand_list:
            op: ParsedOperand = operand.parse_operand(line_id, operand_str, register_labels, memzone_manager)
            if op is not None:
                # if some part was returned, then this is a valid match. Matching
                # precedence order is important here!
                return op
        return None

    def match_operand(
        self,
        line_id: LineIdentifier,
        operand_str: str,
        register_labels: set[str]
    ) -> Operand | None:
        for operand in self._ordered_operand_list:
            if operand.match_operand(line_id, operand_str, register_labels):
                return operand
        return None


class OperandSetCollection(dict):
    def __init__(
        self,
        config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        registers: set[str],
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
    ) -> None:
        super().__init__(self)
        for set_name, set_config in config_dict.items():
            self[set_name] = OperandSet(
                set_name,
                set_config,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        set_names = ','.join([str(v) for v in self.values()])
        return f'OperandSetCollection[{set_names}]'

    def get_operand_set(self, key) -> OperandSet | None:
        return self.get(key, None)
