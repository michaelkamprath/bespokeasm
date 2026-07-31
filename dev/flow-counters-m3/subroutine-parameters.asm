; Minimal 64x4-style called routine. The return address occupies sp+1/sp+2,
; so caller-owned values begin at sp+3 while routine-owned movement starts at 0.
is_prime32:
#track stack mode=called
.candidate := COORDINATE(stack, 3)
.return_value := COORDINATE(stack, 7)

push4
lds .candidate              ; emits 7 after the four-byte local push
sts .return_value           ; emits 11 after the local push
addsp 4                             ; operand-dependent teardown: stack 4 -> 0
rts                                 ; checks 0 == 0 before its physical -2 effect
#endtrack stack                     ; lexical-only delimiter after the terminal
