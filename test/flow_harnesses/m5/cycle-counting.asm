; Both branch paths take exactly five cycles before the common exit.
#track cycles
constant_time_branch:
    jz .alternate           ; 2 cycles: both paths total 2
    nop                     ; 1 cycle: fall-through path totals 3
    jmp .done               ; 2 cycles: fall-through path totals 5

.alternate:
    nop                     ; alternate path totals 3
    nop                     ; alternate path totals 4
    nop                     ; alternate path totals 5

.done:
    #assert cycles == 5
    #endtrack cycles exit=5
    rts
