"""The library of migration rule kinds.

Each kind reads its parameters from the configuration with ``load``, which reports a bad
parameter by its configuration path, and rewrites a file's lines with ``apply``. Rules work
on the masked code of a line (see :mod:`.lexer`), so they never change string literals or
comments, except where a rule is about strings.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from bespokeasm.migrate.lexer import directive_name
from bespokeasm.migrate.lexer import Line


@dataclass
class LoadEnvironment:
    """What a rule needs from the configuration to check its parameters."""
    # Reports a configuration error: (path, problem). Does not return.
    error: Callable[[str, str], None]
    # Every directive a rule may produce, as written: `.org`, `.word`, `#include` and so on.
    directive_spellings: frozenset[str]


@dataclass
class MigrationContext:
    """What a rule needs from the instruction set while migrating."""
    # The instruction set's mnemonics, in lower case. A bare word that is one is never a directive.
    mnemonics: frozenset[str]
    # BespokeASM's directive names, in lower case, without their `.` or `#`.
    directive_names: frozenset[str]


class Rule:
    kind = ''

    @classmethod
    def load(cls, params, path: str, env: LoadEnvironment) -> Rule:
        if params not in (None, {}, True):
            env.error(path, 'takes no parameters')
        return cls()

    def apply(self, lines: list[Line], context: MigrationContext) -> None:
        raise NotImplementedError


# ---- parameter checks ---------------------------------------------------------


def _mapping(params, path: str, env: LoadEnvironment) -> dict:
    if not isinstance(params, dict) or not params:
        env.error(path, 'must be a mapping with at least one entry')
    return params


def _names(params, path: str, env: LoadEnvironment) -> list[str]:
    if not isinstance(params, list) or not params:
        env.error(path, 'must be a list with at least one name')
    for index, name in enumerate(params):
        if not isinstance(name, str) or directive_name(name) is None:
            env.error(f'{path}[{index}]', 'must be a directive name')
    return params


def _string(params: dict, key: str, path: str, env: LoadEnvironment, *, default: str | None = None) -> str | None:
    value = params.get(key, default)
    if value is not None and (not isinstance(value, str) or not value):
        env.error(f'{path}.{key}', 'must be a non-empty string')
    return value


def _check_keys(params: dict, allowed: set[str], path: str, env: LoadEnvironment) -> None:
    for key in params:
        if key not in allowed:
            choices = ', '.join(f'"{name}"' for name in sorted(allowed))
            env.error(f'{path}.{key}', f'is not a parameter of this rule; it takes {choices}')


# ---- matching statements --------------------------------------------------------


def _is_assignment(code: str, end: int) -> bool:
    """Whether the word ending at ``end`` is the symbol of an assignment, as in `name = 1`."""
    rest = code[end:].lstrip()
    return rest.startswith(('=', ':=')) or re.match(r'(?i)(?:equ|eq|set)\b', rest) is not None


def _directive_at(line: Line, names: dict[str, object], context: MigrationContext):
    """The entry of ``names`` for the directive that begins the line's statement, if any.

    A source name matches with or without a leading `.` or `#`, in any case. A bare word
    matches only where it can't be an instruction or the symbol of an assignment.
    """
    statement = line.statement()
    if statement.head is None:
        return None, statement
    name = directive_name(statement.head)
    if name not in names:
        return None, statement
    bare = statement.head[0] not in '.#'
    if bare and statement.head.lower() in context.mnemonics:
        return None, statement
    if _is_assignment(line.code, statement.head_span[1]):
        return None, statement
    return names[name], statement


# ---- rule kinds -------------------------------------------------------------------


class RenameDirectives(Rule):
    """Renames directives: `.include "x"` becomes `#include "x"`. Arguments are kept."""
    kind = 'rename_directives'

    def __init__(self, renames: dict[str, str]) -> None:
        self.renames = renames

    @classmethod
    def load(cls, params, path, env):
        renames = {}
        for source, target in _mapping(params, path, env).items():
            if not isinstance(source, str) or directive_name(source) is None:
                env.error(f'{path}.{source}', 'must be a directive name')
            if target not in env.directive_spellings:
                env.error(
                    f'{path}.{source}',
                    f'must name a BespokeASM directive, such as ".org" or "#include", not {target!r}',
                )
            renames[directive_name(source)] = target
        return cls(renames)

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            target, statement = _directive_at(line, self.renames, context)
            # A directive already written as its target, in any case, is left as it is.
            if target is not None and statement.head.lower() != target.lower():
                line.replace([(*statement.head_span, target)])


class DropDirectives(Rule):
    """Comments out directives with no meaning in BespokeASM, such as a CPU selection."""
    kind = 'drop_directives'

    def __init__(self, names: list[str]) -> None:
        self.names = {directive_name(name): True for name in names}

    @classmethod
    def load(cls, params, path, env):
        return cls(_names(params, path, env))

    def apply(self, lines, context):
        for line in lines:
            if line.active and _directive_at(line, self.names, context)[0]:
                line.dropped = True


class Unsupported(Rule):
    """Keeps a directive BespokeASM can't express as a reported comment. An entry such as
    `{macro: endmacro}` names a block, and reports every line from the first directive to
    the second, so a macro's body isn't assembled where it is defined; `{repeat: [endrep,
    endrepeat]}` names a block with either ending. A later line that uses a block's name,
    such as a macro's, is reported too."""
    kind = 'unsupported'

    def __init__(self, names: list[str], blocks: dict[str, list[str]]) -> None:
        self.names = {directive_name(name): True for name in names}
        self.blocks = {
            directive_name(start): frozenset(directive_name(end) for end in ends) for start, ends in blocks.items()
        }

    @classmethod
    def load(cls, params, path, env):
        if not isinstance(params, list) or not params:
            env.error(path, 'must be a list of directive names, or of {start: end} blocks')
        names, blocks = [], {}
        for index, entry in enumerate(params):
            entry_path = f'{path}[{index}]'
            if isinstance(entry, dict):
                if len(entry) != 1:
                    env.error(entry_path, 'must name one block, as {macro: endmacro}')
                ((start, end),) = entry.items()
                ends = end if isinstance(end, list) else [end]
                if (
                    directive_name(start) is None or not ends
                    or not all(isinstance(name, str) and directive_name(name) is not None for name in ends)
                ):
                    env.error(entry_path, 'must name a block\'s first and last directives, as {macro: endmacro}')
                blocks[start] = ends
            elif isinstance(entry, str) and directive_name(entry) is not None:
                names.append(entry)
            else:
                env.error(entry_path, 'must be a directive name, or a {start: end} block')
        return cls(names, blocks)

    def apply(self, lines, context):
        # A block's name, such as a macro's, and the line that defines it: a later line that
        # uses the name is reported too.
        defined: dict[str, tuple[str, int]] = {}
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.active:
                end_names, statement = _directive_at(line, self.blocks, context)
                if end_names is not None:
                    name = re.match(r'\s*([A-Za-z_][\w.]*)', line.code[statement.operands_start:])
                    if name is not None:
                        defined[name.group(1).lower()] = (statement.head, line.number)
                    index = self._report_block(lines, index, statement.head, end_names)
                    continue
                if _directive_at(line, self.names, context)[0]:
                    line.reports.append(f'{statement.head} is not supported')
                elif statement.head is not None and statement.head.lower() in defined:
                    head, number = defined[statement.head.lower()]
                    line.reports.append(f'uses {statement.head}, defined by the {head} on line {number}')
            index += 1

    def _report_block(self, lines, start, head, end_names) -> int:
        start_name = directive_name(head)
        lines[start].reports.append(f'{head} is not supported')
        depth = 1
        index = start + 1
        while index < len(lines) and depth:
            line = lines[index]
            name = directive_name(line.statement().head)
            if name == start_name:
                depth += 1
            elif name in end_names:
                depth -= 1
            line.reports.append(f'inside the {head} on line {lines[start].number}')
            line.quiet = True
            index += 1
        return index


