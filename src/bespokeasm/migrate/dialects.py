"""Loads the ``migrations`` section of an instruction set configuration.

```yaml
migrations:
  oldasm:
    description: The assembler this source was written for
    rules:
      - rename_directives: {include: '#include', org: '.org'}
      - local_labels: {prefix: '@'}
      - anonymous_labels
```

Each dialect's rules run in the order listed. A rule with no parameters may be written as a
bare name.
"""
from __future__ import annotations

from dataclasses import dataclass

from bespokeasm.migrate.rules import LoadEnvironment
from bespokeasm.migrate.rules import Rule
from bespokeasm.migrate.rules import RULE_KINDS

DIALECT_KEYS = {'description', 'rules'}


@dataclass
class Dialect:
    name: str
    description: str
    rules: list[Rule]

    @property
    def doubled_quotes(self) -> bool:
        """Whether a doubled quote inside a string is part of it, as in `'IT''S'`."""
        return any(getattr(rule, 'doubled_quotes', False) for rule in self.rules)


def load_migrations(section, env: LoadEnvironment) -> dict[str, Dialect]:
    if section is None:
        return {}
    if not isinstance(section, dict):
        env.error('migrations', 'must be a mapping of dialect names to their rules')
    dialects = {}
    for name, config in section.items():
        path = f'migrations.{name}'
        if not isinstance(name, str) or not name.replace('-', '_').isidentifier():
            env.error(path, 'must be named with letters, digits, "_" or "-"')
        if not isinstance(config, dict):
            env.error(path, 'must be a mapping with "description" and "rules"')
        for key in config:
            if key not in DIALECT_KEYS:
                env.error(f'{path}.{key}', 'is not a dialect setting; a dialect has "description" and "rules"')
        description = config.get('description', '')
        if not isinstance(description, str):
            env.error(f'{path}.description', 'must be a string')
        rules_config = config.get('rules')
        if not isinstance(rules_config, list) or not rules_config:
            env.error(f'{path}.rules', 'must be a list with at least one rule')
        rules = [_load_rule(entry, f'{path}.rules[{index}]', env) for index, entry in enumerate(rules_config)]
        dialects[name] = Dialect(name, description.strip(), rules)
    return dialects


def _load_rule(entry, path: str, env: LoadEnvironment) -> Rule:
    if isinstance(entry, str):
        kind, params = entry, None
    elif isinstance(entry, dict) and len(entry) == 1:
        ((kind, params),) = entry.items()
    else:
        env.error(path, 'must be a rule name, or a mapping of one rule name to its parameters')
    if kind not in RULE_KINDS:
        choices = ', '.join(sorted(RULE_KINDS))
        env.error(path, f'"{kind}" is not a migration rule; the rules are {choices}')
    return RULE_KINDS[kind].load(params, f'{path}.{kind}', env)
