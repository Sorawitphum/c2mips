# ADR-010: `#define` แบบง่าย + MMIO `*(volatile int*)CONST`

> สำเนาจาก Spec.md §7 — Spec เป็นต้นฉบับ

**Status:** Accepted — ผู้ใช้อนุมัติค่าเริ่มต้นของ Q1–Q5 (2026-10-28) · **Date:** 2026-10-28

**Context:** โปรแกรมตัวอย่างของ FPGA Studio (ADR-009) เขียน I/O แบบนี้ ซึ่ง MiniC ปัจจุบันปฏิเสธทั้งหมด (`#define` → `E031`, `0x...` → `E001`, `volatile` / `*` / cast → `E030`):

```c
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
```

กฎเหล็กของ Spec §4 ยังอยู่: **ทุกโปรแกรมที่ c2mips รับต้องเป็น C99 ที่ gcc คอมไพล์ได้** — ส่วนเพิ่มนี้จึงเป็นชุดย่อยของ C เท่านั้น

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: preprocessor เต็ม (เรียก `cpp` ภายนอก) | รองรับทุกอย่าง | ต้องมี gcc/cpp ตอนคอมไพล์ (ผิด NFR-7), ตำแหน่ง error เพี้ยน |
| **B: `#define` แบบ object-like ใน lexer + MMIO รูปเดียว** | เล็ก, ตำแหน่ง error ชี้ถูก, ไม่ต้องมีเครื่องมือภายนอก | ไม่มี macro มี argument / `#if` |
| C: builtin `LED`/`SWITCH`/`SEG7` ในคอมไพเลอร์ | ง่ายที่สุด | gcc คอมไพล์ไม่ได้ถ้าไม่มี header; ไม่ใช่โค้ดแบบที่ IDE ให้มา |

**Decision:** B — ใช้ได้ทั้งสอง target แต่ MMIO มีความหมายจริงเฉพาะ `fpga`

**1. `#define`** (แทนที่ระดับ token ใน lexer)
- รับเฉพาะ `#define NAME replacement` แบบ object-like: replacement คือ token ที่เหลือทั้งบรรทัด (ว่างได้); ไม่มี line continuation `\`
- **ไม่รับ:** macro มี argument (`#define F(x) ...`), `#undef`, `#if`/`#ifdef`/…, `#` / `##` → `E031` เหมือนเดิม
- นิยามซ้ำด้วยค่า **เดียวกัน** (token เหมือนกัน) = ได้ (เหมือน C); ค่าต่างกัน = error `E033`
- macro ที่อ้างถึงตัวเอง ตรงหรืออ้อม (`A → B → A`) = error `E033` (เข้มกว่า C ซึ่งแค่ไม่ขยายซ้ำ — โปรแกรมที่ผ่านยังเป็น C ที่ถูกต้อง)
- ชื่อ macro เป็น keyword ไม่ได้ (`E033`); ใช้ก่อน `#define` ไม่ถูกแทน (เหมือน C)
- error ที่เกิดจาก token ที่มาจาก macro: รายงาน **ตำแหน่งที่ใช้ macro** และต่อท้ายข้อความว่า `(from #define NAME at line N)`
- `#include "nexys_a7.h"` → ข้ามเหมือน `#include` อื่นที่รับไว้แล้ว

**2. Hex literal** — `0x...` / `0X...` ใช้ได้ทุก target (Q1) · ค่าที่เกิน `INT_MAX` ใช้ได้ **เฉพาะ** ในรูป MMIO และ **ต้องเขียนเป็น hex** (บิตแพตเทิร์นของที่อยู่ 32 บิต, ≤ `0xFFFFFFFF`) นอกนั้นเป็น `E003` · ตัวเลขฐานสิบที่เกิน `INT_MAX` ยังเป็น `E003` ใน lexer เหมือนเดิมทุกตัวอักษร (พฤติกรรมเดิมไม่เปลี่ยน) · octal (`010`) ยังเป็น `E001` เหมือนเดิม

