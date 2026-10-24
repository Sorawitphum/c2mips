// no-gcc-oracle: x % 0 is UB in C; c2mips panics (ADR-008)
#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int z = 0;
    printf("before\n");
    printf("%d\n", 5 % z);
    return 0;
}
