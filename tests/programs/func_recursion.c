#include <stdio.h>
#include "c2mips.h"

int fact(int n) { if (n <= 1) return 1; return n * fact(n - 1); }
int fib(int n) { if (n < 2) return n; return fib(n - 1) + fib(n - 2); }
int is_odd(int n);
int is_even(int n) { if (n == 0) return 1; return is_odd(n - 1); }
int is_odd(int n) { if (n == 0) return 0; return is_even(n - 1); }
int sum_to(int n) { if (n == 0) return 0; return n + sum_to(n - 1); }

int main(void) {
    printf("%d %d\n", fact(10), fact(12));
    printf("%d %d\n", fib(10), fib(20));
    printf("%d %d %d\n", is_even(10), is_odd(7), is_even(7));
    printf("%d\n", sum_to(5000));
    return 0;
}
