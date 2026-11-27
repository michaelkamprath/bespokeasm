"""Rule kinds for element-syntax sources, such as Carsten Herting's assemblers for the Minimal
computers. In these, whitespace and commas separate elements, so several statements may
share a line and an instruction's operands may continue on the next one. Data needs no
directive: its size comes from how each element is written.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field

from bespokeasm.migrate.lexer import directive_name
from bespokeasm.migrate.lexer import Element
from bespokeasm.migrate.lexer import elements
from bespokeasm.migrate.lexer import Line
from bespokeasm.migrate.rules import _check_keys
from bespokeasm.migrate.rules import _mapping
from bespokeasm.migrate.rules import MigrationContext
from bespokeasm.migrate.rules import Rule

# Directives that take the element after them as their argument.
_DIRECTIVES_WITH_ARGUMENT = {'org'}


def _is_mnemonic(text: str, context: MigrationContext) -> bool:
    return text.lower() in context.mnemonics


@dataclass
class _Statement:
    kind: str  # 'instruction', 'directive', 'data' or 'label'
    # The statement's elements, each with the index of the line it is on. An instruction's
    # operands may be on later lines than its mnemonic.
    parts: list[tuple[int, Element]] = field(default_factory=list)
    # Labels attached to the statement: (line index, element).
    labels: list[tuple[int, Element]] = field(default_factory=list)
    operands_left: int = 0
    # A label after a directive's argument that ends the line: BespokeASM allows `.org X name:`.
    trailing_label: Element | None = None
    # The line the statement is written on, and its column there.
    home: int = 0
    column: int = 0


class SplitStatements(Rule):
    """Puts each directive, each run of data and each label that isn't at the start of its
    line on a line of its own, since a BespokeASM line holds one statement. Instructions that
    share a line stay together. An instruction's operands written on the next line are moved
    up to it. A label written before an operand, which self-modifying code uses to name the
    operand's bytes, becomes an operand label: `LDI` then `value: 0xff` is `LDI @value: 0xff`."""
    kind = 'split_statements'

    def apply(self, lines, context):
        self._opcode_terms(lines, context)
        statements = self._statements(lines, context)
        rendered = self._render(lines, statements)
        new_lines: list[Line] = []
        for index, line in enumerate(lines):
            texts = rendered.get(index)
            if texts is None or texts == [line.text]:
                new_lines.append(line)
                continue
            new_lines.append(line.derive(texts[0]))
            new_lines[-1].notes.extend(line.notes)
            new_lines[-1].reports.extend(line.reports)
            new_lines.extend(line.derive(text) for text in texts[1:])
        lines[:] = new_lines

    def _statements(self, lines, context):
        statements: list[_Statement] = []
        pending_labels: list[tuple[int, Element]] = []
        open_statement: _Statement | None = None

        def attach_labels(statement: _Statement, index: int) -> None:
            # A label on an earlier line, before another label on this one, or before a
            # directive stands alone.
            if statement.kind == 'directive':
                pending_labels.append((-1, None))
            for label_index, label in pending_labels[:-1]:
                statements.append(_Statement('label', labels=[(label_index, label)], home=label_index, column=label.start))
            if pending_labels:
                label_index, label = pending_labels[-1]
                if label is None:
                    pass
                elif label_index == index:
                    statement.labels.append((label_index, label))
                else:
                    statements.append(
                        _Statement('label', labels=[(label_index, label)], home=label_index, column=label.start)
                    )
            pending_labels.clear()

        for index, line in enumerate(lines):
            if not line.active:
                continue
            line_elements = elements(line.text[:line.comment_start])
            for position, element in enumerate(line_elements):
                text = element.text
                last = statements[-1] if statements else None
                if (
                    element.is_label and position == len(line_elements) - 1 and not pending_labels
                    and last is not None and last.kind == 'directive' and not last.operands_left
                    and len(last.parts) == 2 and last.parts[-1][0] == index
                ):
                    last.trailing_label = element
                    continue
                if element.is_label:
                    pending_labels.append((index, element))
                    continue
                if open_statement is not None and open_statement.operands_left:
                    if text.startswith('#'):
                        lines[open_statement.home].reports.append(
                            f'{open_statement.parts[0][1].text} has fewer operands here than the instruction set gives it'
                        )
                        open_statement = None
                    else:
                        if _is_mnemonic(text, context) and open_statement.kind == 'instruction':
                            # A mnemonic where an operand goes is its opcode, as in `LDI INW`.
                            shape = context.shapes.get(text.lower())
                            if shape is None or shape.opcode is None:
                                line.reports.append(f'{text} is an opcode with no fixed value here')
                            else:
                                element = Element(element.start, element.end, f'0x{shape.opcode:02x}')
                                line.notes.append(f'{text} is its opcode, 0x{shape.opcode:02x}')
                        if pending_labels:
                            # A label on an operand names its bytes: an operand label.
                            head = open_statement.parts[0][1].text
                            label_index, label = pending_labels[-1]
                            if open_statement.kind != 'instruction' or len(pending_labels) > 1:
                                for label_index, label in pending_labels:
                                    lines[label_index].reports.append(
                                        f'{label.text} names an operand of {head}, which can have one operand label'
                                        if open_statement.kind == 'instruction'
                                        else f'{label.text} is between {head} and its argument'
                                    )
                            else:
                                start = label.start if label_index == index else element.start
                                element = Element(start, element.end, f'@{label.text} {element.text}')
                            pending_labels.clear()
                        open_statement.parts.append((index, element))
                        open_statement.operands_left -= 1
                        continue
                open_statement = None
                if text.startswith('#'):
                    statement = _Statement('directive', [(index, element)], home=index, column=element.start)
                    if directive_name(text) in _DIRECTIVES_WITH_ARGUMENT:
                        statement.operands_left = 1
                        open_statement = statement
                elif _is_mnemonic(text, context):
                    shape = context.shapes.get(text.lower())
                    statement = _Statement('instruction', [(index, element)], home=index, column=element.start)
                    if shape is None:
                        line.reports.append(f'the number of operands {text} takes is not known')
                    else:
                        statement.operands_left = shape.operand_count
                        if shape.operand_count:
                            open_statement = statement
                else:
                    last = statements[-1] if statements else None
                    if last is not None and last.kind == 'data' and last.home == index and not pending_labels:
                        last.parts.append((index, element))
                        continue
                    statement = _Statement('data', [(index, element)], home=index, column=element.start)
                attach_labels(statement, index)
                if statement.labels:
                    statement.column = statement.labels[0][1].start
                statements.append(statement)
        if open_statement is not None and open_statement.operands_left:
            lines[open_statement.home].reports.append(
                f'{open_statement.parts[0][1].text} is missing operands at the end of the file'
            )
        for label_index, label in pending_labels:
            statements.append(_Statement('label', labels=[(label_index, label)], home=label_index, column=label.start))
        return statements

    @staticmethod
    def _render(lines, statements) -> dict[int, list[str]]:
        """The text of each line that holds or held statements, as one or more lines."""
        by_home: dict[int, list[_Statement]] = {}
        touched = {index for statement in statements for index, _ in statement.parts + statement.labels}
        for statement in statements:
            by_home.setdefault(statement.home, []).append(statement)
        rendered: dict[int, list[str]] = {}
        for index in sorted(touched | set(by_home)):
            line = lines[index]
            groups: list[list[_Statement]] = []
            for statement in by_home.get(index, []):
                # Instructions on one line stay together unless a label starts one.
                if (
                    groups and statement.kind == 'instruction' and not statement.labels
                    and groups[-1][-1].kind == 'instruction'
                ):
                    groups[-1].append(statement)
                else:
                    groups.append([statement])
            # Code split onto a line of its own lines up with the first code on this line.
            code_column = next(
                (
                    group[0].parts[0][1].start for group in groups
                    if group[0].kind in ('instruction', 'data') and group[0].parts[0][0] == index
                ),
                None,
            )
            texts = []
            for group in groups:
                first = group[0]
                # A BespokeASM line holds one label: any others go on lines of their own.
                for _, label in first.labels[:-1]:
                    texts.append(' ' * first.column + label.text)
                text = SplitStatements._statement_text(lines, index, group)
                indent = line.text[:first.column]
                if not texts and indent.strip():
                    # What was before it moved to another line: start where the line's code did.
                    code_start = next(
                        (e.start for e in elements(line.text[:line.comment_start]) if not e.is_label), first.column,
                    )
                    indent = ' ' * code_start
                elif texts:
                    column = first.column
                    if not first.labels and first.kind in ('instruction', 'data') and code_column is not None:
                        column = code_column
                    indent = ' ' * column
                texts.append(indent + text)
            comment = line.text[line.comment_start:]
            if comment and texts:
                column = line.comment_start
                texts[0] += (' ' * (column - len(texts[0])) if len(texts[0]) < column else ' ') + comment
            elif comment:
                texts.append(' ' * line.comment_start + comment)
            rendered[index] = [text.rstrip() for text in texts] or ['']
        return rendered

    @staticmethod
    def _statement_text(lines, index, group: list[_Statement]) -> str:
        """A group's text: its last label, then its elements as written where they are all on
        this line, or joined with commas where operands came from later lines."""
        code = lines[index].text
        label = group[0].labels[-1] if group[0].labels else None
        parts = [part for statement in group for part in statement.parts]
        if not parts:
            return label[1].text
        if all(part_index == index for part_index, _ in parts):
            body = SplitStatements._group_text(code, group)
            if group[0].trailing_label is not None:
                body = code[parts[0][1].start:group[0].trailing_label.end]
        else:
            pieces = []
            for statement in group:
                texts = [element.text for _, element in statement.parts]
                pieces.append(texts[0] + (' ' + ', '.join(texts[1:]) if len(texts) > 1 else ''))
            body = ' '.join(pieces)
        # A label is on the line its statement starts on, and keeps the space after it.
        return body if label is None else code[label[1].start:parts[0][1].start] + body

    @staticmethod
    def _group_text(code: str, group: list[_Statement]) -> str:
        """Statements as written on one line, with a comma between operands that only
        whitespace separated: BespokeASM needs one."""
        text = ''
        for position, statement in enumerate(group):
            elements_ = [element for _, element in statement.parts]
            if position:
                text += code[group[position - 1].parts[-1][1].end:elements_[0].start]
            text += elements_[0].text
            for number, (previous, element) in enumerate(zip(elements_, elements_[1:])):
                separator = code[previous.end:element.start]
                if statement.kind == 'instruction' and number and ',' not in separator:
                    separator = ', ' if separator == ' ' else ',' + separator
                text += separator + element.text
        return text

    @staticmethod
    def _opcode_terms(lines, context) -> None:
        """In these assemblers a mnemonic inside an expression is its opcode, as in `AIW+0`,
        which self-modifying code stores. BespokeASM has no such term, so the opcode is written."""
        for line in lines:
            if not line.active:
                continue
            edits, named = [], []
            for element in elements(line.text[:line.comment_start]):
                text = element.text
                if element.is_label or element.is_quoted or text[0] == '#' or _is_mnemonic(text, context):
                    continue
                lead = len(text) - len(text.lstrip('<>'))
                for term in re.finditer(r'[^+\-]+', text[lead:]):
                    shape = context.shapes.get(term.group(0).lower())
                    if not _is_mnemonic(term.group(0), context):
                        continue
                    if shape is None or shape.opcode is None:
                        line.reports.append(f'{term.group(0)} in {text} is an opcode with no fixed value here')
                        break
                    start = element.start + lead + term.start()
                    edits.append((start, start + len(term.group(0)), f'0x{shape.opcode:02x}'))
                    named.append(f'{term.group(0)} is its opcode, 0x{shape.opcode:02x}')
            if edits and line.active:
                line.replace(edits)
                line.notes.append('; '.join(named))


