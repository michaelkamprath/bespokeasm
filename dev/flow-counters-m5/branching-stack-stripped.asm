; Hand-resolved twin proving that M5 analysis does not change emitted code.
is_nonzero:
    push
    jz .is_zero
    push
    depth 5
    pop
    pop
    rts
.is_zero:
    depth 4
    pop
    rts
