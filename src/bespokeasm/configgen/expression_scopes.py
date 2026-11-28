"""Syntax-highlighting rules for the instruction-set-dependent expression operators: `*` as the
current address, `<`/`>` as the low and high operators, and the `#` that marks an immediate value.

Each editor only matches these where the instruction set turns the feature on. Grammars can't
look back past whitespace, so the rules decide from what follows:

* `*` is the current address unless the next non-space character starts a value; then it is
  multiplication. `JPA *`, `*+2`, `0x3000-*-2` and `.2byte *, *` are addresses; `label*2` and
  `x * (y)` multiply. (`x*-2`, multiplying by a negative literal, reads as an address.)
* `#` marks an immediate value where it starts an operand: after whitespace or a comma, before a
  value, as in `lda #$10`.
* `<` and `>` are the low and high operators when a value follows with no space between, as in
  `<label` or `>(x+1)`. That leaves `<<`/`>>` as shifts, `<=`/`>=` as comparisons, and `#if X > 5`
  a comparison, since BespokeASM requires spaces around preprocessor comparisons.
"""

CURRENT_ADDRESS_SCOPE = 'variable.language.current-address'
LOW_HIGH_OPERATOR_SCOPE = 'keyword.operator.low-high'
IMMEDIATE_PREFIX_SCOPE = 'keyword.operator.immediate'

# TextMate (VS Code) and Sublime Text regexes.
_VALUE_START = r"""(?:[\w$%('".~]|<(?![<=])|>(?![>=]))"""
CURRENT_ADDRESS_PATTERN = r'\*(?!\s*' + _VALUE_START + r')'
LOW_HIGH_OPERATOR_PATTERN = r"""(?<![<>])[<>](?![<>=])(?=[*\w$%('".~])"""
IMMEDIATE_PREFIX_PATTERN = r'(?<=[\s,])#(?=\s*[^\s;])'

# Vim regexes, with the same meaning.
_VIM_VALUE_START = r"""\%([0-9A-Za-z_$%('".~]\|<[<=]\@!\|>[>=]\@!\)"""
VIM_CURRENT_ADDRESS_PATTERN = r'\*\%(\s*' + _VIM_VALUE_START + r'\)\@!'
VIM_LOW_HIGH_OPERATOR_PATTERN = r"""[<>]\@<![<>][<>=]\@!\%([*0-9A-Za-z_$%('".~]\)\@="""
VIM_IMMEDIATE_PREFIX_PATTERN = r'[[:space:],]\@<=#\%(\s*[^[:space:];]\)\@='
