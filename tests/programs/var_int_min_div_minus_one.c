// no-gcc-oracle: INT_MIN / -1 traps under gcc on x86; c2mips gives -x
#include <stdio.h>

int main(void) {
    int m = -2147483647 - 1;
    int d = -1;
    printf("%d\n", m / d);
    return 0;
}
