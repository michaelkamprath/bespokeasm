from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.docsgen import build_documentation_model
from bespokeasm.docsgen import directive_docs
from bespokeasm.docsgen.markdown_generator import MarkdownGenerator


def build_hover_docs(assembler_model: AssemblerModel, verbose: int = 0) -> dict:
    doc_model = build_documentation_model(assembler_model, verbose)
    markdown_generator = MarkdownGenerator(doc_model, verbose)
    instruction_docs = {
        name.upper(): markdown_generator.generate_instruction_markdown(
            name,
            doc,
            add_header_rule=True
        )
        for name, doc in doc_model.instruction_docs.items()
    }
    macro_docs = {
        name.upper(): markdown_generator.generate_instruction_markdown(
            name,
            doc,
            include_missing_doc_notice=False,
            add_header_rule=True
        )
        for name, doc in doc_model.macro_docs.items()
    }
    return {
        'instructions': instruction_docs,
        'macros': macro_docs,
        'predefined': markdown_generator.generate_predefined_hover_docs(),
        'directives': {
            'compiler': directive_docs.COMPILER_DIRECTIVE_DOCS,
            'data_type': directive_docs.BYTECODE_DIRECTIVE_DOCS,
            'preprocessor': directive_docs.PREPROCESSOR_DIRECTIVE_DOCS,
        },
        'registers': markdown_generator.generate_register_hover_docs(),
        'expression_functions': directive_docs.EXPRESSION_FUNCTION_DOCS,
    }
