#track stack
routine:
    push
.old_top := COORDINATE(stack, 1)
    reset_stack
                                ; reset_stack expands to a write to watched
                                ; address 255, so stack becomes indeterminate
#resume stack = 0               ; explicitly anchor the new empty stack
#assert stack == 0
#endtrack stack
