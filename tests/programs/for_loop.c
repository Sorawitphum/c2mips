#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int total = 0;
    for (int i = 0; i < 10; i = i + 1) total = total + i;
    printf("%d\n", total);
    int i = 100;
    for (i = 0; i < 3; i = i + 1) { printf("%d\n", i); }
    printf("%d\n", i);
    for (; i < 5;) i = i + 1;
    printf("%d\n", i);
    int p = 0;
    for (int r = 1; r <= 3; r = r + 1)
        for (int c = 1; c <= 3; c = c + 1)
            p = p + r * c;
    printf("%d\n", p);
    int k = 0;
    for (;;) { k = k + 1; if (k == 7) { printf("%d\n", k); return k; } }
}
