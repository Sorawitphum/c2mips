#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int n = 5;
    if (n > 3) printf("big\n"); else printf("small\n");
    if (n < 3) printf("A\n"); else if (n < 6) printf("B\n"); else printf("C\n");
    if (n) { int n = 1; printf("%d\n", n); }
    printf("%d\n", n);
    if (0) printf("never\n");
    if (1) if (0) printf("x\n"); else printf("dangling\n");
    if (n == 5 && n != 4) { n = n * 2; }
    printf("%d\n", n);
    if (!(n % 2)) printf("even\n"); else printf("odd\n");
    return n > 9;
}
