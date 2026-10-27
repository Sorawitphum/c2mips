# c2mips

คอมไพเลอร์ภาษา C ชุดย่อย (**MiniC**) → **MIPS32 assembly** ที่รันได้บน
[SPIM](https://spimsimulator.sourceforge.net/) และ [MARS](https://computerscience.missouristate.edu/mars-mips-simulator.htm)
เขียนด้วย Python ล้วน (ตอนรันใช้แค่ standard library) มี `nCk(n, k)` เป็นฟังก์ชันในตัว

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

> เอกสารนี้คือคู่มือผู้ใช้ · ข้อกำหนดภาษา การออกแบบ และเหตุผลทุกข้ออยู่ใน [**Spec.md**](Spec.md)
> · คู่มือการทดสอบละเอียดอยู่ใน [docs/usage.md](docs/usage.md)

---

## สารบัญ

1. [สิ่งที่ต้องมี](#1-สิ่งที่ต้องมี)
2. [ติดตั้ง c2mips (ทุก OS)](#2-ติดตั้ง-c2mips-ทุก-os)
3. [ติดตั้ง simulator](#3-ติดตั้ง-simulator)
4. [ใช้งาน](#4-ใช้งาน)
5. [ใช้กับ FPGA Studio](#5-ใช้กับ-fpga-studio)
6. [ภาษา MiniC โดยย่อ](#6-ภาษา-minic-โดยย่อ)
7. [ทดสอบ](#7-ทดสอบ)
8. [โครงสร้างโปรเจกต์](#8-โครงสร้างโปรเจกต์)
9. [พัฒนาต่อ](#9-พัฒนาต่อ)

---

## 1. สิ่งที่ต้องมี

| อะไร | ใช้ทำอะไร | จำเป็นไหม |
|---|---|---|
| Python **3.11+** | รัน c2mips | จำเป็น |
| SPIM 8.0 (`spim` แบบบรรทัดคำสั่ง) | รันไฟล์ `.s` และ `c2mips --run`; test ส่วนใหญ่ | แนะนำ |
| Java 8+ และ `Mars4_5.jar` | รันไฟล์ `.s` แบบ GUI หรือบรรทัดคำสั่ง บน **ทุก OS** | ทางเลือกแทน SPIM |
| gcc รุ่นใหม่ (≥ 7) | oracle ของ differential test | เฉพาะคนรัน test |

ไฟล์ `.s` ที่ได้มี runtime อยู่ในตัวและเป็น ASCII ล้วน — คัดลอกไปเปิดในเครื่องไหนก็ได้ที่มี SPIM หรือ MARS

**สถานะการทดสอบแต่ละ OS**

| OS | c2mips | SPIM | MARS |
|---|---|---|---|
| Windows 11 + WSL | ✅ test ครบทั้งชุด | ✅ ผ่าน WSL (`tools\spim.cmd`) | ✅ |
| Windows 11 **ไม่มี WSL** | ✅ test ครบทั้งชุด (รันบน MARS) | — ไม่มี spim แบบบรรทัดคำสั่งสำหรับ Windows | ✅ ใช้แทน spim ได้ทั้ง `--run` และ test |
| Linux (Ubuntu 24.04) | ควรใช้ได้ (Python ล้วน) — CI ตั้งไว้แล้วแต่ยังไม่เคยรัน | ✅ `apt install spim` (Spec §13) | ควรใช้ได้ (Java) |
| macOS | ควรใช้ได้ (Python ล้วน) — ยังไม่ได้ทดสอบ | ยังไม่ได้ทดสอบ (ดู [§3](#macos)) | ควรใช้ได้ (Java) — ยังไม่ได้ทดสอบ |

## 2. ติดตั้ง c2mips (ทุก OS)

```bash
git clone <repo-url> c2mips
cd c2mips
python -m venv .venv
```

เปิด virtual environment:

| OS / shell | คำสั่ง |
|---|---|
| Linux, macOS (bash/zsh) | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |

แล้วติดตั้ง:

```bash
pip install .            # ใช้งานอย่างเดียว
pip install -e ".[dev]"  # จะพัฒนาหรือรัน test (pytest, hypothesis, ruff, mypy)
```

ตรวจว่าใช้ได้: `c2mips --version`

ไม่อยากใช้ venv: `pipx install .` จะได้คำสั่ง `c2mips` ใช้ได้ทั้งเครื่อง

## 3. ติดตั้ง simulator

### Linux

```bash
sudo apt install spim        # Debian / Ubuntu
```

distro ที่ไม่มีแพ็กเกจ `spim` (เช่น Arch, Fedora): แตกไฟล์ `.deb` ของ Debian
(`spim_8.0+dfsg-7_amd64.deb` จาก `deb.debian.org/debian/pool/main/s/spim/`) แล้วคัดลอก `usr/bin/spim`
ไป `/usr/local/bin/` และ `usr/lib/spim/exceptions.s` ไป `/usr/lib/spim/` — binary ต้องการแค่ libc
(วิธีนี้ทดสอบแล้วบน Arch) · หรือใช้ MARS แทน

### Windows

SPIM แบบบรรทัดคำสั่งไม่มีสำหรับ Windows จึงมีสองทาง — เลือกทางเดียวพอ

**ทาง A: ไม่ใช้ WSL → ใช้ MARS** (ต้องการแค่ Java)

1. ติดตั้ง Java 8 ขึ้นไป เช่น Eclipse Temurin จาก <https://adoptium.net> แล้วตรวจด้วย `java -version`
2. ดาวน์โหลด MARS และตรวจ checksum (PowerShell):

   ```powershell
   Invoke-WebRequest https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar -OutFile C:\tools\Mars4_5.jar
   (Get-FileHash C:\tools\Mars4_5.jar).Hash   # AC340B676BA2B62246B9DF77E62F81AD4447BCFD329AB539716BCD09950B7096
   ```

3. บอก c2mips ว่า jar อยู่ไหน — ชั่วคราว: `$env:MARS_JAR = "C:\tools\Mars4_5.jar"` ·
   ถาวร: `setx MARS_JAR "C:\tools\Mars4_5.jar"` (เปิด terminal ใหม่หลังสั่ง)

แค่นี้ `c2mips prog.c --run` จะใช้ MARS เองเมื่อไม่เจอ spim และ test ทุกตัวที่ต้องใช้ simulator ก็รันบน MARS
(ช้ากว่า spim เพราะเปิด JVM ทุกโปรแกรม)

**ทาง B: ใช้ WSL → ได้ spim ตัวจริง** (เหมือน Linux)

```powershell
wsl --install -d Ubuntu-24.04
wsl -d Ubuntu-24.04 -- sudo apt install -y spim
```

c2mips และ test จะเรียก spim ผ่าน `tools\spim.cmd` ให้เอง (แปลง path Windows → WSL)
ถ้า Ubuntu ไม่ใช่ distro ค่าเริ่มต้นของ WSL ให้ตั้ง `$env:C2MIPS_WSL_DISTRO = "Ubuntu-24.04"`
และสำหรับ `--run` ให้ตั้ง `$env:SPIM = "<path ของ repo>\tools\spim.cmd"`

ทั้งสองทาง — gcc สำหรับรัน test (ไม่จำเป็นต่อการใช้งาน): ใช้รุ่นใหม่ (เช่น WinLibs หรือ MSYS2)
แล้วตั้ง `$env:GCC` ถ้าไม่อยู่ใน PATH —
**อย่าใช้ MinGW gcc 6.3** มันคำนวณ `-(INT_MIN / x)` ผิดภายใต้ `-fwrapv` ([Spec S23](Spec.md#13-ผลการ-spike-ที่ยืนยันแล้ว))

### macOS

ยังไม่ได้ทดสอบ ทางที่น่าจะง่ายสุด:

- **MARS** (ต้องมี Java เท่านั้น — ดูด้านล่าง) สำหรับรันไฟล์ `.s`
- SPIM: ใช้ [QtSpim](https://spimsimulator.sourceforge.net/) (GUI) หรือคอมไพล์ `spim` จาก source ของ SPIM;
  `--run` และ test ต้องการ `spim` แบบบรรทัดคำสั่งใน PATH (หรือตั้ง `SPIM=/path/to/spim`)

### MARS (ทุก OS)

```bash
curl -fsSLO https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar
# sha256: ac340b676ba2b62246b9df77e62f81ad4447bcfd329ab539716bcd09950b7096
java -jar Mars4_5.jar                       # GUI: File > Open > Assemble (F3) > Run (F5)
java -jar Mars4_5.jar nc ae2 prog.s         # บรรทัดคำสั่ง
```

MARS พิมพ์บรรทัดว่างเพิ่มหนึ่งบรรทัดตอนจบ และบน Windows ถ้า output มีภาษาไทยให้เพิ่ม
`-Dstdout.encoding=ISO-8859-1` หลัง `java` ([Spec S17, S20](Spec.md#13-ผลการ-spike-ที่ยืนยันแล้ว))

## 4. ใช้งาน

```bash
c2mips prog.c                    # ได้ prog.s ข้าง ๆ ไฟล์ต้นทาง
c2mips prog.c -o out.s -O1       # ตั้งชื่อเอง + optimize
c2mips prog.c --run              # คอมไพล์แล้วรัน (spim ถ้ามี ไม่งั้น MARS), ส่ง stdin/stdout/exit code ต่อ
spim -file prog.s                # หรือรันเอง (Windows + WSL: tools\spim.cmd -file prog.s)
java -jar Mars4_5.jar nc prog.s  # หรือรันบน MARS เอง
```

| ตัวเลือก | ความหมาย |
|---|---|
| `-o FILE` | ไฟล์ output (ค่าเริ่มต้น: ชื่อเดิม นามสกุล `.s`) |
| `-O0` / `-O1` | `-O0` (ค่าเริ่มต้น) อ่านง่ายตรงตาม template · `-O1` พับค่าคงที่และลดคำสั่ง ~32% ผลลัพธ์เหมือนกันทุกโปรแกรม |
| `--run` | รันไฟล์ที่ได้ ส่ง stdin, stdout และ exit code ต่อ |
| `--sim auto\|spim\|mars` | simulator ของ `--run` · `spim` หาจาก `$SPIM` แล้ว PATH · `mars` ใช้ `$MARS_JAR` + `java` · `auto` (ค่าเริ่มต้น) = spim ถ้าเจอ ไม่งั้น MARS |
| `--emit=tokens\|ast\|asm` | พิมพ์ผลของแต่ละ stage ออกหน้าจอแทนการเขียนไฟล์ |
| `--target spim\|fpga` | `spim` (ค่าเริ่มต้น) = SPIM/MARS · `fpga` = openmips / FPGA Studio ([§5](#5-ใช้กับ-fpga-studio)) |
| `--no-runtime` | ไม่ต่อท้าย runtime (`nCk`, panic) |

**Exit code ของ `c2mips`:** `0` สำเร็จ (มี warning ได้) · `1` compile error · `2` ใช้งานผิด / อ่านไฟล์ไม่ได้

**Error** แสดงแบบ gcc พร้อมรหัส ([Spec §10](Spec.md#10-diagnostics-ข้อความ-error)):

```text
prog.c:3:12: error[E020]: undeclared identifier 'x'
    return x + 1;
           ^
```

**ผลตอนรัน:** สิ่งที่ `main` return คือ exit code ของโปรแกรม · หารด้วยศูนย์หรือ `nCk` ล้น int →
พิมพ์ `runtime error: ...` แล้วจบด้วย exit code **70**

**รับ input:** `scanf("%d", &x)` อ่านจำนวนเต็ม **บรรทัดละหนึ่งตัว** — พิมพ์เองตอนรัน หรือ pipe เข้าไป เช่น
`printf '17\n-5\n' | c2mips prog.c --run` (PowerShell: `"17`n-5" | c2mips prog.c --run`)

**ดูโค้ดทีละคำสั่ง:** เปิดไฟล์ `.s` ใน MARS หรือ QtSpim แล้ว step ดู register และ stack ได้ —
ไฟล์จาก `-O0` มี comment บอกว่าแต่ละช่วงมาจากบรรทัด C ไหน

ตัวอย่างใน [`examples/`](examples): `hello_nck.c`, `example.c` (ตรงกับ Spec ภาคผนวก B),
`fact.c`, `fib.c`, `gcd.c`, `nck_user.c`

## 5. ใช้กับ FPGA Studio

`--target fpga` สร้าง assembly สำหรับ CPU `openmips` (5-stage pipeline) บนบอร์ด Nexys A7 ผ่าน IDE FPGA Studio
([Spec ADR-009, ADR-010](Spec.md#adr-009-target-fpga-openmips--fpga-studio--nexys-a7)) — target เดิม (`spim`) ไม่เปลี่ยน

### ตั้งค่าใน IDE

1. ติดตั้ง c2mips ตาม [§2](#2-ติดตั้ง-c2mips-ทุก-os) (Python 3.11+; ถ้ามี `.venv` ใน repo wrapper จะใช้ตัวนั้นเอง)
2. ใน FPGA Studio นำเข้า **`tools\c2mips_fpga.bat`** เป็น custom compiler
3. IDE จะเรียก `c2mips_fpga.bat <path>\fpga_studio_temp_src.c` — wrapper เขียน `<path>\fpga_studio_temp_src.c.s`
   **และ** พิมพ์ assembly เดียวกันออก stdout (ยังไม่รู้ว่า IDE อ่านทางไหน จึงทำทั้งสองทาง) ·
   error ออก stderr พร้อม exit code ไม่เป็น 0

รันเองจากบรรทัดคำสั่งก็ได้: `c2mips prog.c --target fpga -o prog.s` (`--run` ใช้ไม่ได้กับ target นี้)

### เขียนโปรแกรมสำหรับบอร์ด

ไม่มีระบบปฏิบัติการ จึง **ไม่มี `printf` / `scanf`** (ได้ `E032`) — ใช้ I/O ของบอร์ดแบบ memory-mapped:

```c
#define LED     (*(volatile int*)0xF0000000)   // เขียน
#define SWITCH  (*(volatile int*)0xF0000004)   // อ่าน
#define SEG7    (*(volatile int*)0xF0000008)   // เขียน

int main() {
    while (1) {
        int sw = SWITCH;
        LED = sw + 1;
        SEG7 = sw + 1;
    }
}
```

- `#define NAME ค่า` แบบไม่มี argument และเลขฐานสิบหก `0x...` ใช้ได้ทั้งสอง target
- I/O รับเฉพาะรูป `*(volatile int*)ที่อยู่` (ที่อยู่หารด้วย 4 ลงตัว) — pointer อื่นยังใช้ไม่ได้ (`E030`)
- ทุกการอ่าน/เขียน I/O เกิดจริงตามลำดับในโค้ด (`volatile`) — `-O1` ไม่ตัดและไม่รวม

### ผลลัพธ์บนบอร์ด

| เหตุการณ์ | SEG7 แสดง | จากนั้น |
|---|---|---|
| `main` return ค่า v (ไม่มี `return` = 0) | **v** (เขียนทับค่าที่โปรแกรมเขียน SEG7 ไว้เอง) | วนค้างที่ `_halt` |
| หารด้วยศูนย์ (`/` หรือ `%`) | `0xDEAD0001` | วนค้างที่ `_panic` |
| `nCk` เกิน int | `0xDEAD0002` | วนค้างที่ `_panic` |
| `while (1)` | ค่าที่โปรแกรมเขียนเอง | ไม่จบ |

### assembly ที่ได้

- มีแค่ label กับคำสั่งจริง — ไม่มี directive, ไม่มี comment, ไม่มี pseudo-instruction (`li`, `move`, `b`, `la`),
  ไม่มี `syscall` / `.data` และไม่ใช้ `$at` (assembler ของ IDE เปลี่ยนสิ่งที่ไม่รู้จักเป็น `0x00000000` เงียบ ๆ)
- ทุก branch/jump ตามด้วย `nop` (delay slot ของ openmips)
- เริ่มที่ PC `0x0000`: `lui $sp, 0x8001` → `jal f_main` → เขียนค่าที่คืนลง SEG7 → `_halt`
- แนบ runtime (`nCk`, panic) เฉพาะเมื่อโปรแกรมใช้ `nCk`, `/` หรือ `%`
- คอมไพเลอร์ตรวจทุกบรรทัดกับรายการคำสั่งที่อนุญาต
  (`addu addiu subu and andi or ori xor xori nor slt slti sltu sltiu sll srl sra lui lw sw beq bne bltz bgez blez bgtz j jal jr mult multu div divu mfhi mflo nop`)

### ทดสอบโดยไม่มีบอร์ด

`tests/fpga_sim.py` แปลง assembly เป็นรหัสเครื่อง MIPS32 จริงแล้วรันแบบมี delay slot และ I/O ของบอร์ด —
`pytest -q tests/test_fpga.py` ตรวจทั้งตัวอย่างที่ 1 ของ IDE, A1–A13, N1–N17 (เทียบกับ SPIM) และว่าถ้าไม่มี `nop` ผลจะผิด

### ต้องลองบน IDE จริง (ยังไม่ได้ทดสอบ)

1. นำเข้า `tools\c2mips_fpga.bat` เป็น custom compiler
2. `int main() { int a = 5; int b = a + 1; return b; }` → ตารางไม่มี `0x00000000` นอกจาก `nop` หลัง branch, sim จบที่ `_halt`, SEG7 = 6
3. ตัวอย่างที่ 1 (switch → LED) → เลื่อนสวิตช์แล้ว LED/SEG7 = ค่าสวิตช์ + 1
4. `return nCk(10, 3);` → SEG7 = 120
5. `return 1 / 0;` → SEG7 = `0xDEAD0001` แล้วค้าง
6. คำสั่งที่ยังไม่เคยเห็นใน IDE: `return 17 % 5 * 3 < 9;` (ใช้ `div` `mfhi` `mult` `mflo` `slt`) และ
   `int x = 5; return x == 5;` (ใช้ `sltiu`) — ไม่ควรมี `0x00000000` ในตาราง (ถ้ามี แปลว่า assembler ของ IDE ไม่รู้จักคำสั่งนั้น)

## 6. ภาษา MiniC โดยย่อ

ทุกโปรแกรม MiniC เป็น C99 ที่ gcc คอมไพล์ได้ — กฎเต็มอยู่ใน [Spec §4](Spec.md#4-ภาษาที่รองรับ-minic)

| มี | ไม่มี (ได้ error `E030` บอกตรง ๆ) |
|---|---|
| `int` (32 บิต), ตัวแปร local, block scope + shadowing; เลขฐานสิบ และฐานสิบหก `0x...` | `char` `float` `long` ฯลฯ, pointer, array, struct (ยกเว้น I/O `*(volatile int*)ที่อยู่` — [§5](#5-ใช้กับ-fpga-studio)) |
| `+ - * / %` (wrap แบบ `gcc -fwrapv`, หารปัดเข้าหาศูนย์) | `++` `--` `+=` ฯลฯ |
| `< <= > >= == !=`, `&& \|\| !` (short-circuit) | `break` `continue` `switch` `do` `goto` |
| `if/else`, `while`, `for` (init ประกาศตัวแปรได้) | ตัวแปร global, `#define` ที่มี argument, `#if` `#undef` และ preprocessor อื่น |
| ฟังก์ชัน ≤ 4 พารามิเตอร์, recursion, prototype | ฟังก์ชันที่พารามิเตอร์เกิน 4 ตัว (`E028`) |
| `printf` แบบ string literal กับ `%d` `%%` (ภาษาไทยได้) | `%s` `%x` ฯลฯ |
| `scanf("%d", &x)` | `scanf` รูปอื่น |
| `nCk(n, k)` ผลถูกต้องทุกค่าที่พอดี int | — |

`#include <stdio.h>`, `#include "c2mips.h"` และ `#include "nexys_a7.h"` ถูกข้ามไป (มีไว้ให้ gcc / IDE คอมไพล์ไฟล์เดียวกันได้) · `#define NAME ค่า` (ไม่มี argument) ใช้ได้

ค่าที่ C ไม่นิยาม c2mips นิยามให้ชัด: `x / 0` และ `x % 0` → panic exit 70 · `INT_MIN / -1` = `INT_MIN` ·
`INT_MIN % -1` = `0` · `nCk(n, k)` = 0 เมื่อ `k > n` หรือค่าติดลบ · `nCk` ที่เกิน 2,147,483,647 → panic

## 7. ทดสอบ

ต้องติดตั้งแบบ `pip install -e ".[dev]"` ก่อน

```bash
ruff check .
mypy --strict c2mips
pytest -q                                   # ~1,500 test, 2-3 นาที
```

test ที่ขาดเครื่องมือ (spim, gcc, MARS) จะถูก **skip** ไม่ใช่ fail — ดูจำนวน `skipped` ท้าย output ·
test ที่ต้องรันไฟล์ `.s` ใช้ spim ถ้ามี ไม่งั้นใช้ MARS (`$MARS_JAR`) — บังคับเลือกได้ด้วย
`C2MIPS_SIMULATOR=spim` หรือ `mars`

```bash
pytest -q -m random --random-count 500      # โปรแกรมสุ่ม: SPIM -O0 = SPIM -O1 = gcc = Python
MARS_JAR=/path/to/Mars4_5.jar pytest -q -m mars   # ความเข้ากันได้กับ MARS
python tests/random/gen.py --seed 42        # ดูโปรแกรมสุ่มของ seed นั้น
```

CI (GitHub Actions) รันทุก push และมี nightly สุ่ม 10,000 โปรแกรม + MARS — รายละเอียดใน
[docs/usage.md](docs/usage.md)

## 8. โครงสร้างโปรเจกต์

```text
README.md            คู่มือนี้
Spec.md              ข้อกำหนดภาษา, การออกแบบ, ADR, ผลการทดลองบน SPIM/MARS
c2mips/              ตัวคอมไพเลอร์: lexer -> parser -> sema -> fold (-O1) -> codegen -> emitter
c2mips/runtime/      runtime.s (nCk, panic) ต่อท้ายทุกไฟล์ output
include/c2mips.h     prototype ของ nCk (ใช้ทั้ง c2mips และ gcc)
ref/nck_ref.c        nCk ภาษา C ที่ทำงานเหมือน runtime.s ทุกตัวอักษร (oracle ของ test)
examples/            โปรแกรมตัวอย่าง
tests/               programs/ (golden), errors/ (compile error), random/, unit/, runtime/
tools/spim.cmd       ตัวเรียก spim ใน WSL สำหรับ Windows
tools/c2mips_fpga.bat  wrapper สำหรับ FPGA Studio (--target fpga)
docs/                usage.md (การทดสอบ), adr/ (Architecture Decision Records)
```

## 9. พัฒนาต่อ

อ่าน [Spec.md](Spec.md) ก่อนแก้อะไร แล้วยึดกติกาเหล่านี้ (รายละเอียด: Spec §14 และ `CLAUDE.md`)

- **ความหมายของภาษา** (Spec §4) และ **calling convention** (Spec §6) เปลี่ยนเมื่อมีเหตุผลเท่านั้น และต้องเขียน
  ADR ใหม่ใน `docs/adr/` (และใน Spec §7)
- ทุก feature ต้องมี **golden program** (`tests/programs/*.c` + `.expected`) และ **error test**
  (`tests/errors/*.c` + `.err`) — วิธีเขียนอยู่ใน [docs/usage.md](docs/usage.md)
- ไฟล์ `.s` ที่ emit ต้องเป็น **ASCII ล้วน** (ไบต์ > 0x7F ทำให้ SPIM ค้าง แม้อยู่ใน comment)
- `c2mips/runtime/runtime.s` ผ่านการทดสอบแบบ exhaustive แล้ว — **ห้ามเขียนใหม่** (มี test ตรวจว่าตรงกับ
  Spec ภาคผนวก A)
- ก่อนส่งงาน: `ruff check .`, `mypy --strict c2mips`, `pytest -q` ต้องผ่านทั้งหมด

**License:** ยังไม่ได้กำหนด — ต้องเลือกและเพิ่มไฟล์ `LICENSE` ก่อนเผยแพร่ให้คนอื่นนำไปใช้ต่อ
