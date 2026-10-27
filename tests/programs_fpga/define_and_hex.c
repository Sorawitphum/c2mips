#define BASE 0x10
#define TWICE BASE * 2
#define LIMIT 0x7FFFFFFF

int main(void) {
    return TWICE + 0xff - LIMIT / 0x40000000;
}