class LocalLabels(Rule):
    """Converts local labels to BespokeASM's `.name`: `@loop` with `prefix: '@'`, or `loop$`
    with `suffix: '$'`. A BespokeASM local label has the same scope: it is valid between two
    other labels."""
    kind = 'local_labels'

    def __init__(self, prefix: str | None, suffix: str | None) -> None:
        if prefix is not None:
            self.pattern = re.compile(r'(?<![\w.@$])' + re.escape(prefix) + r'([A-Za-z_]\w*)(?![\w$])')
        else:
            self.pattern = re.compile(r'(?<![\w.@$])([A-Za-z0-9_]\w*)' + re.escape(suffix) + r'(?![\w$])')

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env)
        _check_keys(params, {'prefix', 'suffix'}, path, env)
        prefix, suffix = _string(params, 'prefix', path, env), _string(params, 'suffix', path, env)
        if (prefix is None) == (suffix is None):
            env.error(path, 'takes either "prefix" or "suffix"')
        return cls(prefix, suffix)

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            edits = []
            for match in self.pattern.finditer(line.code):
                name = match.group(1)
                if name.lower() in context.directive_names:
                    line.reports.append(f'{match.group(0)} would become the directive .{name}; rename it')
                    break
                edits.append((match.start(), match.end(), f'.{name}'))
            else:
                if edits:
                    line.replace(edits)


