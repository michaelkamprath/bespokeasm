timing:
#track cycles
.start := COORDINATE(cycles, 0)
nop
nop
.byte OFFSET(.start)
#endtrack cycles
