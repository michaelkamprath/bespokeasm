function:
#track stack
push
.field := COORDINATE(stack, 1)
pop
push
load [sp + .field]
pop
#endtrack stack
