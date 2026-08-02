; One return path leaks a local stack value and must fail at that return.
#track stack mode=called
leaked_push:
    jz .leak
    rts
.leak:
    push
    rts
#endtrack stack
