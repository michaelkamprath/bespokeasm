#require "compilation-control-test >= 0.2.0"

#define SYMBOL1 1
#define SYMBOL2 0
#define SYMBOL3

start:
    push a
#if SYMBOL1
    push i
#else
    push j
#endif

#if SYMBOL2
    pop i
#else
    pop j
#ifdef SYMBOL3      ; nested #ifdef
    mov a, 0
#else
    mov a, 1
#endif
#endif

#if SYMBOL1 == 2
    push a
#elif SYMBOL1 == 1
    push i
#else
    push j
#endif
