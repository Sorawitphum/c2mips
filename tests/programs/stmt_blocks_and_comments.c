#include <stdio.h>

int main(void) {
    // line comment
    /* block
       comment */
    ;
    1 + 2;
    {
        { printf("%d\n", 6 / 3); }
        ;
    }
    return 0; /* trailing */
}
