#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("before\n");
    printf("%d\n", nCk(34, 16));
    return 0;
}
