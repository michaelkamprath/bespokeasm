COMPILER_DIRECTIVES_SET = {
    'org', 'memzone', 'align',
}

BYTECODE_DIRECTIVES_SET = {
    'fill', 'zero', 'zerountil',
    'byte', '2byte', '4byte', '8byte', '16byte', 'cstr', 'asciiz',
}

BASE_PREPROCESSOR_DIRECTIVES_SET = {
    'include', 'require', 'error', 'create_memzone', 'print',
    'define', 'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
    'mute', 'unmute', 'emit',
    'create-scope', 'use-scope', 'deactivate-scope',
}

FLOW_PREPROCESSOR_DIRECTIVES_SET = {
    'track', 'endtrack',
}

PREPROCESSOR_DIRECTIVES_SET = (
    BASE_PREPROCESSOR_DIRECTIVES_SET
    .union(FLOW_PREPROCESSOR_DIRECTIVES_SET)
)

BASE_EXPRESSION_FUNCTIONS_SET = set([
    'LSB',
] + [
    f'BYTE{i}' for i in range(10)
])

FLOW_EXPRESSION_FUNCTIONS_SET = {
    'COORDINATE', 'COUNTER', 'OFFSET',
}

EXPRESSION_FUNCTIONS_SET = (
    BASE_EXPRESSION_FUNCTIONS_SET
    .union(FLOW_EXPRESSION_FUNCTIONS_SET)
)

BUILTIN_CONSTANTS_SET = {
    '__LANGUAGE_NAME__',
    '__LANGUAGE_VERSION__',
    '__LANGUAGE_VERSION_MAJOR__',
    '__LANGUAGE_VERSION_MINOR__',
    '__LANGUAGE_VERSION_PATCH__',
    '__BESPOKEASM_VERSION__',
}

ASSEMBLER_KEYWORD_SET = (
    COMPILER_DIRECTIVES_SET
    .union(BYTECODE_DIRECTIVES_SET)
    .union(PREPROCESSOR_DIRECTIVES_SET)
    .union(EXPRESSION_FUNCTIONS_SET)
    .union(BUILTIN_CONSTANTS_SET)
)


def assembler_keywords_for_isa(flow_counters_enabled: bool) -> set[str]:
    """Return names reserved by an ISA with the selected capabilities."""
    keywords = (
        COMPILER_DIRECTIVES_SET
        .union(BYTECODE_DIRECTIVES_SET)
        .union(BASE_PREPROCESSOR_DIRECTIVES_SET)
        .union(BASE_EXPRESSION_FUNCTIONS_SET)
        .union(BUILTIN_CONSTANTS_SET)
    )
    if flow_counters_enabled:
        keywords.update(FLOW_PREPROCESSOR_DIRECTIVES_SET)
        keywords.update(FLOW_EXPRESSION_FUNCTIONS_SET)
    return keywords


def preprocessor_directives_for_isa(flow_counters_enabled: bool) -> set[str]:
    """Return preprocessor tokens visible for the selected ISA capabilities."""
    directives = set(BASE_PREPROCESSOR_DIRECTIVES_SET)
    if flow_counters_enabled:
        directives.update(FLOW_PREPROCESSOR_DIRECTIVES_SET)
    return directives


def expression_functions_for_isa(flow_counters_enabled: bool) -> set[str]:
    """Return expression-function tokens visible for the selected ISA capabilities."""
    functions = set(BASE_EXPRESSION_FUNCTIONS_SET)
    if flow_counters_enabled:
        functions.update(FLOW_EXPRESSION_FUNCTIONS_SET)
    return functions
