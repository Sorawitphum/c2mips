#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int a = 1;
    int b = 2;
    printf("%d %d %d %d %d %d\n", a < b, a <= b, a > b, a >= b, a == b, a != b);
    printf("%d %d %d %d %d %d\n", b < a, b <= a, b > a, b >= a, b == a, b != a);
    printf("%d %d %d %d %d %d\n", a < a, a <= a, a > a, a >= a, a == a, a != a);
    int lo = -2147483647 - 1;
    int hi = 2147483647;
    printf("%d %d %d %d\n", lo < hi, hi < lo, lo < 0, -1 < 1);
    printf("%d\n", 1 < 2 == 1);
    printf("%d\n", 3 > 2 > 1);
    return 0;
}
