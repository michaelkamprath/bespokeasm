COMPILER_DIRECTIVES_SET = set([
    'org'
])

BYTECODE_DIRECTIVES_SET = set([
    'fill', 'zero', 'zerountil',
    'byte', '2byte', '4byte', 'cstr',
])

PREPROCESSOR_DIRECTIVES_SET = set([
    'include'
])

ASSEMBLER_KEYWORD_SET = (
    COMPILER_DIRECTIVES_SET
    .union(BYTECODE_DIRECTIVES_SET)
    .union(PREPROCESSOR_DIRECTIVES_SET)
)
