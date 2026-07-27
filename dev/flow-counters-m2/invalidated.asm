function:
#track stack
push
.field := COORDINATE(stack, 1)
pop
push
load [sp + OFFSET(.field)]
pop
#endtrack stack
