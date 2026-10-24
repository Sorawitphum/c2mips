#include <stdio.h>
#include "c2mips.h"

int twice(int x);

int main(void) {
    printf("%d\n", twice(21));
    return 0;
}

int twice(int x) { return x * 2; }
