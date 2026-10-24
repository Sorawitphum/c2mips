#include <stdio.h>

int main(void) {
    int a, b;
    scanf("%d", &a);
    scanf("%d", &b);
    printf("%d %d %d\n", a + b, a * b, a / b);
    int i = 0, sum = 0, n;
    scanf("%d", &n);
    while (i < n) {
        int v;
        scanf("%d", &v);
        sum = sum + v;
        i = i + 1;
    }
    printf("sum %d\n", sum);
    return a - b;
}
