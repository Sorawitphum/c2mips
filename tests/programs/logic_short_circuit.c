#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int x = 0;
    int y = 0;
    printf("%d %d %d %d\n", 5 && 7, 0 && 1, 0 || -3, 0 || 0);
    printf("%d %d %d\n", !0, !5, !!7);
    x = (y = 0) && (y = 5);
    printf("%d %d\n", x, y);
    x = (y = 3) || (y = 9);
    printf("%d %d\n", x, y);
    printf("%d\n", 0 && nCk(34, 16));
    printf("%d\n", 1 || nCk(34, 16));
    printf("%d\n", 1 && 2 || 0 && 3);
    printf("%d\n", !(1 < 2) || 4 == 4);
    return 0;
}
