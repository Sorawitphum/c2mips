#include <stdio.h>
#include "c2mips.h"

int zero(void) { return 0; }
int one(int a) { return a + 1; }
int sub(int a, int b) { return a - b; }
int mix(int a, int b, int c, int d) { int t = a * 1000 + b * 100; return t + c * 10 + d; }
int bump(int x) { x = x + 100; return x; }

int main(void) {
    int v = 5;
    printf("%d %d %d\n", zero(), one(41), sub(10, 3));
    printf("%d\n", mix(1, 2, 3, 4));
    printf("%d\n", mix(sub(9, 8), one(1), mix(0, 0, 0, 3), zero()));
    printf("%d %d\n", bump(v), v);
    printf("%d\n", sub(one(one(1)), 10) * -1);
    return sub(50, 8);
}
