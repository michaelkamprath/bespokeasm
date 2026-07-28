; Stack depth and completed writes are independent counters over one routine.
; The initial push changes both counters on the same instruction. Both exits
; balance the stack; writes intentionally ends at a different value on each
; path and has no equality-based exit contract.
#track stack mode=called
#track writes
write_optional_value:
    push
    store
    jz .one_write

    store
    observe COUNTER(writes) ; emits 3
    pop
    rts

.one_write:
    observe COUNTER(writes) ; emits 2
    pop
    rts
#endtrack writes
#endtrack stack
