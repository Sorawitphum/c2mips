#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int x = 4;
    if (x % 2 == 0) {
        return 20;
    } else {
        return 21;
    }
}
