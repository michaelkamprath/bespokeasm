COMPILER_DIRECTIVES_SET = {
    'org', 'memzone', 'align', 'phase', 'dephase',
}

BYTECODE_DIRECTIVES_SET = {
    'fill', 'zero', 'zerountil',
    'byte', '2byte', '4byte', '8byte', '16byte', 'cstr', 'asciiz',
}

BASE_PREPROCESSOR_DIRECTIVES_SET = {
    'include', 'require', 'error', 'create_memzone', 'print', 'assert',
    'define', 'if', 'elif', 'else', 'endif', 'ifdef', 'ifndef',
    'mute', 'unmute', 'emit',
    'create-scope', 'use-scope', 'deactivate-scope',
    'annotate', 'verbatim', 'endverbatim', 'output-format',
}

FLOW_PREPROCESSOR_DIRECTIVES_SET = {
    'endtrack', 'entry', 'resume', 'set', 'suspend', 'track',
}

# The directives an instruction set may give another name with `general.directive_aliases`:
# data and fill directives only. Porting other directives is `bespokeasm migrate`'s job.
DIRECTIVE_ALIAS_TARGETS = (
    'byte', '2byte', '4byte', '8byte', '16byte', 'cstr', 'asciiz', 'fill', 'zero', 'zerountil',
)

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
    'COORDINATE', 'COUNTER',
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
    '__FLOW_COUNTERS_AVAILABLE__',
    '__OUTPUT_FORMAT__',
}

# The names a label, constant, register or mnemonic can't take. Directives are always written
# with their `.` or `#`, so a directive's name is not reserved: `entry:` and `error:` are labels.
# Expression functions such as LSB() and COUNTER() are not reserved either: they are functions
# only when written as a call, NAME(...).
ASSEMBLER_KEYWORD_SET = frozenset(BUILTIN_CONSTANTS_SET)


def assembler_keywords_for_isa(flow_counters_enabled: bool) -> set[str]:
    """Return names reserved by an ISA with the selected capabilities."""
    return set(ASSEMBLER_KEYWORD_SET)


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
