#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("%d\n", 1 + nCk(6, 2) * 2);
    printf("%d\n", nCk(6, 2) - nCk(6, 4));
    printf("%d\n", -nCk(7, 3));
    printf("%d\n", nCk(10, 5) / nCk(5, 2));
    printf("%d\n", nCk(nCk(5, 2), nCk(3, 1)));
    return 0;
}
