#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int n = 10;
    int k = 3;
    int a = (n + k) * 2 - 7 / 2;
    printf("a = %d\n", a);
    printf("C(%d,%d) = %d\n", n, k, nCk(n, k));
    return 0;
}
