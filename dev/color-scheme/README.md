# Color Scheme Development Demo

`color_demo.py` displays every color in BespokeASM's central editor color
scheme using both 24-bit RGB and its nearest 256-color terminal approximation.
It is a development aid for editing
`src/bespokeasm/configgen/color_scheme.py`; it is not part of the packaged
BespokeASM application.

Run it from the repository root in a color-capable terminal:

```bash
source .venv/bin/activate
PYTHONPATH=src python dev/color-scheme/color_demo.py
```
