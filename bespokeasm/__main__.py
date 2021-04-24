import sys
import click

from bespokeasm.assembler import Assembler

@click.group()
@click.version_option("0.0.1")
def main():
    """A Bespoke ISA Assembler"""
    click.echo("bespokeasm is cool")
    pass

@main.command()
@click.argument('asm_file')
@click.option('--config-file', '-c', required=True, help='the filepath to the ISA JSON config')
@click.option('--verbose', '-v', count=True, help='verbosity of logging')
def compile(asm_file, config_file, verbose):
    if verbose:
        click.echo(f'the file to assemble is {asm_file}')
    asm = Assembler(asm_file, config_file, verbose)
    asm.assemble_bytecode()

if __name__ == '__main__':
    args = sys.argv
    if "--help" in args or len(args) == 1:
        click.echo("bespokeasm")
    main()