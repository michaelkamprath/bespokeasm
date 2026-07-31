; Straight-line model of the caller-owned stack slots documented by is_prime32:
;   sp+3 : uint32 candidate
;   sp+7 : return-value placeholder
is_prime32:
#track stack init=0 exit=0        ; track stack movement relative to entry SP
.candidate := COORDINATE(stack, 3)    ; caller's uint32 candidate is at sp+3
.return_value := COORDINATE(stack, 7) ; caller's result slot is at sp+7

lds .candidate    ; like `lds 3`: load from caller's candidate
sts .return_value ; like `sts 7`: store into caller's result slot
#endtrack stack
