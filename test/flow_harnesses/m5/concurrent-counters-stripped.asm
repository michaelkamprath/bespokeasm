; Hand-resolved twin of concurrent-counters.asm.
write_optional_value:
    push
    store
    jz .one_write

    store
    observe 3
    pop
    rts

.one_write:
    observe 2
    pop
    rts
