; Hand-stripped twin of cycle-counting.asm.
constant_time_branch:
    jz .alternate
    nop
    jmp .done

.alternate:
    nop
    nop
    nop

.done:
    rts
