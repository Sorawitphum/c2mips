// no-gcc-oracle: INT_MIN % -1 traps under gcc on x86; c2mips gives 0 (ADR-008)
#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int m = -2147483647 - 1;
    int d = -1;
    printf("%d %d\n", m % d, 7 % d);
    return 0;
}
