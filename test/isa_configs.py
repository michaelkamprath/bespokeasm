"""Instruction set configurations for tests, parsed once per test session.

Parsing a large YAML configuration takes ruamel a quarter of a second, and a test that assembles
builds a new model from the configuration file each time. Tests load the parsed configuration from
here and give the assembler a JSON copy, which loads in well under a millisecond."""
import copy
import functools
import json
from pathlib import Path

from ruamel.yaml import YAML


@functools.cache
def _parsed(path: str) -> dict:
    with open(path) as handle:
        return YAML(typ='safe').load(handle)


def load_config(path) -> dict:
    """The configuration at ``path``, as a copy the caller may change."""
    return copy.deepcopy(_parsed(str(path)))


def _check_json_keys(value, where: str = 'configuration') -> None:
    # JSON turns every key into a string, which would change an integer `value_dict` key.
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f'{where} has the non-string key {key!r}, which JSON would turn into a string')
            _check_json_keys(item, f'{where}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_json_keys(item, f'{where}[{index}]')


def write_json_config(config: dict, directory) -> str:
    """Write ``config`` to `isa.json` in ``directory`` and return the file's path."""
    _check_json_keys(config)
    config_path = Path(directory) / 'isa.json'
    config_path.write_text(json.dumps(config))
    return str(config_path)


def json_config_copy(path, directory) -> str:
    """A JSON copy of the configuration at ``path``, written to ``directory``."""
    return write_json_config(_parsed(str(path)), directory)
