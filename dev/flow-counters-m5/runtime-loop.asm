; A runtime-length loop is honest about the indeterminate span.
#track stack mode=called
runtime_length:
    #suspend stack
.loop:
    push
    jz .loop
    #resume stack = 0
    rts
#endtrack stack
