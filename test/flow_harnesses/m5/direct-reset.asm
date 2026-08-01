; An instruction may replace a counter's physical anchor without writing a
; memory-mapped address. Its flow_invalidates metadata makes every active
; stack instance indeterminate, including when reached through this macro.
#track stack
routine:
    push
    .old_top := COORDINATE(stack, 1)
    reset_stack_direct              ; stack=1 -> ?
#resume stack = 0                   ; explicitly anchor the replacement stack
#assert stack == 0
#endtrack stack
