"""`#output-format <format> <option>=<value> ...`: sets options of an output format for the lines
after it in this file. An option written without `=value` returns to the format's default.
Only the options a format offers to source are accepted; generated ISA documentation lists them."""
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel


class OutputFormatLine(PreprocessorLine):
    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        model: AssemblerModel,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        from bespokeasm.assembler.output_format import available_output_formats
        from bespokeasm.assembler.output_format import find_output_format

        words = instruction.split()[1:]
        if len(words) < 2:
            raise AssemblerError(
                line_id,
                '#output-format takes a format and one or more options, as in '
                '"#output-format listing overflow=wrap width=96"; an option without "=value" returns it '
                'to the format\'s default',
            )
        format_name = words[0]
        output_format = find_output_format(model, format_name)
        if output_format is None:
            known = ', '.join(available_output_formats(model))
            raise AssemblerError(line_id, f"#output-format names unknown format '{format_name}'; the formats are {known}")
        options = {option.name: option for option, _ in output_format.source_options()}
        self.format_name = output_format.name
        # Each option's new value, or None to return it to the format's default.
        self.values: dict[str, object] = {}
        for word in words[1:]:
            option_name, equals, text = word.partition('=')
            if option_name not in options:
                offered = (
                    f"it offers {', '.join(sorted(options))}" if options else 'it offers no options to source'
                )
                raise AssemblerError(
                    line_id,
                    f"output format '{self.format_name}' has no option '{option_name}' that source can set; {offered}",
                )
            if option_name in self.values:
                raise AssemblerError(line_id, f"#output-format sets '{option_name}' more than once")
            if not equals:
                self.values[option_name] = None
                continue
            try:
                self.values[option_name] = options[option_name].parse(text)
            except ValueError as error:
                raise AssemblerError(
                    line_id, f"#output-format {self.format_name} {option_name} must be {error}, not '{text}'",
                ) from None

    def __repr__(self) -> str:
        return f'OutputFormatLine<{self.format_name} {self.values}>'

    def applied_to(self, settings: dict[str, dict]) -> dict[str, dict]:
        """The settings after this line: a new mapping, since lines share the one before."""
        updated = {name: dict(options) for name, options in settings.items()}
        options = updated.setdefault(self.format_name, {})
        for name, value in self.values.items():
            if value is None:
                options.pop(name, None)
            else:
                options[name] = value
        return updated
