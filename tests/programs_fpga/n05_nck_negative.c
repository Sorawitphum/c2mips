#include "c2mips.h"

int main(void) {
    return nCk(-1, 0) + nCk(5, -1) + nCk(-2147483647 - 1, 0);
}
