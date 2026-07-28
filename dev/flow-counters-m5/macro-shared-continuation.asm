; A seven-byte macro and two changing counters require the bytes and flow
; columns to continue. Their overflow shares one physical continuation row.
#track stack mode=called
#track writes
wide_macro_frame:
    push_seven                      ; seven pushes and seven memory writes
    pop
    pop
    pop
    pop
    pop
    pop
    pop
    rts
#endtrack writes
#endtrack stack
