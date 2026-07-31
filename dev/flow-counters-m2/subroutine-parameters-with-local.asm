; The access expressions are unchanged after adding a 4-byte local stack value.
is_prime32:
#track stack init=0 exit=0          ; track stack movement relative to entry SP
.candidate := COORDINATE(stack, 3)    ; caller's uint32 candidate is at sp+3
.return_value := COORDINATE(stack, 7) ; caller's result slot is at sp+7

push4                               ; like the 4-byte divisor pushed at primes line 58
lds .candidate              ; unchanged source; now equivalent to `lds 7`
sts .return_value           ; unchanged source; now equivalent to `sts 11`
pop4
#endtrack stack
