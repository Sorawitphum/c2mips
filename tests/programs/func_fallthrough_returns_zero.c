// no-gcc-oracle: using the value of a function that falls off its end is UB in C
#include <stdio.h>
#include "c2mips.h"

int maybe(int x) {
    if (x > 0)
        return x;
}

int main(void) {
    printf("%d %d\n", maybe(5), maybe(-5));
    return 0;
}
