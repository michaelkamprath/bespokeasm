#create_memzone zone1 $200 $2FF

    push 1          ; line 0 - label scope should be file
label1:             ; line 1 - should be a new local scope
    push 2          ; line 2 - label scope should be local
    push 3          ; line 3 - label scope should be local
label2:             ; line 4 - should be a new local scope
    push 4          ; line 5 - label scope should be local

.org $100           ; line 6 - should reset label scope to file
    push 5          ; line 7 - label scope should be file

label3:             ; line 8 - should be a new local scope
    push 6          ; line 9 - should be a third local scope

.memzone zone1      ; line 10 - should reset label scope to file

    push 7          ; line 11 - should be file label scope
