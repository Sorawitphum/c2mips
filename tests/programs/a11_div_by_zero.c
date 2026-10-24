// no-gcc-oracle: division by zero is UB in C; c2mips panics (ADR-006)
#include <stdio.h>

int main(void) {
    printf("before\n");
    printf("%d\n", 1 / 0);
    printf("after\n");
    return 0;
}