# ---- data without a directive ----------------------------------------------------------


def _slu4_size(text: str, context: MigrationContext) -> int:
    """The size in bytes that Carsten Herting's Minimal 64x4 assembler gives a data element:
    a string's length; one byte for a character, `<expr` or `>expr`; otherwise two bytes if
    any term is a label, `*`, hex with more than two digits, or a decimal outside -128..255."""
    if text[0] in '"\'':
        return 1
    if text[0] in '<>':
        return 1
    for sign, term in re.findall(r'([+-]?)([^+\-]+)', text):
        if re.fullmatch(r'(["\']).\1', term):
            continue
        if term.startswith('0x'):
            if len(re.match(r'[0-9a-fA-F]*', term[2:]).group(0)) > 2:
                return 2
        elif term == '*':
            return 2
        elif term[0].isdigit():
            value = int(re.match(r'\d+', term).group(0)) * (-1 if sign == '-' else 1)
            if value > 255 or value < -128:
                return 2
        elif not _is_mnemonic(term, context):
            return 2
    return 1


_SIZINGS = {'slu4': _slu4_size}
_DATA_DIRECTIVES = {1: '.byte', 2: '.2byte'}


class BareData(Rule):
    """Gives data written without a directive one: `0x41, "hi", label` becomes `.byte 0x41,
    "hi"` and `.2byte label`. Each element's size comes from how it is written, by the named
    strategy; a run of elements of one size shares a directive."""
    kind = 'bare_data'

    def __init__(self, sizing: str) -> None:
        self.size = _SIZINGS[sizing]

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env)
        _check_keys(params, {'sizing'}, path, env)
        sizing = params.get('sizing')
        if sizing not in _SIZINGS:
            env.error(f'{path}.sizing', f'must be one of {", ".join(sorted(_SIZINGS))}')
        return cls(sizing)

    def apply(self, lines, context):
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.active:
                continue
            code = line.text[:line.comment_start]
            found = [element for element in elements(code) if not element.is_label]
            if not found or found[0].text[0] in '.#' or _is_mnemonic(found[0].text, context):
                continue
            if any(_is_mnemonic(e.text, context) or e.text.startswith('#') for e in found):
                continue
            groups: list[tuple[int, list[Element]]] = []
            for element in found:
                size = self.size(element.text, context)
                if groups and groups[-1][0] == size:
                    groups[-1][1].append(element)
                else:
                    groups.append((size, [element]))
            texts = [f'{_DATA_DIRECTIVES[size]} {self._values(code, group)}' for size, group in groups]
            start = found[0].start
            comment = line.text[line.comment_start:]
            first = code[:start] + texts[0]
            if comment:
                column = line.comment_start
                first += (' ' * (column - len(first)) if len(first) < column else ' ') + comment
            line.replace([(0, len(line.text), first)])
            # A label's column is not the code's: the other directives line up with this one.
            column = len(first) - len(first.lstrip()) if not code[:start].strip() else start
            label = next((e for e in elements(code) if e.is_label), None)
            if label is not None:
                column = found[0].start
            extra = [line.derive(' ' * column + text) for text in texts[1:]]
            lines[index:index] = extra
            index += len(extra)

    @staticmethod
    def _values(code: str, group: list[Element]) -> str:
        """The group's elements, with the source's spacing where its separators had commas."""
        text = group[0].text
        for previous, element in zip(group, group[1:]):
            separator = code[previous.end:element.start]
            text += separator if ',' in separator else ', '
            text += element.text
        return text


