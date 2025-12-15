import click


def _option_help_with_metavar(param: click.Option, opt_name: str) -> str:
    """Format help text with metavar or enable/disable prefix for flags."""
    help_text = param.help or ''
    parts = []

    parts.append('[required]' if getattr(param, 'required', False) else '[optional]')

    if param.is_flag and param.secondary_opts:
        parts.append('[enable]' if opt_name in param.opts else '[disable]')
    elif not param.is_flag:
        metavar = param.make_metavar()
        if metavar:
            parts.append(f'[{metavar}]')

    if help_text:
        parts.append(help_text)

    return ' '.join(parts).strip()


class AutoOptionHelpCommand(click.Command):
    """Command that decorates option help in shell completion with metavar info."""

    def shell_complete(self, ctx, incomplete):
        results = []
        if incomplete and not incomplete[0].isalnum():
            option_items = []
            for param in self.get_params(ctx):
                if (
                    not isinstance(param, click.Option)
                    or param.hidden
                    or (
                        not param.multiple
                        and ctx.get_parameter_source(param.name)  # type: ignore
                        is click.core.ParameterSource.COMMANDLINE
                    )
                ):
                    continue

                for name in [*param.opts, *param.secondary_opts]:
                    if name.startswith(incomplete):
                        help_text = _option_help_with_metavar(param, name)
                        item = click.shell_completion.CompletionItem(name, help=help_text)
                        option_items.append((not getattr(param, 'required', False), name.lower(), item))

            option_items.sort()
            results.extend(item for _, _, item in option_items)

        # Include base completions (commands, etc.) while avoiding duplicates.
        base_results = click.core.BaseCommand.shell_complete(self, ctx, incomplete)
        seen_values = {item.value for item in results}
        for item in base_results:
            if item.value in seen_values:
                continue
            results.append(item)
        return results


class OptionForwardingCommand(AutoOptionHelpCommand):
    """Command that offers options even before a dash is typed (useful for option-only commands)."""

    def shell_complete(self, ctx, incomplete):
        results = super().shell_complete(ctx, incomplete)
        has_positional = any(isinstance(p, click.Argument) for p in self.params)
        if has_positional:
            return results

        seen = {item.value for item in results}
        option_items = []
        for param in self.params:
            if not isinstance(param, click.Option):
                continue
            for opt in param.opts + param.secondary_opts:
                if (not incomplete or opt.startswith(incomplete)) and opt not in seen:
                    help_text = _option_help_with_metavar(param, opt)
                    option_items.append(
                        (
                            not getattr(param, 'required', False),
                            opt.lower(),
                            click.shell_completion.CompletionItem(opt, help=help_text),
                        )
                    )
                    seen.add(opt)

        option_items.sort()
        results.extend(item for _, _, item in option_items)
        return results


class AutoOptionGroup(click.Group):
    """Group that applies AutoOptionHelpCommand to subcommands by default."""

    command_class = AutoOptionHelpCommand
    group_class = None


# Ensure nested groups created from AutoOptionGroup also use AutoOptionGroup.
AutoOptionGroup.group_class = AutoOptionGroup
