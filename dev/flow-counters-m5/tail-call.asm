; The frame is balanced and closed before the tail jump.
#track stack mode=called
tail_caller:
    push
    pop
    #endtrack stack exit=0
    jmp tail_callee

tail_callee:
    rts
