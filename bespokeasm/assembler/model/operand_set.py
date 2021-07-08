from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.byte_code.parts import ByteCodePart

class OperandSet:
    def __init__(self, name: str, config_dict: dict, default_endian: str):
        self._name = name
        self._config = config_dict
        self._arg_types = {}
        for arg_type_id, arg_type_conf in self._config['operand_configs'].items():
            arg_type = Operand.factory(arg_type_conf, default_endian)
            self._arg_types[arg_type_id]=arg_type
        self._ordered_operand_list = list(self._arg_types.values())

        # Operands are sorted according to matching precedence order, which is set
        # by the enum value of the types. This allows matching to consider an operand
        # as a special register operand (for example) before just saying it's an expression
        self._ordered_operand_list.sort(key=lambda op: op.type.value, reverse=False)

    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        arg_type_ids = ','.join([id for id in self._arg_types.keys()])
        return f'OperandSet<{self._name},[{arg_type_ids}]>'

    def default_bytecode_size(self) -> int:
        return self._config.get('bytecode_size', None)

    def parse_operand(self,line_num: int, operand_str: str) -> tuple[ByteCodePart, ByteCodePart]:
        for operand in self._ordered_operand_list:
            bytecode_part, argument_part = operand.parse_operand(line_num, operand_str)
            if bytecode_part is not None or argument_part is not None:
                # if some part was returned, then this is a valid match. Matching
                # precedence order is important here!
                return bytecode_part, argument_part
        return None, None

class OperandSetCollection(dict):
    def __init__(self, config_dict: dict, default_endian: str):
        super().__init__(self)
        for set_name, set_config in config_dict.items():
            self[set_name] = OperandSet(set_name, set_config, default_endian)
    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        set_names = ','.join([str(v) for v in self.values()])
        return f'OperandSetCollection[{set_names}]'


    def get_operand_set(self, key) -> OperandSet:
        return self.get(key, None)

