; Both paths return, leaving the next public label unreachable in the open
; lexical region. The label intentionally produces the M5 entry warning.
#track stack mode=called
two_returns:
    jz .alternate
    rts
.alternate:
    rts

next_public_routine:
    nop
