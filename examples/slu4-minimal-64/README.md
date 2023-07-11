# Minimal 64 Home Computer
*Current as of v1.2.x of the Minimal 64 Home Computer*

The Minimal 64 Home Computer (Minimal 64) is TTL CPU designed by Carsten Herting (slu4). Carsten has made his [Minimal 64 design open and available to others](https://github.com/slu4coder/The-Minimal-64-Home-Computer/) to build. The Minimal 64 is is well documented, and even has [a YouTube video series](https://www.youtube.com/watch?v=3zGTsi4AYLw&list=PLYlQj5cfIcBVrKpKJ-Sj68nkw6IRb9KOp) dedicated to it.


### Instruction Macros
The following instruction macros have been added in the ISA confutation file for the Minimal 64:

| Macros Instruction | Operand 1 | Operand 2 | Description |
|:-:|:-:|:-:|:--|
| `spinit` | - | - | Init the stack popint to a value of `0xFFFE`. Modifies A register. |
| `phs2` | 2 bytes | - | Pushes a 2 byte value onto the stack. Maintains byte order according to Min64 OS calling convention. |
| `pls2` | - | - | Pull 2 bytes from stack. Last byte pulled will bein A register. |
