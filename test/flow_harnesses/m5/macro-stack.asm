; One source-level macro expands to three stack-changing instructions. The
; listing reports their aggregate effect on the macro invocation row.
#track stack mode=called
macro_stack_frame:
    push_three                      ; expands to push, push, push
    pop
    pop
    pop
    rts
#endtrack stack
