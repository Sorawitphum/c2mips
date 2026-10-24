#include <stdio.h>

int main(void) {
    int a, b = 2, c;
    a = 1;
    c = a + b;
    printf("%d %d %d\n", a, b, c);
    a = b = 5;
    printf("%d %d\n", a, b);
    printf("%d\n", c = c * 10);
    printf("%d\n", c);
    return 0;
}
