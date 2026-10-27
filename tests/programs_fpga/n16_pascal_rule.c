#include "c2mips.h"

int main(void) {
    int bad = 0, count = 0;
    for (int n = 0; n <= 32; n = n + 1) {
        for (int k = 0; k <= n; k = k + 1) {
            if (nCk(n, k) + nCk(n, k + 1) != nCk(n + 1, k + 1))
                bad = bad + 1;
            count = count + 1;
        }
    }
    if (bad)
        return -bad;
    return count;
}
