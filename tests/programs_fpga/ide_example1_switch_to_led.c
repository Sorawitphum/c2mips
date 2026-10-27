#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    while (1) {
        int sw = SWITCH;
        int result = sw + 1;
        LED = result;
        SEG7 = result;
    }
}