class AnonymousLabels(Rule):
    """Gives anonymous labels names. A lone `:` where a label goes defines one; `:+` refers to
    the next, `:++` the one after it, and `:-` and `:--` count back the same way. Each becomes
    a local label, `.anon_1` and so on, so a reference that crosses another label is reported."""
    kind = 'anonymous_labels'
    _REFERENCE = re.compile(r'(?<![\w.@$:]):(\++|-+|>+|<+)(?![\w.@$])')

    def apply(self, lines, context):
        definitions = []  # (line index, column)
        references = []  # (line index, column, end, forward, count)
        boundaries = []  # (line index, column, label)
        for index, line in enumerate(lines):
            if not line.active:
                continue
            statement = line.statement()
            if statement.anonymous_label_span is not None:
                definitions.append((index, statement.anonymous_label_span[0]))
            elif statement.label is not None and statement.label[0] not in '.@' and not statement.label.endswith('$'):
                boundaries.append((index, statement.label_span[0], statement.label))
            if directive_name(statement.head) in ('org', 'memzone') and statement.head[0] == '.':
                boundaries.append((index, statement.head_span[0], statement.head))
            for match in self._REFERENCE.finditer(line.code, statement.operands_start):
                signs = match.group(1)
                references.append((index, match.start(), match.end(), signs[0] in '+>', len(signs)))
        if not definitions and not references:
            return
        base = self._unused_base(lines)
        names = {position: f'.{base}{ordinal}' for ordinal, position in enumerate(definitions, start=1)}
        edits: dict[int, list[tuple[int, int, str]]] = {}
        for index, column in definitions:
            edits.setdefault(index, []).append((column, column + 1, f'{names[(index, column)]}:'))
        for index, start, end, forward, count in references:
            position = (index, start)
            candidates = (
                [d for d in definitions if d > position] if forward else [d for d in reversed(definitions) if d < position]
            )
            text = lines[index].text[start:end]
            if len(candidates) < count:
                lines[index].reports.append(f'{text} has no anonymous label to refer to')
                continue
            target = candidates[count - 1]
            low, high = min(target, position), max(target, position)
            crossed = next((label for i, c, label in boundaries if low < (i, c) < high), None)
            if crossed is not None:
                lines[index].reports.append(f'{text} crosses {crossed}; give its anonymous label a name')
                continue
            edits.setdefault(index, []).append((start, end, names[target]))
        for index, line_edits in edits.items():
            if lines[index].active:
                lines[index].replace(line_edits)

    @staticmethod
    def _unused_base(lines) -> str:
        words = {word.lower() for line in lines for word in re.findall(r'[\w.@$]+', line.code)}
        base = 'anon_'
        while any(word.lstrip('.@').startswith(base) for word in words):
            base = f'{base}_'
        return base


class ColonlessLabels(Rule):
    """Adds the colon to a label written without one in the first column: `loop  dex`
    becomes `loop: dex`. A name followed by `=`, `equ` or `set` is an assignment and is left
    as it is."""
    kind = 'colonless_labels'
    # A local label ending in `$` may start with a digit, as in `1$`.
    _LABEL = re.compile(r'([A-Za-z_.][\w.]*\$?|\d\w*\$)(?=\s|$)')

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            match = self._LABEL.match(line.code)
            if match is None or _is_assignment(line.code, match.end()):
                continue
            name = match.group(1)
            if name.startswith('.') and directive_name(name) in context.directive_names:
                continue
            line.replace([(match.end(), match.end(), ':')])


class OriginAssignment(Rule):
    """Converts an origin set by assignment, `*= $8000` or `* = $8000`, to `.org $8000`."""
    kind = 'origin_assignment'

    def __init__(self, symbol: str) -> None:
        self.pattern = re.compile(r'^(\s*)' + re.escape(symbol) + r'\s*=(?!=)\s*')

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env) if params not in (None, True) else {}
        _check_keys(params, {'symbol'}, path, env)
        return cls(_string(params, 'symbol', path, env, default='*'))

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            match = self.pattern.match(line.code)
            if match is not None:
                line.replace([(match.start(), match.end(), f'{match.group(1)}.org ')])


