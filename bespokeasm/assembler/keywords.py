COMPILER_DIRECTIVES_SET = set([
    'org'
])

BYTECODE_DIRECTIVES_SET = set([
    'fill', 'zero', 'zerountil',
    'byte', '2byte', '4byte', '8byte', 'cstr',
])

PREPROCESSOR_DIRECTIVES_SET = set([
    'include', 'require',
])

EXPRESSION_FUNCTIONS_SET = set([
    'LSB', 'MSB',
])

ASSEMBLER_KEYWORD_SET = (
    COMPILER_DIRECTIVES_SET
    .union(BYTECODE_DIRECTIVES_SET)
    .union(PREPROCESSOR_DIRECTIVES_SET)
    .union(EXPRESSION_FUNCTIONS_SET)
)
