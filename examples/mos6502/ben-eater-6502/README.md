# Ben Eater 6502 Computer Examples
These are example programs for [Ben Eater's 6502 breadboard computer](https://eater.net/6502), written for **BespokeASM** with the [W65C02S configuration](../w65c02.yaml). They are original programs written in the platform's usual style. They use W65C02S instructions such as `stz` and `bra`, so they need `w65c02.yaml` rather than `mos6502.yaml`. The [parent directory's README](../README.md) describes the configuration and its syntax.

## Hardware
The programs assume the computer as built in the video series:

| Address | Device | Use in these programs |
|:--|:--|:--|
| `$0000`–`$3FFF` | 62256 SRAM, 16 KB of it | Zero-page variables and the stack |
| `$6000`–`$600F` | W65C22 VIA | Port B drives eight LEDs or the LCD's data bus. Port A drives the LCD's `E`, `RW` and `RS` lines on bits 7, 6 and 5. CA1 takes a button. |
| `$8000`–`$FFFF` | 28C256 EEPROM, 32 KB | The program and the reset and interrupt vectors |

The LCD is an HD44780 module in 8-bit mode.

## Files

| File | Description |
|:--|:--|
| [`ben-eater.a65c`](./ben-eater.a65c) | The memory map and the VIA and LCD constants. Every program includes it. |
| [`lcd.a65c`](./lcd.a65c) | LCD routines: set up, wait while busy, send an instruction, write a character, print a string. |
| [`blink.a65c`](./blink.a65c) | Bounces one lit LED back and forth across the LEDs on port B. |
| [`hello-lcd.a65c`](./hello-lcd.a65c) | Prints two lines of text on the LCD, through a zero-page pointer and `(address),y`. |
| [`counter-irq.a65c`](./counter-irq.a65c) | Counts presses of a button on the VIA's CA1 input with an interrupt handler, and prints the count in decimal. |

The include files use the `.a65c` extension, like the programs, so editor extensions generated from `w65c02.yaml` highlight them too. A program includes `ben-eater.a65c` at the top and `lcd.a65c` after its own code, at the place in ROM where the LCD routines should go.

## Building
Each program builds a 32 KB image for the EEPROM, with the reset and interrupt vectors in its last six bytes. From this directory:

```sh
bespokeasm compile -c ../w65c02.yaml -s 0x8000 blink.a65c
```

Where:

* `-c ../w65c02.yaml` : The W65C02S configuration file.
* `-s 0x8000` : Starts the image at the EEPROM's first address, so the file holds exactly the EEPROM's contents.
* `blink.a65c` : The program to build. Add `-p` to print a listing.

Each image is identical to the one ca65 and ld65 build from the same program. Write it to the EEPROM with any programmer that accepts a raw binary file.

## Notes
* **Layout.** The programs place their code with `.org $8000` and the vectors with `.org $FFFA`, as 6502 source usually does. `ben-eater.a65c` also defines `RAM` and `ROM` memory zones, for programs that would rather place code and data by zone with `.memzone`.
* **Zero-page variables can come last.** `counter-irq.a65c` declares its variables at the end of the file, after the code that uses them. **BespokeASM** still gives every instruction that refers to them the shorter zero-page form.
* **Button bounce.** `counter-irq.a65c` doesn't debounce the button, so one press can count more than once.
