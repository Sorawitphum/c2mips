#include <stdio.h>

int main(void) {
    int x = 1;
    {
        int x = 2;
        printf("%d\n", x);
        {
            int x = 3;
            printf("%d\n", x);
        }
        printf("%d\n", x);
    }
    printf("%d\n", x);
    {
        x = x + 40;
    }
    printf("%d\n", x);
    return x;
}
