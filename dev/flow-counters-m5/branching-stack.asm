; M5: the routine has a local stack value before it branches. Each path uses
; the same caller-parameter coordinate and independently restores the stack
; before returning through its own exit point.
#track stack mode=called
is_nonzero:
    .candidate := COORDINATE(stack, 3)
    push                            ; common one-byte local: candidate is sp+4
    jz .is_zero
    push                            ; path-only local: candidate is now sp+5
    depth .candidate        ; emits 5
    pop
    pop
    rts                             ; nonzero path exit
.is_zero:
    depth .candidate        ; emits 4
    pop
    rts                             ; zero path exit
#endtrack stack
