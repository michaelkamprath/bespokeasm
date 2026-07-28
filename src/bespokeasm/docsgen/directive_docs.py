"""
Hover documentation strings for BespokeASM directives.

Each entry maps a directive name (without prefix) to a short markdown
description suitable for display in an editor hover popup.
"""
# Compiler directives (prefixed with '.' in source code)
COMPILER_DIRECTIVE_DOCS: dict[str, str] = {
    'org': (
        '### `.org` : Set Origin Address\n\n'
        '---\n\n'
        'Sets the address for the next emitted bytecode.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.org <address>\n'
        '.org <offset> "memory_zone"\n'
        '```\n\n'
        'Without a memory zone name, the value is an absolute address. '
        'With a quoted memory zone name, the value is an offset from the '
        'start of that zone.'
    ),
    'memzone': (
        '### `.memzone` : Set Memory Zone\n\n'
        '---\n\n'
        'Sets the current memory zone scope for subsequent code.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.memzone <zone_name>\n'
        '```\n\n'
        'Code after this directive is assembled into the named memory zone '
        'until end-of-file or another `.memzone` directive. '
        'Included files revert to the `GLOBAL` zone.'
    ),
    'align': (
        '### `.align` : Align to Page Boundary\n\n'
        '---\n\n'
        'Advances the current address to the next page boundary.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.align\n'
        '.align <page_size>\n'
        '```\n\n'
        'If `<page_size>` is omitted, the ISA-configured page size is used. '
        'The next emitted bytecode will start at an address that is a '
        'multiple of the page size.'
    ),
}

# Bytecode / data type directives (prefixed with '.' in source code)
BYTECODE_DIRECTIVE_DOCS: dict[str, str] = {
    'byte': (
        '### `.byte` : Define Byte Data\n\n'
        '---\n\n'
        'Emits one or more 1-byte values into the bytecode.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.byte <value>, <value>, ...\n'
        '.byte "string"\n'
        '```\n\n'
        'Values can be numeric expressions, labels, or quoted strings. '
        'Strings and numeric expressions may be mixed in the same '
        'comma-separated list.'
    ),
    '2byte': (
        '### `.2byte` : Define 2-Byte Data\n\n'
        '---\n\n'
        'Emits one or more 2-byte values into the bytecode.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.2byte <value>, <value>, ...\n'
        '```\n\n'
        'Each value is a numeric expression. Multi-word endianness '
        'follows the ISA configuration.'
    ),
    '4byte': (
        '### `.4byte` : Define 4-Byte Data\n\n'
        '---\n\n'
        'Emits one or more 4-byte values into the bytecode.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.4byte <value>, <value>, ...\n'
        '```\n\n'
        'Each value is a numeric expression. Multi-word endianness '
        'follows the ISA configuration.'
    ),
    '8byte': (
        '### `.8byte` : Define 8-Byte Data\n\n'
        '---\n\n'
        'Emits one or more 8-byte values into the bytecode.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.8byte <value>, <value>, ...\n'
        '```\n\n'
        'Each value is a numeric expression. Multi-word endianness '
        'follows the ISA configuration.'
    ),
    '16byte': (
        '### `.16byte` : Define 16-Byte Data\n\n'
        '---\n\n'
        'Emits one or more 16-byte values into the bytecode.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.16byte <value>, <value>, ...\n'
        '```\n\n'
        'Each value is a numeric expression. Multi-word endianness '
        'follows the ISA configuration.'
    ),
    'fill': (
        '### `.fill` : Fill with Value\n\n'
        '---\n\n'
        'Fills a region with a repeated byte value.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.fill <count>, <value>\n'
        '```\n\n'
        'Emits `<count>` words, each set to `<value>`.'
    ),
    'zero': (
        '### `.zero` : Fill with Zeros\n\n'
        '---\n\n'
        'Fills a region with zero-valued words.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.zero <count>\n'
        '```\n\n'
        'Shorthand for `.fill <count>, 0`.'
    ),
    'zerountil': (
        '### `.zerountil` : Zero-Fill to Address\n\n'
        '---\n\n'
        'Fills with zeros up to and including a target address.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.zerountil <address>\n'
        '```\n\n'
        'Emits zero-valued words from the current address through '
        '`<address>`. Emits nothing if the target address has already '
        'been passed.'
    ),
    'cstr': (
        '### `.cstr` : C-Style String\n\n'
        '---\n\n'
        'Emits a string followed by a terminator byte.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.cstr "string"\n'
        '```\n\n'
        'The terminator byte defaults to `0` but can be configured in '
        'the ISA configuration. Supports escape sequences.'
    ),
    'asciiz': (
        '### `.asciiz` : Null-Terminated String\n\n'
        '---\n\n'
        'Emits a string followed by a terminator byte.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.asciiz "string"\n'
        '```\n\n'
        'Alias for `.cstr`. The terminator byte defaults to `0` but '
        'can be configured in the ISA configuration.'
    ),
}

