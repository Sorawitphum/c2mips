#include <stdio.h>

int main(void) {
    int big = 2147483647;
    int one = 1;
    big = big + one;
    printf("%d\n", big);
    printf("%d\n", big - one);
    return 0;
}
