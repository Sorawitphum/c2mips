#include <stdio.h>
#include "c2mips.h"

/* factorial, recursive and iterative; 12! is the largest that fits in int */
int fact(int n) {
    if (n <= 1)
        return 1;
    return n * fact(n - 1);
}

int fact_loop(int n) {
    int r = 1;
    for (int i = 2; i <= n; i = i + 1)
        r = r * i;
    return r;
}

int main(void) {
    for (int n = 0; n <= 12; n = n + 1)
        printf("%d! = %d %d\n", n, fact(n), fact_loop(n));
    return 0;
}
