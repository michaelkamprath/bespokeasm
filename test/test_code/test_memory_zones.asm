#create_memzone variables $3000 0x47FF

.memzone predefined_zone
start:
    push $32

.memzone variables
    .byte 0
    .byte 42

.memzone GLOBAL
continue:
    pop a
