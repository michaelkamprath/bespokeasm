import click
import os
import sys

from bespokeasm.assembler import Assembler

@click.group()
@click.version_option("0.0.3")
def main():
    """A Bespoke ISA Assembler"""
    pass

@main.command()
@click.argument('asm_file')
@click.option('--config-file', '-c', required=True, help='the filepath to the ISA JSON config')
@click.option('--output-file', '-o', help='the filepath that the binary image will be written. Defaults to the input file name.')
@click.option('--pretty-print/--no-pretty-print',  default=False, help='if true, a pretty print version of the compilation will be produced.')
@click.option('--pretty-print-output',  default='stdout', help='if pretty-print is enabled, this specifies the output file. Defaults to stdout.')
@click.option('--verbose', '-v', count=True, help='verbosity of logging')
def compile(asm_file, config_file, output_file, pretty_print, pretty_print_output, verbose):
    if output_file is None:
        output_file = os.path.splitext(asm_file)[0] + '.bin'
    if verbose:
        click.echo(f'The file to assemble is: {asm_file}')
        click.echo(f'The binary image will be written to: {output_file}')

    asm = Assembler(asm_file, config_file, output_file, pretty_print, pretty_print_output, verbose)
    asm.assemble_bytecode()

if __name__ == '__main__':
    args = sys.argv
    if "--help" in args or len(args) == 1:
        click.echo("bespokeasm")
    main(auto_envvar_prefix='BESPOKEASM')