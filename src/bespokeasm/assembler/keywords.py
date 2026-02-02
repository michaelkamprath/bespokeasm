COMPILER_DIRECTIVES_SET = {
    'org', 'memzone', 'align',
}

BYTECODE_DIRECTIVES_SET = {
    'fill', 'zero', 'zerountil',
    'byte', '2byte', '4byte', '8byte', '16byte', 'cstr', 'asciiz',
}

PREPROCESSOR_DIRECTIVES_SET = {
    'include', 'require', 'create_memzone', 'print',
    'define', 'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
    'mute', 'unmute', 'emit',
    'create-scope', 'use-scope', 'deactivate-scope',
}

EXPRESSION_FUNCTIONS_SET = set([
    'LSB',
] + [
    f'BYTE{i}' for i in range(10)
])

BUILTIN_CONSTANTS_SET = {
    '__LANGUAGE_NAME__',
    '__LANGUAGE_VERSION__',
    '__LANGUAGE_VERSION_MAJOR__',
    '__LANGUAGE_VERSION_MINOR__',
    '__LANGUAGE_VERSION_PATCH__',
}

ASSEMBLER_KEYWORD_SET = (
    COMPILER_DIRECTIVES_SET
    .union(BYTECODE_DIRECTIVES_SET)
    .union(PREPROCESSOR_DIRECTIVES_SET)
    .union(EXPRESSION_FUNCTIONS_SET)
    .union(BUILTIN_CONSTANTS_SET)
)
