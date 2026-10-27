# c2mips

คอมไพเลอร์ภาษา C ชุดย่อย (**MiniC**) → **MIPS32 assembly** เขียนด้วย Python ล้วน มี `nCk(n, k)` เป็นฟังก์ชันในตัว
ใช้ได้กับสองปลายทาง:

| ปลายทาง | ใช้กับ | ตัวเลือก |
|---|---|---|
| **FPGA Studio** (CPU `openmips` บนบอร์ด Nexys A7) | ใช้เป็น custom compiler ใน IDE ดูตารางรหัสเครื่องและรันบน sim/บอร์ดได้ | `--target fpga` |
| SPIM / MARS | simulator MIPS สำหรับเรียน, มี `printf` / `scanf` | `--target spim` (ค่าเริ่มต้น) |

```c
#define SEG7 (*(volatile int*)0xF0000008)

int main() {
    SEG7 = nCk(10, 3);      // 7-Segment แสดง 120
    while (1) { }
}
```

> คู่มือนี้เน้นการใช้กับ **FPGA Studio** · ข้อกำหนดภาษาและเหตุผลการออกแบบทุกข้ออยู่ใน [**Spec.md**](Spec.md)
> ([ADR-009](docs/adr/ADR-009-target-fpga.md) target fpga, [ADR-010](docs/adr/ADR-010-preprocessor-mmio.md) `#define` + I/O)
> · คู่มือการทดสอบอยู่ใน [docs/usage.md](docs/usage.md)

---

## สารบัญ

