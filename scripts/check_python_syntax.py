"""Compile each Python file given on the command line and report any syntax error.

Pre-commit runs this with the oldest Python the project supports, so syntax that only newer
versions accept (such as a backslash inside an f-string expression before 3.12) is caught
before CI. Nothing is written to disk.
"""
import sys


def main(paths: list[str]) -> int:
    failed = 0
    for path in paths:
        with open(path, 'rb') as file:
            source = file.read()
        try:
            compile(source, path, 'exec', dont_inherit=True)
        except SyntaxError as error:
            failed += 1
            print(f'{path}:{error.lineno}:{error.offset}: {error.msg} (Python {sys.version.split()[0]})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
