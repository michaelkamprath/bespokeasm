def split_line_comment(line: str) -> tuple[str, str]:
    """Split a source line into code and trailing comment.

    A semicolon starts a comment only when it is outside quoted literals.
    """
    in_quote: str | None = None
    escaped = False

    for index, character in enumerate(line):
        if in_quote is not None:
            if escaped:
                escaped = False
                continue
            if character == '\\':
                escaped = True
                continue
            if character == in_quote:
                in_quote = None
            continue

        if character in ("'", '"'):
            in_quote = character
            continue

        if character == ';':
            return line[:index], line[index + 1:]

    return line, ''


def split_operands(operand_str: str | None) -> list[str]:
    """Split an instruction operand string by top-level commas.

    Commas inside quotes or bracketed groups are preserved.
    """
    if operand_str is None:
        return []
    if operand_str.strip() == '':
        return []
    parts: list[str] = []
    start = 0
    for index in top_level_indexes(operand_str, ','):
        parts.append(operand_str[start:index].strip())
        start = index + 1
    parts.append(operand_str[start:].strip())
    return parts


def top_level_indexes(text: str, character: str) -> list[int]:
    """The positions of ``character`` in ``text`` outside quotes and outside any `( )`, `[ ]`
    or `{ }` group: in `$10 + [a+6]` only the first `+` is top level."""
    indexes: list[int] = []
    in_quote: str | None = None
    escaped = False
    depth = {'(': 0, '[': 0, '{': 0}
    closers = {')': '(', ']': '[', '}': '{'}
    for index, current in enumerate(text):
        if in_quote is not None:
            if escaped:
                escaped = False
            elif current == '\\':
                escaped = True
            elif current == in_quote:
                in_quote = None
            continue
        if current in ("'", '"'):
            in_quote = current
        elif current in depth:
            depth[current] += 1
        elif current in closers and depth[closers[current]] > 0:
            depth[closers[current]] -= 1
        elif current == character and not any(depth.values()):
            indexes.append(index)
    return indexes


def encloses_whole(text: str, opener: str, closer: str) -> bool:
    """Whether ``text`` starts with ``opener`` and the ``closer`` matching it is the last
    character: true for `(vec)` and `((a+1)*2)`, false for `(a)+(b)`, `(a+1)*2` and `(a`.
    Quoted characters, as in `(')')`, don't count."""
    if len(text) < 2 or text[0] != opener or text[-1] != closer:
        return False
    depth = 0
    in_quote: str | None = None
    escaped = False
    for index, character in enumerate(text):
        if in_quote is not None:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == in_quote:
                in_quote = None
            continue
        if character in ("'", '"'):
            in_quote = character
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return index == len(text) - 1
    return False


def enclosure_depth(text: str, opener: str, closer: str) -> int:
    """How many pairs of ``opener`` and ``closer`` wrap the whole of ``text``: 2 for `((vec))`,
    1 for `((vec)+1)`, 0 for `vec` or `(a)+(b)`."""
    depth = 0
    text = text.strip()
    while encloses_whole(text, opener, closer):
        depth += 1
        text = text[1:-1].strip()
    return depth
