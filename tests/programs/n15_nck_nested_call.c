#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("%d\n", nCk(nCk(4, 2), 2));
    return 0;
}
