from __future__ import annotations

import os
import re
from pathlib import Path


def _read_pyproject() -> tuple[str, str]:
    text = Path('pyproject.toml').read_text(encoding='utf-8')
    fallback_py = '3.11'
    fallback_app = '0.0.0'
    req = ''
    ver = ''

    tomllib = None
    try:
        import tomllib as _tomllib  # py3.11+
        tomllib = _tomllib
    except ImportError:
        try:
            import tomli as _tomllib  # external fallback
            tomllib = _tomllib
        except ImportError:
            tomllib = None

    if tomllib:
        data = tomllib.loads(text)
        req = data.get('project', {}).get('requires-python', '')
        ver = data.get('project', {}).get('version', '')
    else:
        m_req = re.search(r'^requires-python\s*=\s*"([^"]+)"', text, re.M)
        if m_req:
            req = m_req.group(1)
        m_ver = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        if m_ver:
            ver = m_ver.group(1)

    match = re.search(r'(\d+\.\d+)', req)
    py_version = match.group(1) if match else fallback_py
    if not ver:
        ver = fallback_app
    return py_version, ver


def _append_line(path: str | None, line: str) -> None:
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(f'{line}\n')


def main() -> None:
    py_version, app_version = _read_pyproject()

    github_output = os.getenv('GITHUB_OUTPUT')
    github_env = os.getenv('GITHUB_ENV')

    if github_output or github_env:
        _append_line(github_output, f'version={py_version}')
        _append_line(github_output, f'app_version={app_version}')
        _append_line(github_env, f'APP_VERSION={app_version}')
    else:
        print(f'PY_VERSION={py_version}')
        print(f'APP_VERSION={app_version}')


if __name__ == '__main__':
    main()
