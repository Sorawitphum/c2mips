#include <stdio.h>

int main(void) {
    int total = 0;
    { int y = 5; total = total + y; }
    { int y; y = 7; total = total * y; }
    { int y = total; int z = y - 1; total = z; }
    printf("%d\n", total);
    return 0;
}