1. [เริ่มใช้กับ FPGA Studio ใน 5 นาที](#1-เริ่มใช้กับ-fpga-studio-ใน-5-นาที)
2. [เขียนโปรแกรมสำหรับบอร์ด](#2-เขียนโปรแกรมสำหรับบอร์ด)
3. [อ่านผลใน FPGA Studio](#3-อ่านผลใน-fpga-studio)
4. [ตัวอย่างของ FPGA Studio ใช้ได้แค่ไหน](#4-ตัวอย่างของ-fpga-studio-ใช้ได้แค่ไหน)
5. [แก้ปัญหา (FPGA Studio)](#5-แก้ปัญหา-fpga-studio)
6. [ทำงานอย่างไรเบื้องหลัง](#6-ทำงานอย่างไรเบื้องหลัง)
7. [ใช้กับ SPIM / MARS](#7-ใช้กับ-spim--mars)
8. [ภาษา MiniC โดยย่อ](#8-ภาษา-minic-โดยย่อ)
9. [ทดสอบ](#9-ทดสอบ)
10. [โครงสร้างโปรเจกต์และการพัฒนาต่อ](#10-โครงสร้างโปรเจกต์และการพัฒนาต่อ)

---

## 1. เริ่มใช้กับ FPGA Studio ใน 5 นาที

### 1.1 สิ่งที่ต้องมี

- Windows 10/11 ที่ติดตั้ง **FPGA Studio** แล้ว
- **Python 3.11 ขึ้นไป** จาก <https://www.python.org/downloads/> — ตอนติดตั้ง **ติ๊ก "Add python.exe to PATH"**
  ตรวจด้วย `python --version` ใน PowerShell
- ไม่ต้องมี Java, SPIM, MARS หรือ gcc

### 1.2 ดาวน์โหลด c2mips

**มี git:**

```powershell
git clone https://github.com/Sorawitphum/c2mips.git C:\c2mips-repo
```

**ไม่มี git:** กดปุ่ม **Code → Download ZIP** บน GitHub แล้วแตกไฟล์ไปไว้ที่ `C:\c2mips-repo`

ตรวจว่าโครงสร้างถูก — ต้องได้ `True` ทั้งสองบรรทัด:

```powershell
Test-Path C:\c2mips-repo\c2mips\__main__.py
Test-Path C:\c2mips-repo\tools\c2mips_fpga.bat
```

> **สำคัญ:** โฟลเดอร์ `C:\c2mips-repo` ต้องเป็น repo **ทั้งก้อน** (มีโฟลเดอร์ย่อย `c2mips\` และ `tools\` อยู่ข้างใน)
> ถ้าคัดลอกแค่โฟลเดอร์ `c2mips\` ด้านในออกมาจะใช้ไม่ได้ (ดู [§5](#5-แก้ปัญหา-fpga-studio))
> จะวางไว้ที่อื่นก็ได้ แต่ห้าม path มีอักขระไทย

ไม่ต้องสั่ง `pip install` — wrapper โหลดโค้ดจาก repo เอง (ถ้ามี `.venv` ใน repo จะใช้ Python ในนั้นก่อน)

### 1.3 ทดสอบก่อนนำเข้า IDE

```powershell
cd C:\c2mips-repo
.\tools\c2mips_fpga.bat examples\fpga\hello_seg7.c
```

> ใน PowerShell ต้องมี `.\` นำหน้าเสมอ ไม่งั้นได้ `The term '...bat' is not recognized`

ถ้าใช้ได้จะเห็น assembly พิมพ์ออกมา บรรทัดแรกคือ `lui $sp, 0x8001` และมีไฟล์ `.c.s` เกิดข้างไฟล์ต้นทาง

### 1.4 นำเข้าเป็นคอมไพเลอร์ใน FPGA Studio

1. ใน FPGA Studio เลือก **นำเข้าคอมไพเลอร์** ("เลือกไฟล์คอมไพเลอร์ที่ต้องการนำเข้า (.exe, .bat, .py, .jar, .sh)")
2. เลือกไฟล์ **`C:\c2mips-repo\tools\c2mips_fpga.bat`**
   — เลือกจากตำแหน่งนี้โดยตรง **อย่าคัดลอกไฟล์ `.bat` ไปไว้ที่อื่น** เพราะมันหาตัวคอมไพเลอร์จากโฟลเดอร์แม่ของตัวเอง
3. Architecture เลือก **MIPS32** และ CPU เลือก **openmips (Nexys A7)**
4. ช่อง arguments ปล่อยไว้ตามเดิมได้ — wrapper **ไม่ส่งต่อ** argument จาก IDE (เช่น `-march=mips32 -O2`) ให้ c2mips
   ([§5](#5-แก้ปัญหา-fpga-studio))

### 1.5 ลองโปรแกรมแรก

เปิดแท็บใหม่ วางโค้ดนี้ (= `examples\fpga\hello_seg7.c`) แล้วกดแปลง:

```c
int main() {
    int a = 5;
    int b = a + 1;
    return b;
}
```

ผลที่ถูกต้อง (ตรวจแล้วบน FPGA Studio):

```text
PC      Type  Assembly                  Hex
0x0000  I     lui   $sp, 0x8001         0x3C1D8001   ← ตั้ง stack
0x0004  J     jal f_main <0x001C>       0x0C000007   ← เรียก main
0x0008  R     nop                       0x00000000   ← delay slot
0x000C  I     lui   $t0, 0xF000         0x3C08F000
0x0010  I     sw    $v0, 8($t0)         0xAD020008   ← SEG7 = ค่าที่ main คืน (6)
0x0014  J     j _halt <0x0014>          0x08000005   ← จบ: วนที่ตัวเอง
0x0018  R     nop                       0x00000000
0x001C  ...   (โค้ดของ main)
```

กด Run ใน simulator → **SEG7 แสดง 6** แล้วค้างที่ `_halt` = ใช้ได้แล้ว

### 1.6 ตัวอย่างพร้อมใช้ (`examples\fpga\`)

เปิดไฟล์เหล่านี้ใน IDE (File → Open) หรือคัดลอกโค้ดไปวาง:

| ไฟล์ | ทำอะไร | SEG7 ที่ควรเห็น |
|---|---|---|
| `hello_seg7.c` | โปรแกรมแรก | `6` |
| `switch_to_led.c` | ตัวอย่างที่ 1 ของ IDE: สวิตช์ + 1 → LED, SEG7 | ค่าสวิตช์ + 1 |
| `nck_seg7.c` | `nCk(10, 3)` | `120` |
| `calculator.c` | ตัวอย่างที่ 3 ของ IDE แบบที่ c2mips คอมไพล์ได้ | สวิตช์ซ้าย + สวิตช์ขวา |
| `pymips_nck.c` | ตัวอย่างที่ 7 ของ IDE แบบที่ c2mips คอมไพล์ได้ (`5C2` → RAM[0]) | `10` |
| `div_by_zero.c` | ทดสอบ panic | `DEAD0001` |
| `new_instructions.c` | ทดสอบคำสั่ง `div mfhi mult mflo slt sltiu` กับ assembler ของ IDE | `2` |

---

## 2. เขียนโปรแกรมสำหรับบอร์ด

### 2.1 I/O ของบอร์ด (memory-mapped)

บอร์ดไม่มีระบบปฏิบัติการ จึง **ไม่มี `printf` / `scanf`** (ใช้แล้วได้ error `E032`) — ติดต่อกับบอร์ดด้วยการอ่าน/เขียนที่อยู่:

| อุปกรณ์ | ที่อยู่ | ทิศทาง | เขียนใน C |
|---|---|---|---|
| LED 16 ดวง | `0xF0000000` | เขียน | `#define LED (*(volatile int*)0xF0000000)` |
| สวิตช์ 16 ตัว | `0xF0000004` | อ่าน | `#define SWITCH (*(volatile int*)0xF0000004)` |
| 7-Segment 8 หลัก | `0xF0000008` | เขียน | `#define SEG7 (*(volatile int*)0xF0000008)` |

```c
#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    while (1) {
        int sw = SWITCH;      // อ่านสวิตช์
        int result = sw + 1;
        LED = result;         // เขียน LED
        SEG7 = result;        // เขียน 7-Segment
    }
}
```

กติกา:

- `#define NAME ค่า` ใช้ได้เฉพาะแบบ **ไม่มี argument** (ไม่มี `#define F(x) ...`, `#if`, `#undef`)
- I/O ต้องอยู่ในรูป `*(volatile int*)ที่อยู่` เท่านั้น ที่อยู่เป็นค่าคงที่และหารด้วย 4 ลงตัว
  — ตัวแปร pointer (`volatile int *p = ...; p[0] = x;`) **ยังใช้ไม่ได้** (`E030`)
- ทุกการอ่าน/เขียน I/O เกิดจริงและตามลำดับในโค้ด ไม่ถูกตัดหรือสลับ (`volatile`)
- เลขฐานสิบหก `0x...` ใช้ได้
- `#include "nexys_a7.h"` ถูกข้ามไป — ให้ `#define` เองในไฟล์ (ตามตารางข้างบน)

### 2.2 ใช้ `nCk`

`nCk(n, k)` มีในตัว ไม่ต้อง include อะไร ได้ผลถูกต้องทุกค่าที่พอดี int (ไม่ล้นระหว่างคำนวณ):

```c
#define SEG7 (*(volatile int*)0xF0000008)

int main() {
    int n = 5;
    int k = 2;
    return nCk(n, k);       // SEG7 แสดง 10
}
```

`nCk(n, k)` = 0 เมื่อ `k > n` หรือมีค่าติดลบ · ผลเกิน 2,147,483,647 → panic (ดู [§3.2](#32-ค่าบน-7-segment-เมื่อโปรแกรมจบ))

### 2.3 ทำอะไรได้ / ไม่ได้

| ใช้ได้ | ยังใช้ไม่ได้ → ทางเลี่ยง |
|---|---|
| `int`, ตัวแปร local, `if/else`, `while`, `for`, ฟังก์ชัน ≤ 4 พารามิเตอร์, recursion | `char` `float` array struct ตัวแปร global |
| `+ - * / %`, `< <= > >= == !=`, `&& \|\| !` | `++` `--` → `i = i + 1` · `+=` → `x = x + y` |
| `nCk(n, k)` | `>>` `<<` `&` `\|` `^` `~` → สำหรับค่าที่ไม่ติดลบ: `x >> 8` = `x / 256`, `x & 255` = `x % 256`, `x << 3` = `x * 8` |
| I/O ผ่าน `#define` แบบ `*(volatile int*)ที่อยู่` | ตัวแปร pointer, `p[i]` → `#define RAM0 (*(volatile int*)0x00000000)` แล้วใช้ `RAM0 = x;` |
| — | `printf` `scanf` (ไม่มีบนบอร์ด) → เขียนผลลง `SEG7` หรือ `LED` |

ทุกข้อที่ใช้ไม่ได้จะขึ้น **error พร้อมเลขบรรทัด** ใน IDE (ไม่แปลงผิดแบบเงียบ ๆ)

---

## 3. อ่านผลใน FPGA Studio

### 3.1 ตาราง 32-bit Machine Code

- `0x00000000` ที่ถูกต้องมีแบบเดียว คือ **`nop` ที่อยู่ถัดจาก branch/jump** (`jal`, `j`, `jr`, `beq`, `bne`, `bltz` ...)
  เพราะ CPU openmips มี **delay slot** — คำสั่งถัดจาก branch ถูกทำเสมอ
- ถ้าเห็น `0x00000000` ที่คอลัมน์ Assembly **ไม่ใช่** `nop` แปลว่า assembler ของ IDE ไม่รู้จักคำสั่งนั้น
  (IDE แปลงคำสั่งที่ไม่รู้จักเป็น 0 โดยไม่เตือน) — กรุณาแจ้งเป็น issue พร้อมตาราง
- **คอลัมน์ Description บอกที่อยู่หน่วยความจำผิดได้** เช่น `sw $t0, -4($fp)` อาจเขียนว่า `MEM[0x8000FFFC]`
  ทั้งที่จริงคือ `0x8000FFF4` — IDE คำนวณคอลัมน์นี้แบบคงที่ ไม่ได้ไล่ค่า register จริง
  ให้ดูค่าจริงจากแผง **CPU & Registers** ตอนกด Run/Step

### 3.2 ค่าบน 7-Segment เมื่อโปรแกรมจบ

| เหตุการณ์ | SEG7 แสดง | จากนั้น |
|---|---|---|
| `main` return ค่า v (ไม่มี `return` = 0) | **v** (เขียนทับค่าที่โปรแกรมเขียน SEG7 ไว้เอง) | วนค้างที่ `_halt` |
| หารด้วยศูนย์ (`/` หรือ `%`) | `0xDEAD0001` (`DEAD0001`) | วนค้างที่ `_panic` |
| `nCk` เกิน int | `0xDEAD0002` (`DEAD0002`) | วนค้างที่ `_panic` |
| `while (1)` ไม่จบ | ค่าที่โปรแกรมเขียนเอง | ทำงานต่อไปเรื่อย ๆ |

### 3.3 ความเร็ว

c2mips สร้างโค้ดแบบ `-O0` (อ่านง่าย ตรงตาม template ใน Spec §6) ซึ่งยาวกว่าโค้ดของ mips-gcc ที่มากับ IDE
เช่น ตัวอย่างที่ 1 (สวิตช์ → LED) ใช้ **23 คำสั่งต่อรอบ** เทียบกับ gcc 5 คำสั่ง
ผลลัพธ์เหมือนกันทุกอย่าง แต่ที่ความเร็ว sim 5 Hz ของ IDE จะเห็น LED เปลี่ยนช้ากว่า (~4.6 วินาทีต่อรอบ)
— เพิ่มความเร็ว sim ใน IDE ได้ (`sim_speed`)

ตอนนี้ยังเลือก `-O1` ผ่าน IDE ไม่ได้ (wrapper ไม่ส่งต่อ argument) — ถ้าต้องการ ให้แก้บรรทัด
`"%PY%" -m c2mips --target fpga ...` ใน `tools\c2mips_fpga.bat` เป็น `... --target fpga -O1 ...`

---

## 4. ตัวอย่างของ FPGA Studio ใช้ได้แค่ไหน

ตัวอย่างในโฟลเดอร์ `workspace\nexys-a7-project` ของ IDE:

| ไฟล์ | ผล | หมายเหตุ / ทางแก้ |
|---|---|---|
| `1_switch_to_led.c` | ✅ ใช้ได้โดยไม่ต้องแก้ | ตรวจตารางรหัสเครื่องแล้วถูกทุกคำสั่ง |
| `2_binary_counter.c` | ❔ ยังไม่ได้ลอง | |
| `3_calculator.c` | ❌ `E010` ที่ `>>` | ใช้ `raw / 256` แทน `raw >> 8` และ `raw % 256` แทน `raw & 255` (ค่าสวิตช์ไม่ติดลบ ผลเท่ากัน) |
| `4_fibonacci.c` | ❔ ยังไม่ได้ลอง | ถ้ามี `++` ให้แก้เป็น `i = i + 1` |
| `5_hello_world_vga.c` | ❔ ยังไม่ได้ลอง | VGA ยังไม่มีในตาราง I/O ของ c2mips |
| `6_direct_assembly.s`, `8_pymips_pipeline_test.s` | — | เป็น assembly ไม่ต้องผ่านคอมไพเลอร์ C |
| `7_pymips_nck.c` | ❌ `E030` ที่ `i++` และใช้ตัวแปร pointer `ram[0]` | ใช้ `nCk` ในตัวแทน `nCr` และ `#define RAM0 (*(volatile int*)0x00000000)` แทน `ram[0]` (ตัวอย่างด้านล่าง) |

ฉบับที่แก้แล้วของตัวอย่างที่ 3 และ 7 อยู่ใน `examples\fpga\calculator.c` และ `examples\fpga\pymips_nck.c`

ช่วยกันเติมตารางนี้ได้ — ลองตัวอย่างที่เป็น ❔ แล้วแจ้งผล

---

## 5. แก้ปัญหา (FPGA Studio)

| อาการ | สาเหตุ | วิธีแก้ |
|---|---|---|
| ตารางมีแต่บรรทัดของโค้ด C และ Hex เป็น `0x00000000` ทุกบรรทัด | คอมไพเลอร์ล้มเหลว IDE จึงแสดงซอร์สแทน | ดู **ข้อความสีแดงด้านล่างหน้าต่าง** — มี `ไฟล์:บรรทัด:คอลัมน์: error[Exxx]` บอกจุดที่ผิด |
| `error[E031]: unsupported preprocessor directive` | ใช้ c2mips รุ่นเก่า หรือใช้ `#if` / `#define` ที่มี argument | ใช้ c2mips รุ่นที่มี `--target fpga` และใช้ `#define NAME ค่า` แบบไม่มี argument |
| `error[E030]: operator '++' is not supported` | MiniC ยังไม่มี `++` `--` `+=` | เขียนเป็น `i = i + 1` ([§2.3](#23-ทำอะไรได้--ไม่ได้)) |
| `error[E010]: expected expression but found '>'` | ใช้ `>>` (หรือ `<<`) | ใช้ `/` หรือ `*` ด้วยกำลังของ 2 ([§2.3](#23-ทำอะไรได้--ไม่ได้)) |
| `error[E032]` | ใช้ `printf` / `scanf` บน target fpga | เขียนผลลง `SEG7` / `LED` แทน |
| PowerShell: `The term 'xxx.bat' is not recognized` | PowerShell ไม่รันไฟล์ในโฟลเดอร์ปัจจุบันถ้าไม่มี `.\` | พิมพ์ `.\tools\c2mips_fpga.bat ...` (ใน cmd ไม่ต้องมี `.\`) |
| `No module named c2mips` | โฟลเดอร์ผิด: `.bat` ไม่ได้อยู่ใน `tools\` ของ repo หรือ repo ไม่ครบ | ตรวจ [§1.2](#12-ดาวน์โหลด-c2mips) ให้ได้ `True` ทั้งสองบรรทัด และนำเข้า `.bat` จาก `tools\` โดยตรง |
| `ImportError: cannot import name 'dataclass' ... (most likely due to a circular import)` | คัดลอกแค่โฟลเดอร์ `c2mips\` ด้านในออกมาวางเป็น repo ทำให้ไฟล์ `ast.py` ของ c2mips ไปบังโมดูล `ast` ของ Python | วาง repo ทั้งก้อน: `C:\c2mips-repo\c2mips\__main__.py` ต้องมีอยู่จริง |
| `'python' is not recognized` | ไม่ได้ติดตั้ง Python หรือไม่ได้ติ๊ก Add to PATH | ติดตั้ง Python ใหม่แล้วติ๊ก "Add python.exe to PATH" |
| `0x00000000` ที่ไม่ใช่ `nop` | assembler ของ IDE ไม่รู้จักคำสั่งนั้น | แจ้ง issue พร้อมตาราง ([§3.1](#31-ตาราง-32-bit-machine-code)) |
| LED เปลี่ยนช้า | โค้ด `-O0` ยาว + sim 5 Hz | [§3.3](#33-ความเร็ว) |
| `Windows denied access` ตอนวางไฟล์ไว้ที่ `C:\` | Windows ป้องกัน root ของไดรฟ์ C | วาง repo ในโฟลเดอร์ย่อย เช่น `C:\c2mips-repo` |

---

## 6. ทำงานอย่างไรเบื้องหลัง

### 6.1 IDE เรียกคอมไพเลอร์อย่างไร (สังเกตจากเครื่องจริง)

1. IDE บันทึกโค้ดในแท็บที่เปิดอยู่เป็น `%TEMP%\fpga_studio_temp_src.c`
2. เรียก `c2mips_fpga.bat %TEMP%\fpga_studio_temp_src.c` (ส่ง path อย่างเดียว, โฟลเดอร์ทำงาน = โฟลเดอร์ติดตั้ง IDE)
3. wrapper รัน `python -m c2mips --target fpga <src> -o <src>.s` แล้ว
   - เขียน `%TEMP%\fpga_studio_temp_src.c.s` **และ** พิมพ์ assembly เดียวกันออก stdout
   - ถ้า error: ข้อความออก stderr พร้อม exit code ไม่เป็น 0 → IDE แสดงเป็นแถบสีแดง
4. IDE assemble ด้วย assembler ของตัวเอง แล้วแสดงตาราง / ส่งออก VHDL, Verilog, `.coe`

### 6.2 assembly ที่ `--target fpga` สร้าง

- **มีแค่ label กับคำสั่งจริง** — ไม่มี directive, comment, pseudo-instruction (`li`, `move`, `b`, `la`),
  `syscall`, `.data` และไม่ใช้ `$at` (เพราะ assembler ของ IDE เปลี่ยนสิ่งที่ไม่รู้จักเป็น `0x00000000` เงียบ ๆ)
  - `li r, v` → `addiu r, $zero, v` หรือ `lui` + `ori` · `move a, b` → `addu a, b, $zero` · `b L` → `beq $zero, $zero, L`
- **ทุก branch/jump ตามด้วย `nop`** (delay slot)
- **startup** แบบเดียวกับ mips-gcc ของ IDE: เริ่มที่ PC `0x0000` → `lui $sp, 0x8001` → `jal f_main` → เขียนค่าที่คืนลง SEG7 → `_halt`
- **runtime** (`nCk`, panic) แนบเฉพาะเมื่อโปรแกรมใช้ `nCk`, `/` หรือ `%` — มาจาก `c2mips/runtime/runtime_fpga.s`
  ซึ่งใช้อัลกอริทึม nCk เดียวกับ `runtime.s` ที่ทดสอบ exhaustive แล้ว
- **ฟังก์ชันของผู้ใช้** ถูกตั้งชื่อเป็น `f_<ชื่อ>` (เช่น `main` → `f_main`) กันชนกับชื่อคำสั่ง
- คอมไพเลอร์ตรวจทุกบรรทัดกับรายการคำสั่งที่อนุญาต:
  `addu addiu subu and andi or ori xor xori nor slt slti sltu sltiu sll srl sra lui lw sw beq bne bltz bgez blez bgtz j jal jr mult multu div divu mfhi mflo nop`

### 6.3 สถานะการทดสอบบน FPGA Studio

| รายการ | สถานะ |
|---|---|
| IDE เรียก `c2mips_fpga.bat` และแสดง error ของ c2mips | ✅ |
| โปรแกรม `a = 5; b = a + 1; return b;` — ตารางรหัสเครื่องถูกทุกคำสั่ง | ✅ |
| ตัวอย่างที่ 1 (สวิตช์ → LED) — ตารางรหัสเครื่องถูกทุกคำสั่ง | ✅ |
| กด Run แล้วเห็นค่าบน SEG7 / LED จริง | ⏳ ยังไม่ได้บันทึกผล |
| `nck_seg7.c` → SEG7 = 120 (runtime ที่มีลูปและ delay slot) | ⏳ |
| `div_by_zero.c` → SEG7 = `DEAD0001` | ⏳ |
| `new_instructions.c` — คำสั่งที่ยังไม่เคยเห็นใน IDE (`div` `mfhi` `mult` `mflo` `slt` `sltiu`) | ⏳ ไม่ควรมี `0x00000000` ที่ไม่ใช่ `nop` |
| บนบอร์ด Nexys A7 จริง | ⏳ |

### 6.4 ทดสอบโดยไม่มีบอร์ด

`tests/fpga_sim.py` แปลง assembly เป็นรหัสเครื่อง MIPS32 จริงแล้วรันแบบมี delay slot และ I/O ของบอร์ด —
`pytest -q tests/test_fpga.py` ตรวจตัวอย่างที่ 1 ของ IDE, A1–A13, N1–N17 (เทียบกับ SPIM) และยืนยันว่าถ้าไม่มี `nop` ผลจะผิด

---

## 7. ใช้กับ SPIM / MARS

### 7.1 ติดตั้ง

```bash
git clone https://github.com/Sorawitphum/c2mips.git c2mips
cd c2mips
python -m venv .venv
```

| OS / shell | เปิด venv |
|---|---|
| Linux, macOS | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |

```bash
pip install .            # ใช้งานอย่างเดียว (ได้คำสั่ง c2mips)
pip install -e ".[dev]"  # พัฒนาหรือรัน test
c2mips --version
```

**Simulator** (เลือกอย่างใดอย่างหนึ่ง)

| OS | SPIM | MARS (ต้องมี Java 8+) |
|---|---|---|
| Debian / Ubuntu | `sudo apt install spim` | ทุก OS |
| Arch / Fedora | แตก `spim_8.0+dfsg-7_amd64.deb` จาก `deb.debian.org/debian/pool/main/s/spim/` แล้วคัดลอก `usr/bin/spim` → `/usr/local/bin/`, `usr/lib/spim/exceptions.s` → `/usr/lib/spim/` | ✅ |
| Windows + WSL | `wsl --install -d Ubuntu-24.04` แล้ว `wsl -d Ubuntu-24.04 -- sudo apt install -y spim` — c2mips เรียกผ่าน `tools\spim.cmd` (ตั้ง `$env:SPIM` เป็น path ของไฟล์นี้สำหรับ `--run`) | ✅ |
| Windows ไม่มี WSL | ไม่มี spim แบบบรรทัดคำสั่ง | ✅ ใช้ MARS แทนได้ทั้ง `--run` และ test |
| macOS | ยังไม่ได้ทดสอบ — QtSpim (GUI) หรือคอมไพล์ spim เอง | ควรใช้ได้ |

MARS:

```powershell
Invoke-WebRequest https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar -OutFile C:\tools\Mars4_5.jar
(Get-FileHash C:\tools\Mars4_5.jar).Hash   # AC340B676BA2B62246B9DF77E62F81AD4447BCFD329AB539716BCD09950B7096
setx MARS_JAR "C:\tools\Mars4_5.jar"       # เปิด terminal ใหม่หลังสั่ง
```

MARS พิมพ์บรรทัดว่างเพิ่มหนึ่งบรรทัดตอนจบ · บน Windows ถ้า output มีภาษาไทยให้เพิ่ม `-Dstdout.encoding=ISO-8859-1` หลัง `java`
([Spec S17, S20](Spec.md#13-ผลการ-spike-ที่ยืนยันแล้ว))

### 7.2 ใช้งาน

```c
#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("C(10,3) = %d\n", nCk(10, 3));
    return 0;
}
```

```console
$ c2mips examples/hello_nck.c --run
C(10,3) = 120
```

```bash
c2mips prog.c                    # ได้ prog.s ข้าง ๆ ไฟล์ต้นทาง
c2mips prog.c -o out.s -O1       # ตั้งชื่อเอง + optimize
c2mips prog.c --run              # คอมไพล์แล้วรัน (spim ถ้ามี ไม่งั้น MARS)
spim -file prog.s                # หรือรันเอง
java -jar Mars4_5.jar nc prog.s
```

| ตัวเลือก | ความหมาย |
|---|---|
| `-o FILE` | ไฟล์ output (ค่าเริ่มต้น: ชื่อเดิม นามสกุล `.s`) |
| `-O0` / `-O1` | `-O0` (ค่าเริ่มต้น) อ่านง่ายตรงตาม template · `-O1` พับค่าคงที่และลดคำสั่ง ~32% ผลเหมือนกันทุกโปรแกรม |
| `--target spim\|fpga` | `spim` (ค่าเริ่มต้น) = SPIM/MARS · `fpga` = openmips / FPGA Studio |
| `--run` | รันไฟล์ที่ได้ ส่ง stdin, stdout และ exit code ต่อ (ใช้ไม่ได้กับ `--target fpga`) |
| `--sim auto\|spim\|mars` | simulator ของ `--run` · `auto` = spim ถ้าเจอ ไม่งั้น MARS (`$MARS_JAR` + `java`) |
| `--emit=tokens\|ast\|asm` | พิมพ์ผลของแต่ละ stage ออกหน้าจอแทนการเขียนไฟล์ |
| `--no-runtime` | ไม่ต่อท้าย runtime (`nCk`, panic) |

- **Exit code ของ `c2mips`:** `0` สำเร็จ (มี warning ได้) · `1` compile error · `2` ใช้งานผิด / อ่านไฟล์ไม่ได้
- **ผลตอนรัน (target spim):** ค่าที่ `main` return = exit code · หารศูนย์หรือ `nCk` ล้น → พิมพ์ `runtime error: ...` แล้ว exit **70**
- **รับ input:** `scanf("%d", &x)` อ่านบรรทัดละหนึ่งตัว เช่น `printf '17\n-5\n' | c2mips prog.c --run`
- **ดูทีละคำสั่ง:** เปิดไฟล์ `.s` ใน MARS หรือ QtSpim — ไฟล์จาก `-O0` มี comment บอกว่ามาจากบรรทัด C ไหน
- ตัวอย่างใน [`examples/`](examples): `hello_nck.c`, `example.c`, `fact.c`, `fib.c`, `gcd.c`, `nck_user.c`

---

## 8. ภาษา MiniC โดยย่อ

ทุกโปรแกรม MiniC เป็น C99 ที่ gcc คอมไพล์ได้ — กฎเต็มอยู่ใน [Spec §4](Spec.md#4-ภาษาที่รองรับ-minic)

| มี | ไม่มี (ได้ error `E030` บอกตรง ๆ) |
|---|---|
| `int` (32 บิต), ตัวแปร local, block scope + shadowing; เลขฐานสิบ และฐานสิบหก `0x...` | `char` `float` `long` ฯลฯ, pointer, array, struct (ยกเว้น I/O `*(volatile int*)ที่อยู่`) |
| `+ - * / %` (wrap แบบ `gcc -fwrapv`, หารปัดเข้าหาศูนย์) | `++` `--` `+=` ฯลฯ, `<< >> & \| ^ ~` |
| `< <= > >= == !=`, `&& \|\| !` (short-circuit) | `break` `continue` `switch` `do` `goto` |
| `if/else`, `while`, `for` (init ประกาศตัวแปรได้) | ตัวแปร global, `#define` ที่มี argument, `#if` `#undef` |
| ฟังก์ชัน ≤ 4 พารามิเตอร์, recursion, prototype | ฟังก์ชันที่พารามิเตอร์เกิน 4 ตัว (`E028`) |
| `printf` (string literal กับ `%d` `%%`, ภาษาไทยได้) และ `scanf("%d", &x)` — **target spim เท่านั้น** | `%s` `%x` ฯลฯ |
| `nCk(n, k)` ผลถูกต้องทุกค่าที่พอดี int | — |

`#include <stdio.h>`, `#include "c2mips.h"` และ `#include "nexys_a7.h"` ถูกข้ามไป · `#define NAME ค่า` (ไม่มี argument) ใช้ได้

ค่าที่ C ไม่นิยาม c2mips นิยามให้ชัด: `x / 0` และ `x % 0` → panic · `INT_MIN / -1` = `INT_MIN` · `INT_MIN % -1` = `0` ·
`nCk(n, k)` = 0 เมื่อ `k > n` หรือค่าติดลบ · `nCk` เกิน 2,147,483,647 → panic

---

## 9. ทดสอบ

ต้องติดตั้งแบบ `pip install -e ".[dev]"` ก่อน

```bash
ruff check .
mypy --strict c2mips
pytest -q                                   # ~1,500 test, 2-3 นาที
pytest -q tests/test_fpga.py                # เฉพาะ target fpga (ไม่ต้องมี IDE หรือบอร์ด)
```

test ที่ขาดเครื่องมือ (spim, gcc, MARS) จะถูก **skip** ไม่ใช่ fail · test ที่ต้องรันไฟล์ `.s` ใช้ spim ถ้ามี ไม่งั้น MARS
(บังคับด้วย `C2MIPS_SIMULATOR=spim` หรือ `mars`)

```bash
pytest -q -m random --random-count 500            # โปรแกรมสุ่ม: SPIM -O0 = SPIM -O1 = gcc = Python
MARS_JAR=/path/to/Mars4_5.jar pytest -q -m mars   # ความเข้ากันได้กับ MARS
python tests/random/gen.py --seed 42              # ดูโปรแกรมสุ่มของ seed นั้น
```

gcc (เฉพาะคนรัน differential test): ใช้รุ่น ≥ 7 เช่น WinLibs หรือ MSYS2 แล้วตั้ง `$env:GCC` ถ้าไม่อยู่ใน PATH —
**อย่าใช้ MinGW gcc 6.3** มันคำนวณ `-(INT_MIN / x)` ผิดภายใต้ `-fwrapv` ([Spec S23](Spec.md#13-ผลการ-spike-ที่ยืนยันแล้ว))

CI (GitHub Actions) รันทุก push และมี nightly สุ่ม 10,000 โปรแกรม + MARS — รายละเอียดใน [docs/usage.md](docs/usage.md)

---

## 10. โครงสร้างโปรเจกต์และการพัฒนาต่อ

```text
README.md                 คู่มือนี้
Spec.md                   ข้อกำหนดภาษา, การออกแบบ, ADR, ผลการทดลองบน SPIM/MARS/FPGA Studio
c2mips/                   ตัวคอมไพเลอร์: lexer -> parser -> sema -> fold (-O1) -> codegen -> emitter
c2mips/fpga.py            ส่วนเฉพาะ target fpga (แทน pseudo, delay slot, whitelist)
c2mips/runtime/           runtime.s (SPIM/MARS) และ runtime_fpga.s (openmips)
tools/c2mips_fpga.bat     wrapper สำหรับ FPGA Studio  ← ไฟล์ที่นำเข้า IDE
tools/spim.cmd            ตัวเรียก spim ใน WSL สำหรับ Windows
include/c2mips.h          prototype ของ nCk (ใช้ทั้ง c2mips และ gcc)
ref/nck_ref.c             nCk ภาษา C ที่ทำงานเหมือน runtime.s ทุกตัวอักษร (oracle ของ test)
examples/                 โปรแกรมตัวอย่าง (SPIM/MARS)
examples/fpga/            โปรแกรมตัวอย่างสำหรับ FPGA Studio
tests/                    programs/ (golden), errors/, random/, unit/, runtime/, fpga_sim.py
docs/                     usage.md (การทดสอบ), adr/ (Architecture Decision Records)
```

กติกา (รายละเอียด: Spec §14 และ `CLAUDE.md`):

- **ความหมายของภาษา** (Spec §4) และ **calling convention** (Spec §6) เปลี่ยนเมื่อมีเหตุผลเท่านั้น และต้องเขียน ADR ใหม่ใน `docs/adr/`
- ทุก feature ต้องมี **golden program** (`tests/programs/*.c` + `.expected`) และ **error test** (`tests/errors/*.c` + `.err`)
- ไฟล์ `.s` ที่ emit ต้องเป็น **ASCII ล้วน** (ไบต์ > 0x7F ทำให้ SPIM ค้าง แม้อยู่ใน comment)
- `c2mips/runtime/runtime.s` ผ่านการทดสอบแบบ exhaustive แล้ว — **ห้ามเขียนใหม่**
- target fpga: ห้าม emit คำสั่งนอก whitelist ([§6.2](#62-assembly-ที่---target-fpga-สร้าง)) และทุก branch/jump ต้องตามด้วย `nop`
- ก่อนส่งงาน: `ruff check .`, `mypy --strict c2mips`, `pytest -q` ต้องผ่านทั้งหมด

**งานต่อไปที่วางแผนไว้:** `++` `--` `+=` และ `<< >> & | ^ ~` (ให้ตัวอย่าง 3 และ 7 ของ IDE คอมไพล์ได้โดยไม่ต้องแก้),
ตัวแปร `volatile int *` + `p[i]` (ต้องเขียน ADR ก่อน), `-O1` จาก IDE

**License:** ยังไม่ได้กำหนด — ต้องเลือกและเพิ่มไฟล์ `LICENSE` ก่อนเผยแพร่ให้คนอื่นนำไปใช้ต่อ