# Preprocessor directives (prefixed with '#' in source code)
PREPROCESSOR_DIRECTIVE_DOCS: dict[str, str] = {
    'include': (
        '### `#include` : Include Source File\n\n'
        '---\n\n'
        'Includes another assembly source file at this location.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#include "filename.asm"\n'
        '```\n\n'
        'The file is searched relative to the current file first, then '
        'in configured include directories. Each file may only be '
        'included once. Respects conditional compilation.'
    ),
    'require': (
        '### `#require` : Version Requirement\n\n'
        '---\n\n'
        'Asserts a version requirement; halts assembly on failure.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#require "language-id >= 1.0.0"\n'
        '#require __LANGUAGE_VERSION__ >= 2.0.0\n'
        '#require __BESPOKEASM_VERSION__ >= 0.7.2\n'
        '```\n\n'
        'Supports both the legacy quoted-string format and symbol-based '
        'comparisons restricted to built-in language/BespokeASM version '
        'symbols and literals. Complete versions use semantic-version '
        'ordering. Use `#assert` for invariants involving user macros.'
    ),
    'define': (
        '### `#define` : Define Preprocessor Macro\n\n'
        '---\n\n'
        'Defines a text-substitution macro symbol.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#define SYMBOL value\n'
        '#define FLAG\n'
        '```\n\n'
        'Occurrences of `SYMBOL` in subsequent code are replaced with '
        '`value`. An empty value defines the symbol for use with '
        '`#ifdef`. Substitution is recursive.'
    ),
    'if': (
        '### `#if` : Conditional Compilation\n\n'
        '---\n\n'
        'Begins a conditional compilation block.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#if <expr> <comparison> <expr>\n'
        '#if <expr>\n'
        '```\n\n'
        'The single-expression form implies `!= 0`. Expressions may use '
        'preprocessor macros and built-in version symbols. '
        'Static-analysis values are not allowed because this directive '
        'selects which source is compiled. '
        'Must be closed with `#endif`.'
    ),
    'elif': (
        '### `#elif` : Else-If Condition\n\n'
        '---\n\n'
        'Adds an alternative condition to a `#if` block.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#elif <expr> <comparison> <expr>\n'
        '#elif <expr>\n'
        '```\n\n'
        'Must follow a `#if` or another `#elif`. Static-analysis values are '
        'not allowed because this directive selects which source is compiled.'
    ),
    'else': (
        '### `#else` : Else Block\n\n'
        '---\n\n'
        'Fallback block when all preceding conditions are false.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#else\n'
        '```\n\n'
        'Must appear within a `#if` / `#endif` block.'
    ),
    'endif': (
        '### `#endif` : End Conditional Block\n\n'
        '---\n\n'
        'Terminates a `#if` / `#ifdef` / `#ifndef` conditional block.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#endif\n'
        '```'
    ),
    'ifdef': (
        '### `#ifdef` : If Defined\n\n'
        '---\n\n'
        'Begins a conditional block that compiles if a macro symbol is defined.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#ifdef SYMBOL\n'
        '```\n\n'
        'Must be closed with `#endif`.'
    ),
    'ifndef': (
        '### `#ifndef` : If Not Defined\n\n'
        '---\n\n'
        'Begins a conditional block that compiles if a macro symbol is *not* defined.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#ifndef SYMBOL\n'
        '```\n\n'
        'Must be closed with `#endif`.'
    ),
    'create_memzone': (
        '### `#create_memzone` : Create Memory Zone\n\n'
        '---\n\n'
        'Defines a new memory zone with an address range.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#create_memzone NAME $start $end\n'
        '```\n\n'
        'The zone must be fully contained within the `GLOBAL` memory zone. '
        'Zone names must be unique.'
    ),
    'mute': (
        '### `#mute` : Suppress Bytecode Emission\n\n'
        '---\n\n'
        'Suppresses bytecode output from subsequent lines.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#mute\n'
        '```\n\n'
        'Useful for defining symbols without emitting code. '
        'Mute and unmute calls stack; each `#mute` needs a matching '
        '`#unmute` or `#emit`. Does not affect `#include`d files.'
    ),
    'unmute': (
        '### `#unmute` : Restore Bytecode Emission\n\n'
        '---\n\n'
        'Restores bytecode output suppressed by `#mute`.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#unmute\n'
        '```\n\n'
        'Mute and unmute calls stack; each `#mute` needs a matching '
        '`#unmute` or `#emit`.'
    ),
    'emit': (
        '### `#emit` : Restore Bytecode Emission\n\n'
        '---\n\n'
        'Restores bytecode output suppressed by `#mute`.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#emit\n'
        '```\n\n'
        'Alias for `#unmute`.'
    ),
    'print': (
        '### `#print` : Print Message\n\n'
        '---\n\n'
        'Prints a message to standard output during assembly.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#print "message"\n'
        '#print <verbosity> "message"\n'
        '#print <color> "message"\n'
        '#print <verbosity> <color> "message"\n'
        '```\n\n'
        'Optional `<verbosity>` sets the minimum `-v` level. '
        'Optional `<color>` colorizes the output '
        '(`red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`). '
        'Respects conditional compilation and mute state.'
    ),
    'error': (
        '### `#error` : Emit Error\n\n'
        '---\n\n'
        'Emits an error and immediately stops assembly.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#error\n'
        '#error "message"\n'
        '```\n\n'
        'If no message is provided, a default message is used. '
        'Respects conditional compilation and mute state.'
    ),
    'create-scope': (
        '### `#create-scope` : Create Named Label Scope\n\n'
        '---\n\n'
        'Creates a custom symbol namespace with an optional prefix.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#create-scope "scope_name"\n'
        '#create-scope "scope_name" prefix="pfx_"\n'
        '```\n\n'
        'The scope is also activated upon creation. Labels can only be '
        'added to a scope in the file where it was created. '
        'The prefix defaults to `_` if omitted.'
    ),
    'use-scope': (
        '### `#use-scope` : Activate Named Scope\n\n'
        '---\n\n'
        'Activates a named label scope for symbol resolution.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#use-scope "scope_name"\n'
        '```\n\n'
        'Labels in the scope become resolvable on subsequent lines. '
        'Activation is file-local and does not project into '
        '`#include`d files. May be used before `#create-scope`.'
    ),
    'deactivate-scope': (
        '### `#deactivate-scope` : Deactivate Named Scope\n\n'
        '---\n\n'
        'Deactivates a previously activated named label scope.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#deactivate-scope "scope_name"\n'
        '```\n\n'
        'Labels from the scope are no longer resolved on subsequent lines.'
    ),
    'track': (
        '### `#track` : Begin Flow-Counter Tracking\n\n'
        '---\n\n'
        'Begins a control-flow-aware static-analysis region for a configured '
        'flow-counter class.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#track <counter-class>\n'
        '#track <counter-class> as=<counter-name> mode=<entry-mode> '
        'init=<expression> exit=<expression>\n'
        '```\n\n'
        '`as=` gives the instance a distinct name so multiple counters may '
        'overlap; otherwise the class name is used. '
        '`mode=` selects an entry convention configured by the counter class. '
        'Explicit `init=` and `exit=` values override the selected mode. '
        'The directive does not emit bytecode or consume an address.'
    ),
    'endtrack': (
        '### `#endtrack` : End Flow-Counter Tracking\n\n'
        '---\n\n'
        'Closes the active flow-counter region lexically and applies its exit '
        'check when the execution path is still live.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#endtrack <counter-name>\n'
        '#endtrack <counter-name> exit=<expression>\n'
        '```\n\n'
        'With `exit_policy: balanced`, omitting `exit=` requires the final '
        'value to equal the initial value. With `exit_policy: none`, an '
        'omitted exit check simply closes the region. After a terminal has '
        'already reconciled the path, `#endtrack` is a lexical-only delimiter.'
    ),
    'entry': (
        '### `#entry` : Declare an Alternate Flow Entry\n\n'
        '---\n\n'
        'Attaches an intentional control-flow entry to the next address '
        'label inside an active tracking region.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#entry <counter-name>\n'
        '#entry <counter-name> value=<expression>\n'
        '```\n\n'
        'An unreachable label requires `value=`. A reachable label may omit '
        'it and reuse its unique incoming value. Consecutive `#entry` '
        'directives for different active counters attach to the same label. '
        'The directive emits no bytecode.'
    ),
    'assert': (
        '### `#assert` : Require a Compile-Time Condition\n\n'
        '---\n\n'
        'Stops assembly when a compile-time condition is false.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#assert <expression>\n'
        '#assert <expression> <comparison> <expression-or-string>\n'
        '#assert <condition> "message"\n'
        '#assert <condition> <color> "message"\n'
        '```\n\n'
        'The condition has the same semantics as `#if`: the one-expression '
        'form implies `!= 0`, comparisons may be `==`, `!=`, `<`, `<=`, '
        '`>`, or `>=`, and preprocessor macros and built-in version symbols '
        'are resolved. Unlike `#if`, an assertion only validates; it never '
        'selects which source is compiled. The optional colors are the same '
        'as for `#print`.\n\n'
        'Unlike `#require`, which declares language or tool version '
        'compatibility, `#assert` states an arbitrary compile-time invariant.'
    ),
    'set': (
        '### `#set` : Re-anchor a Flow Counter\n\n'
        '---\n\n'
        'Assigns a programmer-supplied value to an active scalar counter.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#set <counter-name> = <expression>\n'
        '```\n\n'
        'Only the named instance changes; other active counters continue '
        'independently.'
    ),
    'suspend': (
        '### `#suspend` : Suspend Flow-Counter Tracking\n\n'
        '---\n\n'
        'Marks one scalar counter indeterminate across a span, including '
        'run-time-length loops.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#suspend <counter-name>\n'
        '```\n\n'
        'Instruction effects are ignored for that instance until it is '
        'resumed. Its value and coordinates cannot be used while suspended.'
    ),
    'resume': (
        '### `#resume` : Resume Flow-Counter Tracking\n\n'
        '---\n\n'
        'Restores a known value to a suspended scalar counter.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '#resume <counter-name> = <expression>\n'
        '```\n\n'
        'A coordinate from the same instance may be named directly to restore '
        'its saved scalar anchor. Resumption is a programmer assertion, and '
        'coordinates created before the suspended span are permanently '
        'invalidated.'
    ),
}