# ---- character literals -----------------------------------------------------------------


class CharLiterals(Rule):
    """Converts a single character in double quotes, used as a number, to a character literal:
    `"a"` becomes `'a'`. BespokeASM uses double quotes for strings only."""
    kind = 'char_literals'

    @classmethod
    def load(cls, params, path, env):
        params = _mapping(params, path, env)
        _check_keys(params, {'double_quoted'}, path, env)
        if params.get('double_quoted') is not True:
            env.error(f'{path}.double_quoted', 'must be true')
        return cls()

    def apply(self, lines, context):
        for line in lines:
            if not line.active:
                continue
            edits = []
            for start, end in line.strings():
                if line.text[start] != '"':
                    continue
                inner = line.text[start + 1:end - 1]
                char = inner if line.literal_backslashes else re.sub(r'\\(.)', r'\1', inner)
                if len(char) != 1:
                    continue
                escaped = '\\' + char if char in '\\\'' else char
                edits.append((start, end, f"'{escaped}'"))
            if edits:
                line.replace(edits)


# ---- origins set while muted ---------------------------------------------------------------


class MutedOrigin(Rule):
    """Carsten Herting's assemblers keep two addresses: the one labels see, and where the next
    byte goes. `#mute` stops bytes going out, and an `#org` while muted moves only the first,
    so `#mute #org 0xfc00 #emit` assembles what follows for 0xfc00 but puts it where the bytes
    were going. That becomes `.phase 0xfc00`. Carsten's `#mute` doesn't nest and BespokeASM's
    does, so a `#mute` while muted, and an `#emit` while not, are dropped.

    In those assemblers `*` is always where the bytes go. A `*` inside a phase gets a `.dephase`
    before its line if no label or instruction follows before the next `#org`; otherwise the
    line is reported. Bytes after an `#emit` whose `#mute` was followed by data, so that the
    two addresses drifted apart by an amount only assembling can tell, are reported too."""
    kind = 'muted_origin'
    _STAR = re.compile(r'(?<![\w"\'])\*(?![\w"\'])')

    def __init__(self, image_start: int | None = None) -> None:
        self.image_start = image_start

    @classmethod
    def load(cls, params, path, env):
        if params in (None, True):
            return cls()
        params = _mapping(params, path, env)
        _check_keys(params, {'image_start'}, path, env)
        start = params.get('image_start')
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            env.error(f'{path}.image_start', 'must be an address, such as 0x2000')
        return cls(start)

    def apply(self, lines, context):
        self._removed: set[int] = set()
        if self.image_start is not None:
            self._place_start(lines, context)
        self._apply(lines, context)
        lines[:] = [line for line in lines if id(line) not in self._removed]

    def _place_start(self, lines, context) -> None:
        """Bytes before the first #org go to ``image_start``, while addresses start at 0."""
        uses_addresses = False
        for index, line in enumerate(lines):
            kind = self._kind(line, context) if line.active else 'other'
            if kind == 'org':
                return
            statement = line.statement() if line.active else None
            if statement is not None and (statement.label is not None or kind == 'instruction'):
                uses_addresses = True
            if kind in ('bytes', 'instruction'):
                break
        else:
            return
        uses_addresses = uses_addresses or any(
            line.active and (line.statement().label is not None or self._kind(line, context) == 'instruction'
                             or self._STAR.search(line.code))
            for line in lines[index:]
            if not (line.active and self._kind(line, context) == 'org')
        )
        first = index
        while first > 0 and lines[first - 1].statement().label is not None:
            first -= 1
        inserted = [lines[first].derive(f'.org 0x{self.image_start:04x}')]
        if uses_addresses and self.image_start != 0:
            inserted.append(lines[first].derive('.phase 0x0000'))
        lines[first:first] = inserted

    def _apply(self, lines, context):
        muted = False
        phased = False
        region: list[int] = []  # the lines of the current muted region
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.active:
                index += 1
                continue
            kind = self._kind(line, context)
            if kind == 'mute':
                if muted:
                    line.dropped = True
                else:
                    muted, region = True, [index]
            elif kind == 'emit':
                if not muted:
                    line.dropped = True
                else:
                    muted = False
                    region.append(index)
                    phased = self._close_region(lines, region, context) or phased
            elif muted:
                region.append(index)
            elif kind == 'org':
                phased = False
            elif phased and self._STAR.search(line.code[line.statement().operands_start:]):
                if self._nothing_depends_on_addresses(lines, index, context):
                    # Before the whole source line, if a rule split it.
                    first = index
                    while first > 0 and lines[first - 1].number == line.number:
                        first -= 1
                    indent = lines[first].text[:len(lines[first].text) - len(lines[first].text.lstrip())]
                    lines.insert(first, line.derive(f'{indent}.dephase'))
                    index += 1
                    phased = False
                else:
                    line.reports.append(
                        '"*" here is where the bytes go, which is not the address inside this .phase'
                    )
            index += 1

    def _close_region(self, lines, region: list[int], context) -> bool:
        """Convert a muted region that moved the address, at its #emit. True if a phase begins."""
        kinds = [self._kind(lines[i], context) for i in region]
        if 'org' not in kinds and 'bytes' not in kinds and 'instruction' not in kinds:
            return False
        if not self._bytes_follow(lines, region[-1] + 1, context):
            return False
        emit = lines[region[-1]]
        if 'bytes' in kinds or 'instruction' in kinds:
            emit.reports.append(
                'the bytes after this #emit go where they were going at the #mute, not at the address; '
                'data while muted moved the address by an amount only assembling can tell'
            )
            return False
        numbers = [lines[i].number for i in region]
        first = lines[region[0]]
        for i, kind in zip(region, kinds):
            line = lines[i]
            if kind == 'org':
                head = line.statement().head_span
                line.replace([(head[0], head[1], '.phase')])
                if numbers.count(line.number) > 1:
                    # One source line, `#mute #org 0xfc00 #emit`, becomes one `.phase 0xfc00`.
                    indent = len(first.text) - len(first.text.lstrip())
                    line.replace([(0, len(line.text) - len(line.text.lstrip()), first.text[:indent])])
            elif kind in ('mute', 'emit'):
                if numbers.count(line.number) > 1:
                    self._removed.add(id(line))
                    org = next(
                        (lines[j] for j, k in zip(region, kinds) if k == 'org' and lines[j].number == line.number),
                        None,
                    )
                    comment = line.text[line.comment_start:]
                    if comment and org is not None and org.comment_start == len(org.text):
                        org.replace([(len(org.text), len(org.text), ' ' + comment)])
                else:
                    line.dropped = True
        return True

    def _bytes_follow(self, lines, start: int, context) -> bool:
        """Whether bytes go out after ``start`` before the next #org, #mute or the end of the file."""
        for line in lines[start:]:
            kind = self._kind(line, context)
            if kind in ('org', 'mute'):
                return False
            if kind in ('bytes', 'instruction'):
                return True
        return False

    def _nothing_depends_on_addresses(self, lines, start: int, context) -> bool:
        for line in lines[start + 1:]:
            kind = self._kind(line, context)
            if kind in ('org', 'mute'):
                return True
            statement = line.statement()
            if statement.label is not None or kind == 'instruction':
                return False
        return True

    @staticmethod
    def _kind(line: Line, context: MigrationContext) -> str:
        """'mute', 'emit', 'org', 'instruction', 'bytes' (data or alignment) or 'other'."""
        statement = line.statement()
        head = statement.head
        if head is None:
            # Data without a directive, such as `0xff`, or nothing but a label.
            return 'bytes' if line.code[statement.operands_start:].strip() else 'other'
        name = directive_name(head)
        if head[0] in '#.' and name in ('mute', 'emit', 'org'):
            return name
        if head.lower() in context.mnemonics:
            return 'instruction'
        if head[0] == '#':
            return 'bytes' if name == 'page' else 'other'
        if head[0] == '.':
            return 'other' if name in ('phase', 'dephase', 'memzone') else 'bytes'
        # A word that isn't a mnemonic begins data, as a label does in `start, end-start`.
        return 'bytes'
