#include <stdio.h>
#include "c2mips.h"

/* README ADR-004: n!/(k!(n-k)!) written by the user agrees with the builtin nCk for every
   n <= 12 (13! no longer fits in int, which is why the builtin does not use it). */
int fact(int n) {
    if (n <= 1)
        return 1;
    return n * fact(n - 1);
}

int comb(int n, int k) {
    return fact(n) / (fact(k) * fact(n - k));
}

int main(void) {
    int checked = 0, bad = 0, sum = 0;
    for (int n = 0; n <= 12; n = n + 1) {
        for (int k = 0; k <= n; k = k + 1) {
            if (comb(n, k) != nCk(n, k)) {
                printf("mismatch at n=%d k=%d\n", n, k);
                bad = bad + 1;
            }
            sum = sum + nCk(n, k);
            checked = checked + 1;
        }
    }
    printf("checked %d, mismatches %d, sum %d\n", checked, bad, sum);
    return bad != 0;
}
