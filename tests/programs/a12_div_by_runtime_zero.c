// no-gcc-oracle: division by zero is UB in C; c2mips panics (ADR-006)
#include <stdio.h>

int main(void) {
    int x = 7;
    int y = 0;
    printf("%d %d\n", 1, x / y);
    return 0;
}
