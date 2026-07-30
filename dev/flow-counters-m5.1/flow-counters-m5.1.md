# flow-documentation-m5-1

## General Information

### ISA Overview

| ISA Attribute | Value |
|:--|:--|
| **ISA Name** | `flow-documentation-m5-1` |
| **Version** | 0.5.1 |
| **File Extension** | *.asm |

---

| Hardware Attribute | Value |
|:--|:--|
| **Address Size** | 8 bits |
| **Word Size** | 8 bits |
| **Default Origin Address** | 0 |

---

| Endianness Attribute | Value |
|:--|:--|
| **Multi-Word Endianness** | `little` |
| **Intra-Word Endianness** | `big` |

---

| String Handling Attribute | Value |
|:--|:--|
| **C-String Terminator** | 0 |
| **Embedded Strings Allowed** | Disabled |
| **String Byte Packing** | Disabled |

### Compatibility

**Minimum BespokeASM Version:** 0.8.0

## Operand Sets

### `value`

| Operand | Syntax | Value | Addressing Mode |
| :-- | :-- | :-- | :-- |
| `immediate` | `immediate` | numeric expression expressed as 8 bit value | Immediate |

# Flow Counters

See [Flow Counters](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#flow-counters) for the assembly-language syntax and general feature documentation.

## Data Stack Depth (`stack`)

Tracks routine-owned bytes on the data stack.

| Property | Value |
| --- | --- |
| Source | `flow_effects.stack` |
| Minimum Value | 0 |
| Maximum Value | 32 |
| Default Initial Value | 0 |
| Exit Policy | `balanced` |
| Coordinate Offsets | `positive` |
| Allow Zero Offset | Yes |
| Unknown Instructions | `error` |
| Invalidated By Writes To | `0xff` |
| Join Policy | `require-equal` |

### Entry Modes

| Mode | Initial Value | Exit Value | Description |
| --- | --- | --- | --- |
| `called` | 0 | 0 | A subroutine entered with a stack-saved return address. |

### Terminal Instructions

| Instruction | Reconciliation |
| --- | --- |
| `rts` | Before effect |

## Cycle Count (`cycles`)

Counts instruction execution cycles.

| Property | Value |
| --- | --- |
| Source | `flow_effects.cycles` |
| Minimum Value | 0 |
| Maximum Value | Not set |
| Default Initial Value | 0 |
| Exit Policy | `none` |
| Coordinate Offsets | `both` |
| Allow Zero Offset | Yes |
| Unknown Instructions | `error` |
| Invalidated By Writes To | Not set |
| Join Policy | `require-equal` |

### Terminal Instructions

| Instruction | Reconciliation |
| --- | --- |
| `rts` | After effect |

## Memory Writes (`writes`)

Counts writes to memory.

| Property | Value |
| --- | --- |
| Source | `flow_effects.writes` |
| Minimum Value | 0 |
| Maximum Value | Not set |
| Default Initial Value | 0 |
| Exit Policy | `none` |
| Coordinate Offsets | `both` |
| Allow Zero Offset | Yes |
| Unknown Instructions | `error` |
| Invalidated By Writes To | Not set |
| Join Policy | `require-equal` |

### Terminal Instructions

| Instruction | Reconciliation |
| --- | --- |
| `rts` | Before effect |

# Instructions

## Uncategorized

### `ADJUST`

*Documentation not provided.*

*Calling syntax:*

```asm
adjust immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | -ARG(0) physical effect. |
| Counter | cycles | +1 physical effect. |

---

### `CALL`

*Documentation not provided.*

*Calling syntax:*

```asm
call immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | +2 physical effect. |
| Counter | stack | The caller-visible net effect after return: +0. |
| Counter | cycles | +4 physical effect. |

---

### `CALL_NET_MINUS_ONE`

*Documentation not provided.*

*Calling syntax:*

```asm
call_net_minus_one immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | +2 physical effect. |
| Counter | stack | The caller-visible net effect after return: -1. |
| Counter | cycles | +4 physical effect. |

---

### `CALL_UNKNOWN`

*Documentation not provided.*

*Calling syntax:*

```asm
call_unknown immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | +2 physical effect. |
| Counter | cycles | +4 physical effect. |

---

### `DEPTH`

*Documentation not provided.*

*Calling syntax:*

```asm
depth immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +1 physical effect. |

---

### `IJMP`

*Documentation not provided.*

*Calling syntax:*

```asm
ijmp
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +2 physical effect. |

---

### `JMP`

*Documentation not provided.*

*Calling syntax:*

```asm
jmp immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +2 physical effect. |

---

### `JZ`

*Documentation not provided.*

*Calling syntax:*

```asm
jz immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +2 physical effect. |

---

### `NOP`

*Documentation not provided.*

*Calling syntax:*

```asm
nop
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +1 physical effect. |

---

### `OBSERVE`

*Documentation not provided.*

*Calling syntax:*

```asm
observe immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +1 physical effect. |

---

### `POP`

*Documentation not provided.*

*Calling syntax:*

```asm
pop
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | -1 physical effect. |
| Counter | cycles | +2 physical effect. |

---

### `PUSH`

*Documentation not provided.*

*Calling syntax:*

```asm
push
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | +1 physical effect. |
| Counter | cycles | +2 physical effect. |
| Counter | writes | +1 physical effect. |

---

### `REPLACE_STACK_ANCHOR` : Replace stack anchor

*Calling syntax:*

```asm
replace_stack_anchor
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | Unconditionally becomes indeterminate. |
| Counter | cycles | +2 physical effect. |

---

### `RTS`

*Documentation not provided.*

*Calling syntax:*

```asm
rts
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | -2 physical effect. |
| Counter | stack | This terminates the flow path and reconciles the counter before the instruction effect. |
| Counter | cycles | +3 physical effect. |
| Counter | cycles | This terminates the flow path and reconciles the counter after the instruction effect. |
| Counter | writes | This terminates the flow path and reconciles the counter before the instruction effect. |

---

### `STORE`

*Documentation not provided.*

*Calling syntax:*

```asm
store
```

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | cycles | +2 physical effect. |
| Counter | writes | +1 physical effect. |

---

### `WRITE_ADDR` : Write memory address

*Calling syntax:*

```asm
write_addr immediate
```

where

| Operand | Type | Value |
| :-- | :-- | :-- |
| `immediate` | numeric | numeric expression expressed as 8 bit value |

#### Modifies

| Type | Target | Description |
| --- | --- | --- |
| Counter | stack | Becomes indeterminate when zero-based write-target operand(s) 0 may address 0xff. |
| Counter | cycles | +2 physical effect. |
| Counter | writes | +1 physical effect. |

# Macros

## Uncategorized

### `PUSH_SEVEN`

*Calling syntax:*

```asm
PUSH_SEVEN
```

---

### `PUSH_THREE`

*Calling syntax:*

```asm
PUSH_THREE
```
