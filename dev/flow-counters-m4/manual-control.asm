; M4: concurrent stack tracking plus overlapping cycle-count windows.
#define REQUIRED_WINDOWS 2
#assert REQUIRED_WINDOWS >= 2 red "M4 requires two overlapping windows"

routine:
#track stack mode=called
#track cycles as=outer init=0
.candidate := COORDINATE(stack, 3) ; caller parameter beyond the return address
push
lds OFFSET(.candidate)             ; emits sp+4 after the one-byte local push

#track cycles as=inner init=0
nop
#assert inner == 1
#set outer = COUNTER(outer) + 7

#suspend inner
nop
#resume inner = 1
nop

#endtrack inner exit=2
pop
#assert COUNTER(outer) == 15
#endtrack outer exit=15
rts
#endtrack stack
