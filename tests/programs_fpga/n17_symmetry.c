#include "c2mips.h"

int main(void) {
    int bad = 0, count = 0;
    for (int n = 0; n <= 33; n = n + 1) {
        for (int k = -1; k <= n + 1; k = k + 1) {
            if (nCk(n, k) != nCk(n, n - k))
                bad = bad + 1;
            count = count + 1;
        }
    }
    if (bad)
        return -bad;
    return count;
}
