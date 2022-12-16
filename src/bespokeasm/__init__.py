import importlib.metadata

BESPOKEASM_VERSION_STR = importlib.metadata.version("bespokeasm")

# if a cconfig file requires a certain bespoke ASM version, it should be at least this version.
BESPOKEASM_MIN_REQUIRED_STR = "0.3.0"
