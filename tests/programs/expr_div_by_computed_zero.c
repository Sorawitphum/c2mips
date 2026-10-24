// no-gcc-oracle: division by zero is UB in C; c2mips panics (ADR-006)
#include <stdio.h>

int main(void) {
    printf("%d %d\n", 1, 7 / (3 - 3));
    return 0;
}
