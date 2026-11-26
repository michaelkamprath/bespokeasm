# MOS 6502 and WDC W65C02S Assembly

These configurations for **BespokeASM** create assemblers for the MOS 6502 and its CMOS descendant, the WDC W65C02S. Source is written in the conventional 6502 style, so most code written for other 6502 assemblers assembles with little or no change. Every opcode in both configurations produces the same bytes as [ca65](https://cc65.github.io/doc/ca65.html) 2.18.

| Configuration | CPU | File Extension | Opcodes |
|:--|:--|:-:|:-:|
| [`mos6502.yaml`](./mos6502.yaml) | NMOS MOS 6502 | `.a65` | 151 |
| [`w65c02.yaml`](./w65c02.yaml) | WDC W65C02S | `.a65c` | 212 |

The W65C02S configuration is a superset of the 6502 one: it adds `bra`, `phx`, `phy`, `plx`, `ply`, `stz`, `trb`, `tsb`, the bit instructions `rmb0`–`rmb7`, `smb0`–`smb7`, `bbr0`–`bbr7` and `bbs0`–`bbs7`, `wai` and `stp`, and the `(address)` and `jmp (address,x)` addressing modes. 6502 code assembles to the same bytes with either configuration. The two use different file extensions so that both editor extensions can be installed at once.

## Instruction Set
The instruction sets are documented in these references:

* [6502 Instruction Set](https://www.masswerk.at/6502/6502_instruction_set.html) - Every NMOS opcode with its addressing modes, flags and cycle counts.
* [6502 Reference](https://6502.org/users/obelisk/6502/reference.html) and [65C02 Reference](https://6502.org/users/obelisk/65c02/reference.html) - Descriptions of each instruction.
* [65C02 Opcodes](https://www.6502.org/tutorials/65c02opcodes.html) - What the 65C02 adds to and changes from the 6502, including cycle counts.
* [W65C02S Datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c02s.pdf) - The chip's manufacturer documentation.

Every instruction is documented in the configuration files, with its flags and, for each addressing mode, its cycle count. Run `bespokeasm docs -c w65c02.yaml` to generate the full instruction reference, and the generated editor extensions show the same documentation on hover.

### Addressing Modes

| Addressing Mode | Syntax | Example |
|:--|:--|:--|
| Implied | | `inx` |
| Accumulator | `a`, or nothing | `asl a`, `asl` |
| Immediate | `#value` | `lda #$10`, `lda #<message` |
| Zero Page | `address` | `lda $10` |
| Zero Page,X and Zero Page,Y | `address,x`, `address,y` | `lda $10,x`, `ldx $10,y` |
| Absolute | `address` | `lda $1234` |
| Absolute,X and Absolute,Y | `address,x`, `address,y` | `lda $1234,x` |
| Indirect | `(address)` | `jmp (vector)` |
| Indexed Indirect | `(address,x)` | `lda ($20,x)` |
| Indirect Indexed | `(address),y` | `lda ($20),y` |
| Relative | `label` | `bne loop` |
| Zero Page Indirect (W65C02S) | `(address)` | `lda ($20)` |
| Absolute Indexed Indirect (W65C02S) | `(address,x)` | `jmp (table,x)` |
| Zero Page, Relative (W65C02S) | `address, label` | `bbr7 flags, wait` |

### Syntax Notes
The general syntax of **BespokeASM** is explained in [its wiki](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax). These are the conventions specific to these configurations:

* **Zero page is chosen automatically.** Instructions that have both a zero-page and an absolute form use the shorter zero-page form whenever the address is in page zero (`$0000`–`$00FF`), including labels defined later in the source. ca65 uses the absolute form for those forward references, so code that refers to zero-page variables before defining them can assemble shorter with **BespokeASM**. Instructions that only have a zero-page form, such as `stx address,y` and the W65C02S bit instructions, report an error for an address outside page zero.
* **`<` and `>`** take the low and high byte of the value that follows: `lda #<message` and `lda #>message`. As in ca65, they apply to the next term, so `<label+1` is `(<label)+1`. Write `<(label+1)` for the low byte of the sum.
* **`*`** is the address of the current instruction, so `bne *` branches to itself.
* **The accumulator** may be written or left out: `asl a` and `asl` are the same. On the W65C02S, so are `inc a` and `inc`, and `dec a` and `dec`. The `ina` and `dea` spellings some assemblers accept are not supported.
* **The bit instructions** take the bit number in the mnemonic, as in ca65 and WDC's documentation: `smb3 flags`, `bbr7 flags, label`.
* **Registers** `a`, `x` and `y` are reserved words. The stack pointer `s` and status register `p` are documented but not reserved, so they can be used as label names.
* **Directives:** `.word` and `.addr` are the same as `.2byte`, `.res` the same as `.fill`, and `.text` the same as `.byte`. `.res 4` reserves four zero bytes, and `.res 4, $FF` fills them with `$FF`.
* **Memory zones:** `ZERO_PAGE` (`$0000`–`$00FF`) and `STACK` (`$0100`–`$01FF`) are predefined. Memory zones for a particular computer's RAM, ROM and I/O belong in that computer's source, not in these configurations.

Some features of other 6502 assemblers have different spellings in **BespokeASM**, or are not supported: macros (`.macro`), anonymous labels (`:+`, `:-`), labels without a colon, `*=` for the origin (use `.org`), segments, and the `z:` and `a:` address-size prefixes.

## Flow Counters
Both configurations support **BespokeASM**'s assembly-time [flow counters](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#flow-counters). They are optional and never change the generated bytes.

* `stack` tracks the bytes a region has pushed on the page-one stack. Pushes add one and pulls subtract one; `jsr` and `rts` move the 2-byte return address, and `rti` removes the status byte and return address. `txs` replaces the stack pointer, so it makes the counter indeterminate. Entry modes `called`, `interrupt` and `jumped` describe how a region is entered. The stack pointer points at the next free byte, so `COORDINATE(stack, N)` names the byte at `$0100 + S + N`.
* `cycles` counts clock cycles from each instruction's documented cycle count. It doesn't count the extra cycle for crossing a page, or on the W65C02S for `adc` and `sbc` in decimal mode. A conditional branch takes one more cycle when taken than when not, which **BespokeASM**'s flow analysis can't follow yet, so track `cycles` over straight-line code only.

```asm
SOURCE = $0300
DEST   = $0301
#track stack mode=called
#track cycles
copy:   pha                 ; 3 cycles, 1 byte pushed
        lda SOURCE          ; 4
        sta DEST            ; 4
        pla                 ; 4, back to 0 bytes pushed
#endtrack cycles exit=15
        rts                 ; checks the stack is back where it started
```

## Compiling Code
To compile code, use the configuration for your CPU, `mos6502.yaml` for `.a65` files or `w65c02.yaml` for `.a65c` files. For a computer with a 32 KB ROM at `$8000`–`$FFFF`, such as an AT28C256 EEPROM, a typical compilation command will look like:

```sh
bespokeasm compile -c w65c02.yaml -s 0x8000 -p my_code.a65c
```

Where:

* `-c w65c02.yaml` : The path to the W65C02S configuration file in this directory.
* `-s 0x8000` : Starts the binary image at address `$8000`, so the file holds exactly the ROM's contents. Without it the image starts at address 0. Add `-f 0xFF` to fill unused space with `$FF`, an erased EEPROM's value, instead of zeros.
* `-p` : Prints a listing of the compiled code.
* `my_code.a65c` : The assembly code to compile.

### Syntax Highlighting
**BespokeASM** can generate syntax highlighting extensions for several popular text editors from either configuration. [See the documentation](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions) for how to install and use the language extensions.