FLOW_ASSERT_DOC_SUFFIX = (
    '\n\nIn a flow-enabled ISA, `COUNTER(name)` and `OFFSET(coordinate)` may '
    'be used in either operand. An otherwise undefined bare left operand is '
    'retained as shorthand for an active scalar counter, such as '
    '`#assert stack == 0`. Prefer `COUNTER(stack)` when an explicit flow '
    'reference is clearer. This does not extend `#if` or `#elif`; static '
    'analysis never controls conditional compilation.'
)

# Expression functions used in numeric expressions
EXPRESSION_FUNCTION_DOCS: dict[str, str] = {
    'LSB': (
        '### `LSB()` : Least Significant Byte\n\n'
        '---\n\n'
        'Returns the least significant byte of an expression.\n\n'
        '**Usage:**\n\n'
        '```\n'
        'LSB(expression)\n'
        '```\n\n'
        'Equivalent to `BYTE0(expression)`. Extracts bits 7\u20130 '
        'of the evaluated value.'
    ),
    'COUNTER': (
        '### `COUNTER()` : Current Flow-Counter Value\n\n'
        '---\n\n'
        'Returns the current scalar value of an active flow counter during '
        'static analysis.\n\n'
        '**Usage:**\n\n'
        '```\n'
        'COUNTER(counter-name)\n'
        '```\n\n'
        'This function is valid in fixed-width instruction operands, '
        'fixed-size data values, and flow directives such as `#assert`, '
        '`#set`, and `#resume`. It is rejected in layout, conditional '
        'preprocessor, and instruction-selection expressions.'
    ),
    'COORDINATE': (
        '### `COORDINATE()` : Declare a Counter Coordinate\n\n'
        '---\n\n'
        'Identifies a position at a signed offset from the current position '
        'of an active scalar flow counter.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.parameter := COORDINATE(stack, 3)\n'
        '```\n\n'
        'The second argument is an ordinary compile-time expression. The '
        "counter class's `coordinate_offsets` policy controls whether "
        'positive, negative, or both nonzero offset directions are valid; '
        '`allow_zero_offset` controls zero independently. '
        '`COORDINATE()` is valid only on the right side of a `:=` declaration.'
    ),
    'OFFSET': (
        '### `OFFSET()` : Counter-Coordinate Offset\n\n'
        '---\n\n'
        'Returns the active scalar counter value minus a coordinate saved '
        'with `:=`.\n\n'
        '**Usage:**\n\n'
        '```\n'
        'OFFSET(.coordinate)\n'
        '```\n\n'
        'The argument must be a counter-coordinate symbol, not an ordinary '
        'constant or address label. Referencing a coordinate invalidated by '
        'crossing its saved position is an error.'
    ),
}

