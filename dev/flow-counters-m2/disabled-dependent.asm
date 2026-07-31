function:
#track stack
push
.field := COORDINATE(stack, 1)
.byte OFFSET(.field)
pop
#endtrack stack
