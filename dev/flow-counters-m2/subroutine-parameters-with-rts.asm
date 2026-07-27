; M2 equivalent of a called routine whose RTS will perform a pre-effect
; terminal reconciliation in M3. The return address is at sp+1 and sp+2,
; but the counter tracks only stack movement owned by this routine.
is_prime32:
#track stack init=0 exit=0
.candidate := COORDINATE(stack, 3)    ; caller's uint32 candidate is at sp+3
.return_value := COORDINATE(stack, 7) ; caller's result slot is at sp+7

push4                               ; local uint32: counter 0 -> 4
lds OFFSET(.candidate)              ; candidate moved from sp+3 to sp+7
sts OFFSET(.return_value)           ; result slot moved from sp+7 to sp+11
pop4                                ; discard local: counter 4 -> 0
#endtrack stack                     ; reconcile routine-owned movement before RTS
rts                                 ; physical -2 return-address pull is outside the region
