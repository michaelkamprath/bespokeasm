; An otherwise unreachable externally callable entry needs an explicit value.
#track stack mode=called
    jmp main

#entry stack value=0
alternate_entry:
    rts

main:
    rts
#endtrack stack
