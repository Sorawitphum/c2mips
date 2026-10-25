#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int i = 1;
    int sum = 0;
    while (i <= 100) { sum = sum + i; i = i + 1; }
    printf("%d\n", sum);
    while (0) printf("never\n");
    int n = 3;
    while (n) { printf("%d\n", n); n = n - 1; }
    int a = 1071;
    int b = 462;
    while (b != 0) { int t = a % b; a = b; b = t; }
    printf("%d\n", a);
    return 0;
}
