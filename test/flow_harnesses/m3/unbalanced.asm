is_prime32:
#track stack mode=called
.candidate := COORDINATE(stack, 3)
push4
lds .candidate
addsp 3
rts
#endtrack stack