class OperandPrefixes(Rule):
    """Handles address-size prefixes on operands, such as `z:` and `a:`. A prefix in `drop`
    is removed; one in `unsupported` is reported."""
    kind = 'operand_prefixes'

    def __init__(self, drop: list[str], unsupported: list[str]) -> None:
        self.drop = {prefix.lower() for prefix in drop}
        prefixes = sorted(self.drop | {prefix.lower() for prefix in unsupported}, key=len, reverse=True)
        self.pattern = re.compile(r'(?<![\w.@$])(?:' + '|'.join(map(re.escape, prefixes)) + ')', re.IGNORECASE)

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env)
        _check_keys(params, {'drop', 'unsupported'}, path, env)
        lists = {}
        for key in ('drop', 'unsupported'):
            value = params.get(key, [])
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                env.error(f'{path}.{key}', 'must be a list of prefixes, such as "z:"')
            lists[key] = value
        if not lists['drop'] and not lists['unsupported']:
            env.error(path, 'must list at least one prefix in "drop" or "unsupported"')
        return cls(lists['drop'], lists['unsupported'])

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            edits = []
            for match in self.pattern.finditer(line.code, line.statement().operands_start):
                if match.group(0).lower() in self.drop:
                    edits.append((match.start(), match.end(), ''))
                else:
                    line.reports.append(f'the {match.group(0)} operand prefix is not supported')
                    break
            else:
                if edits:
                    line.replace(edits)


class CurrentAddressSymbol(Rule):
    """Converts another current-address symbol, such as a standalone `$`, to `*`. `$7C` stays
    a hex literal."""
    kind = 'current_address_symbol'

    def __init__(self, symbol: str) -> None:
        self.pattern = re.compile(r'(?<![\w$])' + re.escape(symbol) + r'(?![\w$])')

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env)
        _check_keys(params, {'symbol'}, path, env)
        symbol = _string(params, 'symbol', path, env)
        if symbol is None:
            env.error(f'{path}.symbol', 'is required')
        return cls(symbol)

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            edits = [
                (match.start(), match.end(), '*')
                for match in self.pattern.finditer(line.code, line.statement().operands_start)
            ]
            if edits:
                line.replace(edits)


class StringEscapes(Rule):
    """Converts a quote written twice inside a string, `'IT''S'`, to an escaped one, `'IT\\'S'`."""
    kind = 'string_escapes'
    doubled_quotes = True

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env)
        _check_keys(params, {'doubled_quotes'}, path, env)
        if params.get('doubled_quotes') is not True:
            env.error(f'{path}.doubled_quotes', 'must be true')
        return cls()

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            edits = []
            for start, end in line.strings():
                quote = line.text[start]
                inner = line.text[start + 1:end - 1]
                if quote * 2 in inner:
                    edits.append((start + 1, end - 1, inner.replace(quote * 2, '\\' + quote)))
            if edits:
                line.replace(edits)


class AssignmentOperators(Rule):
    """Converts other assignment operators, such as `:=`, to `=`."""
    kind = 'assignment_operators'

    def __init__(self, operators: list[str]) -> None:
        alternatives = '|'.join(
            re.escape(operator) + (r'\b' if operator[-1].isalnum() else '')
            for operator in sorted(operators, key=len, reverse=True)
        )
        self.pattern = re.compile(r'^(\s*[A-Za-z_.@][\w.@]*\$?\s*)(?:' + alternatives + ')', re.IGNORECASE)

    @classmethod
    def load(cls, params, path, env):
        if not isinstance(params, list) or not params or not all(isinstance(item, str) and item for item in params):
            env.error(path, 'must be a list of assignment operators, such as ":="')
        return cls(params)

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            match = self.pattern.match(line.code)
            if match is not None:
                line.replace([(match.end(1), match.end(), '=')])


RULE_KINDS: dict[str, type[Rule]] = {
    rule.kind: rule
    for rule in (
        RenameDirectives,
        DropDirectives,
        Unsupported,
        LocalLabels,
        AnonymousLabels,
        ColonlessLabels,
        OriginAssignment,
        OperandPrefixes,
        CurrentAddressSymbol,
        StringEscapes,
        AssignmentOperators,
    )
}
