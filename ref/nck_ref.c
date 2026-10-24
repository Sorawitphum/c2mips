/* Reference implementation for differential testing on the host (gcc).
   Must match runtime/runtime.s bit-for-bit, including the error path. */
#include <stdio.h>
#include <stdlib.h>
#include "c2mips.h"

static unsigned gcd_u(unsigned a, unsigned b) {
    while (b != 0) { unsigned t = a % b; a = b; b = t; }
    return a;
}

int nCk(int n, int k) {
    if (n < 0 || k < 0 || k > n) return 0;
    if (n - k < k) k = n - k;
    unsigned base = (unsigned)(n - k), r = 1;
    for (unsigned i = 1; i <= (unsigned)k; i++) {
        unsigned num = base + i;
        unsigned g = gcd_u(r, i);
        r /= g;
        num /= (i / g);
        unsigned long long p = (unsigned long long)r * num;
        if (p > 2147483647ULL) {
            printf("runtime error: nCk overflow\n");
            fflush(stdout);
            exit(70);
        }
        r = (unsigned)p;
    }
    return (int)r;
}
