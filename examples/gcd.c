#include <stdio.h>
#include "c2mips.h"

/* Euclid's algorithm with %, recursive and iterative */
int gcd(int a, int b) {
    if (b == 0)
        return a;
    return gcd(b, a % b);
}

int gcd_loop(int a, int b) {
    while (b != 0) {
        int t = a % b;
        a = b;
        b = t;
    }
    return a;
}

int show(int a, int b) {
    printf("gcd(%d, %d) = %d %d\n", a, b, gcd(a, b), gcd_loop(a, b));
    return 0;
}

int main(void) {
    show(1071, 462);
    show(462, 1071);
    show(17, 5);
    show(0, 9);
    show(9, 0);
    show(2147483647, 2147483646);
    show(1836311903, 1134903170);
    show(65536, 4096);
    return 0;
}
