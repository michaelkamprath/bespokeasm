# Named Memory Zones
## Overview
The general goal is to create the ability to define at compile time memory ranges that can be referred to by name. Once defined, the named memory space can be used in the following manners:

1. a directive can set the current address address as an offset within the named memory space.
2. a directive that indicates the subsequent code/data should be in the named memory space but leave it up to the compiler to set the exact address (usually just set the address in the order that the code is assembled). This would work across multiple disjoint references to the named memory zone.

Named memory zones are a compilation

## Requirements
### Named Memory Zones
A named memory zone is a contiguous address range in the allowable address space of a given ISA that has an alphanumeric string as an identifier. The following additional conditions apply:

* A named memory zone must be completely contained by the allowed memory space of the configured ISA.
* Multiple named memory zones may overlap with each other
* When byte code is assembled, multiple byte codes assigned to the same absolute memory address is a fatal error.
* Named memory zones are a compile time construct, and are intended to only be a means to manage memory ranges and byte code memory locations in assembly code. 
* Memory zones have a start and end absolute memory address. Byte code assigned to that memory zone with an absolute address outside of the memory zone's range will be an error.
* A memory zone's name cannot be also used for any label.

#### Creation

##### Global Memory Zone
By default, a memory zone named `GLOBAL` is defined to be the full range of memory addresses allowed by the instruction set configuration file. For example, if the ISA defines a 16-bit address type, then the `GLOBAL` memory zone will be addresses `0x0000` though `0xFFFF`. 

The `GLOBAL` memory zone can be redefined in the ISA configuration to be a subset of what is permitted by the memory address bit size.

##### In Code
A memory zone can be defined with the following directive

```asm
#create_memzone <memory zone name> <start address> <end address>
```

Where `<memory zone name>` is an alphanumeric string with no spaces which will serve as the memory zone name, `<start address>` is the absolute address of the start of the memory zone, and `<end address>` is the absolute address of the end of the memory zone. Both `<start address>` and `<end address>` must be defined with integer literals.

Any defined memory zone must be fully contained in the `GLOBAL` memory zone. 

##### ISA Configuration
A predefined memory zone can be defined in the instruction set configuration file. In the `predefined` section, a subsection named `memory_zones` can be defined. That second contains a list of dictionaries with the following keys:

| Option Key | Value Type | Description |
|:-:|:-:|:--|
|`name`| string | The name of the memory zone |
|`start`| integer | The start address of the memory zone. |
|`end`| integer | The end address of the memory zone. |

See the configuration file schema specification.

### Address Origin Setting

#### Memory Zone Scope
By default, code in any given source file is assembled into the `GLOBAL` memory zone scope. To set the current memory zone scope to something different, the following directive is used:

```asm
.memzone <memory zone name>
```

Note that the `GLOBAL` memory zone name can be used this directive. Subsequent assembly code lines will be compiled into the indicated memory zone scope until the end of the current assembly file or another directive that changes the memory zone scope. Addresses assigned to the byte code will be per the code ordering. 

Non-contiguous uses of a given memory zone scope will be compiled as if the assembly code in each use instance was concatenated together in the order processed by the assembler.

If a source file that is currently using a non-`GLOBAL` memory zone includes another source file, that included source file will be compiled into the `GLOBAL` memory zone scope per normal file processing as described above. When compilation returns to the original source file that included the additional source file, compilation will continue using the same memory zone scope that was active when the `#include` directive was processed. This means that source files must always declare any non-`GLOBAL` emory zone scope they wish to use, and such declarations only persist for the scope of that source file.

#### Relative Origin within a Memory Zone
A relative origin within a memory zone can be set with the `.org` directive:

```asm
.org <address offset value> "<memory zone name>"
```

Where `<address offset value>` is the positive offset from the start of the specific memory zone, and `<memory zone name>` is the name of the specified memory zone (which is optional, see below). The `<memory zone name>` value is denoted by quotes so as to offset it from the `<address offset value>` if that was set as an expression. So, if a memory zone named "variables" is defined to be the range of `0x2000` through `0x2FFF`, then:

```asm
.org 0x0100 "variables"
```

Would be the same as setting the current origin to `0x2100` in the `GLOBAL` scope. 

Not specifying a `<memory zone name>` will cause the `<address offset value>` to be interpreted as an absolute address. So:

```asm
.org $3400
```

Will set the current address to $3400. This absolute address interpretation is regardless of how the `GLOBAL` memory zone is defined.

When using `GLOBAL` as the `<memory zone name>` then `<address offset value>` will be interpreted as an offset form the start of the `GLOBAL` memory zone as it would with any other named memory zone. If the `GLOBAL` memory zone has not be redefined, the net effect is the same as using `.org` with an absolute address. However, if the start address of the `GLOBAL` memory zone has been redefined, then `<address offset value>` will be applied as an offset from the redefined start of `GLOBAL`. 


### Memory Zone Error Conditions
The following conditions will be considered an error:

* A defined memory zone not fully contained by the `GLOBAL` memory zone.
* A memory zone defined more than once.
* Byte code that get assigned to the same absolute memory address.
* Memory zone names that have spaces or non-alphanumeric characters. 