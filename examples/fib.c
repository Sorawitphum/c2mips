#include <stdio.h>
#include "c2mips.h"

/* Fibonacci, recursive and iterative */
int fib(int n) {
    if (n < 2)
        return n;
    return fib(n - 1) + fib(n - 2);
}

int fib_loop(int n) {
    int a = 0, b = 1;
    while (n > 0) {
        int t = a + b;
        a = b;
        b = t;
        n = n - 1;
    }
    return a;
}

int main(void) {
    for (int n = 0; n <= 20; n = n + 1)
        printf("fib(%d) = %d %d\n", n, fib(n), fib_loop(n));
    return 0;
}
