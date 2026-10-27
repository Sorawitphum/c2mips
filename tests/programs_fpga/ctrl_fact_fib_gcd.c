#include "c2mips.h"

int fact(int n) {
    if (n <= 1)
        return 1;
    return n * fact(n - 1);
}

int fib(int n) {
    int a = 0, b = 1;
    while (n > 0) {
        int t = a + b;
        a = b;
        b = t;
        n = n - 1;
    }
    return a;
}

int gcd(int a, int b) {
    if (b == 0)
        return a;
    return gcd(b, a % b);
}

int main(void) {
    return fact(10) + fib(20) + gcd(1071, 462);
}
