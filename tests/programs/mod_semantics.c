#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("%d %d %d %d\n", 7 % 3, -7 % 3, 7 % -3, -7 % -3);
    printf("%d %d %d\n", 0 % 5, 2147483647 % 2, 1 + 7 % 4 * 2);
    int a = 17;
    int b = 5;
    printf("%d\n", (a / b) * b + a % b);
    printf("%d\n", a % b % 3);
    return 0;
}
