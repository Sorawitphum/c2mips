#include <stdio.h>

int main(void) {
    int m = -2147483647 - 1;
    int d = -1;
    int p = 7;
    int q = -2;
    printf("%d\n", p / q);
    printf("%d\n", -p / 2);
    printf("%d\n", p / d);
    printf("%d\n", m * d);
    return 0;
}
