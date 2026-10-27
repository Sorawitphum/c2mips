#define LED (*(volatile int*)0xF0000002)
int main(void) {
    LED = 1;
    return 0;
}
