#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("%d\n", nCk(-1, 0));
    printf("%d\n", nCk(5, -1));
    printf("%d\n", nCk(-2147483647 - 1, 0));
    return 0;
}
