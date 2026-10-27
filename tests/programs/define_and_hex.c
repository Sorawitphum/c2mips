#include <stdio.h>
#include "c2mips.h"

#define N 10
#define K 3
#define MASK 0xFF

int main(void) {
    printf("%d %d %d\n", nCk(N, K), 0x1F + MASK, 0X7fffffff);
    return N;
}
