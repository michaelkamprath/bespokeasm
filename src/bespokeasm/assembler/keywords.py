COMPILER_DIRECTIVES_SET = set([
    'org', 'memzone',
])

BYTECODE_DIRECTIVES_SET = set([
    'fill', 'zero', 'zerountil',
    'byte', '2byte', '4byte', '8byte', 'cstr', 'asciiz',
])

PREPROCESSOR_DIRECTIVES_SET = set([
    'include', 'require', 'create_memzone',
    'define', 'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
])

EXPRESSION_FUNCTIONS_SET = set([
    'LSB',
] + [
    f'BYTE{i}' for i in range(10)
])

ASSEMBLER_KEYWORD_SET = (
    COMPILER_DIRECTIVES_SET
    .union(BYTECODE_DIRECTIVES_SET)
    .union(PREPROCESSOR_DIRECTIVES_SET)
    .union(EXPRESSION_FUNCTIONS_SET)
)
