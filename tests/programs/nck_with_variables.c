#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int n = 10;
    int k = 3;
    printf("C(%d,%d) = %d\n", n, k, nCk(n, k));
    int r = nCk(n, k) + nCk(n, k + 1);
    printf("%d %d\n", r, nCk(n + 1, k + 1));
    k = nCk(6, 3) / nCk(4, 1) - 1;
    return k;
}
