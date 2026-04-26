# GMC-4 / SFMT Assembler

This example configuration creates a BespokeASM assembler for the [Gakken GMC-4](https://en.wikipedia.org/wiki/GMC-4) (a 4-bit educational microcomputer kit released in 2009 as part of the *Otona-no-Kagaku* series), which shares its instruction set with the older Radio Shack *Science Fair Microcomputer Trainer* (SFMT). Both machines descend from the mid-1970s Gakken FX-MICOM R-165.

## Architecture Summary

The GMC-4 is a 4-bit Harvard-architecture machine.

| | |
|---|---|
| **Word size** | 4 bits (one nibble) |
| **Program memory** | 80 nibbles, addresses `0x00`–`0x4F` |
| **Data memory** | 16 nibbles, addresses `0x50`–`0x5F` |
| **Primary registers** | `A` (accumulator), `Y` (data pointer) |
| **Shadow registers** | `B`, `Z` — exchanged with `A`, `Y` by the `CH` instruction |
| **Auxiliary set** | `A'`, `B'`, `Y'`, `Z'` — exchanged with `{A,B,Y,Z}` by the `CHNG` CAL routine |
| **Status** | A single 1-bit `FLAG` |

Data memory is addressed indirectly through `Y` as `mem[0x50 + Y]`.

## Instruction Encoding

Every instruction starts with a 4-bit opcode in the high nibble. There are three sizes:

| Form | Opcodes | Size |
|---|---|---|
| `[op]` | `0`–`7` | 1 nibble |
| `[op] [imm4]` | `8`–`E` | 2 nibbles |
| `[op] [addr_hi4] [addr_lo4]` | `F` | 3 nibbles |

The `JUMP` opcode (`F`) is the only three-nibble instruction. Its 8-bit operand is an absolute program address (validated against the program memory zone, `0x00`–`0x4F`).

The `cal` opcode (`E`) selects one of the built-in subroutines via its low nibble. The original GMC-4 assembly notation is retained: write `cal RSTO`, `cal DSPR`, etc., where the routine name is a predefined constant resolving to its 4-bit index. A bare numeric immediate (`cal 0xD`) also works.

## Mnemonics

BespokeASM mnemonics are case-insensitive. This example uses mnemonic decorators directly, so the historical GMC-4 spellings `m+`, `m-`, `dem+`, and `dem-` assemble as written.

The configuration also sets `default_numeric_base: hex`, so unprefixed numeric operands are interpreted as hexadecimal. Source code may write operands as bare hex digits (`aia f`, `tiy a`, `cia b`) and the historic GMC-4 / SFMT manual listings assemble unmodified. The standard prefixed forms (`0x1F`, `$1F`, `1Fh`, `b1010`, `%1010`) continue to work as explicit overrides.

### Primary instructions

| Mnemonic | Opcode | Operand | Effect |
|---|---|---|---|
| `ka` | `0` | — | `A` ← keypad. `FLAG=1` if no key was pressed. |
| `ao` | `1` | — | Display `A` on the 7-segment LED. |
| `ch` | `2` | — | Swap `A`↔`B` and `Y`↔`Z`. |
| `cy` | `3` | — | Swap `A`↔`Y`. |
| `am` | `4` | — | `mem[0x50+Y]` ← `A`. |
| `ma` | `5` | — | `A` ← `mem[0x50+Y]`. |
| `m+` | `6` | — | `A` ← `A + mem[0x50+Y]`. `FLAG=1` on carry. |
| `m-` | `7` | — | `A` ← `mem[0x50+Y] - A`. `FLAG=1` on borrow. |
| `tia n` | `8` | 4-bit imm | `A` ← `n`. |
| `aia n` | `9` | 4-bit imm | `A` ← `A + n`. `FLAG=1` on carry. |
| `tiy n` | `A` | 4-bit imm | `Y` ← `n`. |
| `aiy n` | `B` | 4-bit imm | `Y` ← `Y + n`. `FLAG=1` on carry. |
| `cia n` | `C` | 4-bit imm | `FLAG=0` iff `A == n`, else `1`. |
| `ciy n` | `D` | 4-bit imm | `FLAG=0` iff `Y == n`, else `1`. |
| `cal n` | `E` | 4-bit imm | Call built-in subroutine `n` (see below). |
| `jump a` | `F` | 8-bit addr | If `FLAG==1`, jump to `a`. After execution `FLAG` is forced to `1`. |

### CAL subroutines

Each routine is selected with `cal NAME`, where `NAME` is a predefined constant equal to the routine's 4-bit index. The full encoded byte is `E_`, where the low nibble is the constant.

| Source | Encoding | Effect |
|---|---|---|
| `cal RSTO` | `E0` | Clear the 7-segment display. |
| `cal SETR` | `E1` | Turn on binary LED indexed by `Y` (0–6). |
| `cal RSTR` | `E2` | Turn off binary LED indexed by `Y` (0–6). |
| `cal CMPL` | `E4` | `A` ← `~A` (one's complement). |
| `cal CHNG` | `E5` | Swap `{A,B,Y,Z}` with `{A',B',Y',Z'}`. |
| `cal SIFT` | `E6` | `A` ← `A >> 1`. `FLAG=1` if the original `A` was even. |
| `cal ENDS` | `E7` | Play the end-of-program tone. |
| `cal ERRS` | `E8` | Play the error tone. |
| `cal SHTS` | `E9` | Play a short beep. |
| `cal LONS` | `EA` | Play a longer beep. |
| `cal SUND` | `EB` | Play the tone whose pitch is `A` (valid 1..0xE). |
| `cal TIMR` | `EC` | Delay for `(A + 1) * 0.1` seconds. |
| `cal DSPR` | `ED` | Display the 7 binary LEDs from `mem[0x5E]` (low 4 bits) and `mem[0x5F]` (high 3 bits). |

`E3` is not assigned a name. Use `cal 3` if you really need to emit it.

The thirteen named routines above are reached through predefined constants. Both the uppercase canonical names (`RSTO`, `SETR`, ...) and their lowercase aliases (`rsto`, `setr`, ...) are accepted, since historical GMC-4 / SFMT listings mix the two cases freely.

The remaining two CAL routines — the decimal-arithmetic forms — are exposed as **standalone mnemonics** rather than `cal NAME` constants:

| Mnemonic | Encoding | Effect |
|---|---|---|
| `dem-` | `EE` | Decimal-adjusted `mem[0x50+Y] - A`; `Y--`. |
| `dem+` | `EF` | Decimal-adjusted `mem[0x50+Y] + A`; `Y--`; auto-adjust on overflow. |

For compatibility with a handful of manual listings that wrote them as CAL routines, `cal dem-` and `cal dem+` are also accepted and emit the same bytes.

### Predefined data-memory symbols

| Symbol | Address | Meaning |
|---|---|---|
| `data_base` | `0x50` | Base of data memory; the cell selected by `Y` is `data_base + Y`. |
| `data_5e` | `0x5E` | Low 4 bits of the pattern shown by `cal DSPR`. |
| `data_5f` | `0x5F` | High 3 bits of the pattern shown by `cal DSPR`. |

The `GLOBAL` memory zone covers program memory (`0x00`–`0x4F`); a separate `data_memory` zone covers `0x50`–`0x5F`. BespokeASM will refuse to emit program bytecode outside `GLOBAL`.

## FLAG and the JUMP idiom

The single-bit `FLAG` is set by most arithmetic, comparison, and I/O instructions. The convention is:

* `FLAG = 1` → "exceptional": no key pressed, overflow, borrow, not-equal, shifted-an-even-number.
* `FLAG = 0` → "normal": equality, no overflow, key was pressed.

`JUMP` branches when `FLAG = 1`. **Crucially, `JUMP` always forces `FLAG = 1` after executing**, whether or not the jump was taken. The canonical idiom for an unconditional branch is therefore two `JUMP`s back-to-back: the first may or may not be taken, but the second always is, because the first leaves `FLAG = 1`.

```asm
    cia 5         ; FLAG = 0 if A == 5, else FLAG = 1
    jump match    ; taken when A != 5
    jump match    ; unconditional - reached only when A == 5,
                  ; but FLAG=1 was forced by the prior JUMP
```

## Examples

* [`count-up.gmc4`](./count-up.gmc4) — counts `0..F` repeatedly on the 7-seg display with a delay; demonstrates `tia`, `ao`, `aia`, `cal TIMR`, and the two-`jump` unconditional-loop idiom.
* [`key-echo.gmc4`](./key-echo.gmc4) — polls the keypad and echoes the pressed key onto the display; demonstrates `ka`'s `FLAG` semantics and conditional `jump`.

## Compiling

Source files use the `.gmc4` extension. To get an annotated listing showing the per-instruction nibble layout:

```sh
bespokeasm compile -c gmc4-isa.yaml -p -t listing count-up.gmc4
```

Because the GMC-4 word is a single nibble, two consecutive nibbles share each byte of the binary (high nibble first); a final half-byte of program is padded with a trailing `0` nibble.
