import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class RegisterOperand(Operand):
    _DECORATOR_REGEX_PATTERNS = {
        'plus': r'\+',
        'plus_plus': r'\+\+',
        'minus': r'\-',
        'minus_minus': r'\-\-',
    }

    _OPERAND_PATTERN_TEMPLATE = r'{0}{1}'

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, regsiters: set[str]):
        super().__init__(operand_id, arg_config_dict, default_endian)
        if self.register not in regsiters:
            sys.exit(f'ERROR - ISA configation declares register based operand {self} but the '
                     f'register label "{self.register}" is not a declared register.')

    def __str__(self):
        return f'RegisterOperand<{self.id},register={self.register}>'

    @property
    def type(self) -> OperandType:
        return OperandType.REGISTER

    @property
    def register(self) -> str:
        return self._config['register']

    @property
    def operand_register_string(self) -> str:
        return self.register

    @property
    def has_decorator(self) -> bool:
        return 'decorator' in self._config

    @property
    def decorator_pattern(self) -> str:
        if self.has_decorator:
            if 'type' not in self._config['decorator']:
                sys.exit(
                    f'ERROR - ISA configation declares register based operand {self} with a decorator '
                    f'but the decorator type is not configured.'
                )
            decorator_type = self._config['decorator']['type']
            if decorator_type not in RegisterOperand._DECORATOR_REGEX_PATTERNS:
                sys.exit(
                    f'ERROR - ISA configation declares register based operand {self} with unknow decorator '
                    f'type = {decorator_type}'
                )
            return RegisterOperand._DECORATOR_REGEX_PATTERNS[decorator_type]
        return ''

    @property
    def decorator_is_prefix(self) -> bool:
        if self.has_decorator:
            return self._config['decorator'].get('is_prefix', False)
        return False

    @property
    def match_pattern(self) -> str:
        if not self.has_decorator:
            return r'\b{0}\b'.format(self.register)
        elif self.decorator_is_prefix:
            return r'(?<!(?:\+|\-|\d|\w)){0}{1}\b'.format(self.decorator_pattern, self.register)
        else:
            return r'\b{0}{1}(?!(?:\+|\-|\d|\w))'.format(self.register, self.decorator_pattern)

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        match = re.match(
            r'^{0}$'.format(self.match_pattern),
            operand.strip()
        )
        if match is not None:
            bytecode_part = NumericByteCodePart(
                self.bytecode_value,
                self.bytecode_size,
                False,
                'big',
                line_id
            ) if self.bytecode_value is not None else None
            arg_part = None
            return ParsedOperand(self, bytecode_part, arg_part, operand)
        return None
