#include <stdio.h>

int main(void) {
    printf("before\n");
    printf("%d\n", 1 / 0);
    printf("after\n");
    return 0;
}
