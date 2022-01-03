
from bespokeasm.assembler.model import AssemblerModel

class LanguageConfigGenerator:
    def __init__(self, config_file_path: str, is_verbose: int) -> None:
        self._model = AssemblerModel(config_file_path, is_verbose)
        self._verbose = is_verbose

    @property
    def model(self) -> AssemblerModel:
        return self._model
    @property
    def verbose(self) -> int:
        return self._verbose