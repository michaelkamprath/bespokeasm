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
    current: list[str] = []
    in_quote: str | None = None
    escaped = False
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0

    for character in operand_str:
        if in_quote is not None:
            current.append(character)
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == in_quote:
                in_quote = None
            continue

        if character in ("'", '"'):
            in_quote = character
            current.append(character)
            continue

        if character == '(':
            paren_depth += 1
        elif character == ')' and paren_depth > 0:
            paren_depth -= 1
        elif character == '[':
            bracket_depth += 1
        elif character == ']' and bracket_depth > 0:
            bracket_depth -= 1
        elif character == '{':
            brace_depth += 1
        elif character == '}' and brace_depth > 0:
            brace_depth -= 1

        if character == ',' and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
            parts.append(''.join(current).strip())
            current = []
            continue

        current.append(character)

    parts.append(''.join(current).strip())
    return parts