**3. MMIO** — รับ **เฉพาะ** รูป `*(volatile int*)INTCONST` และ `*(volatile int *)INTCONST` (เว้นวรรคได้, อยู่ในวงเล็บได้อย่างที่ macro ข้างบนทำ)
- **rvalue:** `int s = SWITCH;` → `lw` · **lvalue:** `LED = expr;` → `sw` (ค่าของ assignment คือค่าที่เขียน เหมือน assignment ปกติ)
- address ต้องหารด้วย 4 ลงตัว ไม่งั้น `E034`
- pointer ทั่วไป (`int *p`, `&x`, cast อื่น, `volatile` นอกรูปนี้) → `E030` เหมือนเดิม
- codegen: `lui $t2, hi16` (+ `ori $t2, $t2, lo16` ถ้า lo16 ≠ 0) แล้ว `lw $t0, 0($t2)` / `sw $t0, 0($t2)` — `$t2` เป็น scratch อยู่แล้วตาม Spec §6.1
- **`volatile`:** ทุกการอ้างอิงต้องเกิด load/store จริงตามลำดับในโค้ด — fold ห้ามตัด ห้ามรวม ห้ามย้ายลำดับ (`SWITCH + SWITCH` = อ่านสองครั้ง; `x * 0` ที่ x มาจาก SWITCH ยังอ่าน) · MMIO ไม่นับเป็น leaf ใน -O1 (§6.9 ข้อ 5–6) จึงไม่ถูกเลื่อนไปอ่านช้า

**รหัส error ใหม่** (ADR-009 + ADR-010):

| รหัส | Stage | ความหมาย |
|---|---|---|
| E032 | sema | `printf` / `scanf` ใช้ไม่ได้บน `--target fpga` |
| E033 | lexer | `#define` นิยามซ้ำต่างค่า / อ้างถึงตัวเอง / ชื่อเป็น keyword |
| E034 | parser | ที่อยู่ MMIO หารด้วย 4 ไม่ลงตัว หรือเกิน `0xFFFFFFFF` |

**Consequences:** เพิ่ม golden ที่ใช้ `#define` / hex / MMIO; ตัวอย่างที่ 1 ของ IDE กลายเป็น golden asm `tests/golden/fpga_switch_to_led.s`; differential กับ gcc ยังใช้ได้กับโปรแกรมที่ใช้ `#define`/hex (gcc ทำ preprocessing เอง) แต่ไม่ได้กับโปรแกรมที่แตะ MMIO (บน host เป็น address ที่เขียนไม่ได้) → ติด `// no-gcc-oracle:`

**คำถามที่ตัดสินแล้ว (ใช้ค่าเริ่มต้นทั้งหมด):**
- **Q1 — hex ขัดกับ test เดิม:** golden `tests/errors/e001_hex_literal` (มีมาตั้งแต่ M1) คาดว่า `return 0x1F;` เป็น error `E001` แต่งานนี้ให้เพิ่ม hex ใน lexer **และ** สั่งว่า test เดิมทุกตัวต้องผ่านเหมือนเดิม — ทำทั้งสองอย่างพร้อมกันไม่ได้ · ค่าเริ่มต้น: hex ใช้ได้ **ทุก target** (เป็น C99 ที่ถูกต้อง) และเปลี่ยน golden นั้นเป็น hex ที่ผิดรูป (`0x`, `0x1G` → `E001`) พร้อมเพิ่ม golden ที่ `return 0x1F;` ได้ 31 · ทางเลือก: hex ใช้ได้เฉพาะ `--target fpga` (test เดิมไม่เปลี่ยน แต่โปรแกรมเดียวกันได้ผลต่างกันตาม target)
- **Q4 — MMIO บน `--target spim`:** "ใช้ได้ทั้งสอง target" อ่านได้สองแบบ · ค่าเริ่มต้น: คอมไพล์ได้ทั้งสอง target (`lw`/`sw` ที่อยู่นั้นตรง ๆ) — บน SPIM/MARS จะเกิด address exception ตอนรัน (เป็น kernel space) · ทางเลือก: บน `spim` เป็น compile error
- **Q5 — "fold -O1: ถ้า hi เหมือนกันใช้ offset ได้":** ค่าเริ่มต้น: ที่ `-O1` ใส่ lo16 ลงใน offset ของ `lw`/`sw` แทน `ori` (เช่น SEG7 = `lui $t2, 0xF000` + `sw $t0, 8($t2)`; ปรับ hi เมื่อ lo16 ≥ 0x8000) **ต่อการเข้าถึงหนึ่งครั้ง** — ไม่ใช้ `$t2` ซ้ำข้าม statement (ต้องรู้สถานะ register ข้าม label ซึ่งเกินขอบเขต)