COUNTER_COORDINATE_DOCS: dict[str, str] = {
    ':=': (
        '### `:=` : Declare Counter Coordinate\n\n'
        '---\n\n'
        'Saves an immutable coordinate on one active scalar flow counter '
        'without emitting bytecode or consuming address space.\n\n'
        '**Usage:**\n\n'
        '```\n'
        '.slot := COORDINATE(stack, 0)\n'
        '.arg := COORDINATE(stack, 3)\n'
        '```'
    ),
}
# Generate BYTEx docs for BYTE0 through BYTE9
for _i in range(10):
    EXPRESSION_FUNCTION_DOCS[f'BYTE{_i}'] = (
        f'### `BYTE{_i}()` : Extract Byte {_i}\n\n'
        '---\n\n'
        f'Returns byte {_i} of an expression (0-indexed from least significant).\n\n'
        '**Usage:**\n\n'
        '```\n'
        f'BYTE{_i}(expression)\n'
        '```\n\n'
        f'Extracts the byte at offset {_i} from the least significant end of '
        'the evaluated value, regardless of endian setting. '
        f'This is bits {_i * 8 + 7}\u2013{_i * 8} of the value.'
    )

# Combined lookup: all directive docs keyed by name (no prefix). Includes the
# `:=` counter-coordinate declaration so aggregate consumers cannot miss it.
ALL_DIRECTIVE_DOCS: dict[str, str] = {
    **COMPILER_DIRECTIVE_DOCS,
    **BYTECODE_DIRECTIVE_DOCS,
    **PREPROCESSOR_DIRECTIVE_DOCS,
    **COUNTER_COORDINATE_DOCS,
}
