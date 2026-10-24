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
5. [ภาษา MiniC โดยย่อ](#5-ภาษา-minic-โดยย่อ)
6. [ทดสอบ](#6-ทดสอบ)
7. [โครงสร้างโปรเจกต์](#7-โครงสร้างโปรเจกต์)
8. [พัฒนาต่อ](#8-พัฒนาต่อ)

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
| Windows 11 | ✅ test ครบทั้งชุด | ✅ ผ่าน WSL (`tools\spim.cmd`) | ✅ |
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

SPIM แบบบรรทัดคำสั่งไม่มีสำหรับ Windows จึงรันใน WSL:

```powershell
wsl --install -d Ubuntu-24.04
wsl -d Ubuntu-24.04 -- sudo apt install -y spim
```

c2mips และ test จะเรียก spim ผ่าน `tools\spim.cmd` ให้เอง (แปลง path Windows → WSL)
ถ้า Ubuntu ไม่ใช่ distro ค่าเริ่มต้นของ WSL ให้ตั้ง `$env:C2MIPS_WSL_DISTRO = "Ubuntu-24.04"`
และสำหรับ `--run` ให้ตั้ง `$env:SPIM = "<path ของ repo>\tools\spim.cmd"`

gcc สำหรับรัน test: ใช้รุ่นใหม่ (เช่น WinLibs หรือ MSYS2) แล้วตั้ง `$env:GCC` ถ้าไม่อยู่ใน PATH —
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
c2mips prog.c --run              # คอมไพล์แล้วรันบน spim, ส่ง stdout และ exit code ต่อ
spim -file prog.s                # หรือรันเอง (Windows: tools\spim.cmd -file prog.s)
```

| ตัวเลือก | ความหมาย |
|---|---|
| `-o FILE` | ไฟล์ output (ค่าเริ่มต้น: ชื่อเดิม นามสกุล `.s`) |
| `-O0` / `-O1` | `-O0` (ค่าเริ่มต้น) อ่านง่ายตรงตาม template · `-O1` พับค่าคงที่และลดคำสั่ง ~32% ผลลัพธ์เหมือนกันทุกโปรแกรม |
| `--run` | รันบน `spim` (หาจาก `$SPIM` แล้วจาก PATH) |
| `--emit=tokens\|ast\|asm` | พิมพ์ผลของแต่ละ stage ออกหน้าจอแทนการเขียนไฟล์ |
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

**รับ input:** `scanf("%d", &x)` อ่านจำนวนเต็ม **บรรทัดละหนึ่งตัว** ป้อนผ่าน stdin เช่น
`printf '17\n-5\n' | spim -file prog.s` — `--run` ยังไม่ส่ง stdin ต่อ ให้รัน spim เอง

**ดูโค้ดทีละคำสั่ง:** เปิดไฟล์ `.s` ใน MARS หรือ QtSpim แล้ว step ดู register และ stack ได้ —
ไฟล์จาก `-O0` มี comment บอกว่าแต่ละช่วงมาจากบรรทัด C ไหน

ตัวอย่างใน [`examples/`](examples): `hello_nck.c`, `example.c` (ตรงกับ Spec ภาคผนวก B),
`fact.c`, `fib.c`, `gcd.c`, `nck_user.c`

## 5. ภาษา MiniC โดยย่อ

ทุกโปรแกรม MiniC เป็น C99 ที่ gcc คอมไพล์ได้ — กฎเต็มอยู่ใน [Spec §4](Spec.md#4-ภาษาที่รองรับ-minic)

| มี | ไม่มี (ได้ error `E030` บอกตรง ๆ) |
|---|---|
| `int` (32 บิต), ตัวแปร local, block scope + shadowing | `char` `float` `long` ฯลฯ, pointer, array, struct |
| `+ - * / %` (wrap แบบ `gcc -fwrapv`, หารปัดเข้าหาศูนย์) | `++` `--` `+=` ฯลฯ |
| `< <= > >= == !=`, `&& \|\| !` (short-circuit) | `break` `continue` `switch` `do` `goto` |
| `if/else`, `while`, `for` (init ประกาศตัวแปรได้) | ตัวแปร global, `#define` และ preprocessor อื่น |
| ฟังก์ชัน ≤ 4 พารามิเตอร์, recursion, prototype | ฟังก์ชันที่พารามิเตอร์เกิน 4 ตัว (`E028`) |
| `printf` แบบ string literal กับ `%d` `%%` (ภาษาไทยได้) | `%s` `%x` ฯลฯ |
| `scanf("%d", &x)` | `scanf` รูปอื่น |
| `nCk(n, k)` ผลถูกต้องทุกค่าที่พอดี int | — |

`#include <stdio.h>` และ `#include "c2mips.h"` ถูกข้ามไป (มีไว้ให้ gcc คอมไพล์ไฟล์เดียวกันได้)

ค่าที่ C ไม่นิยาม c2mips นิยามให้ชัด: `x / 0` และ `x % 0` → panic exit 70 · `INT_MIN / -1` = `INT_MIN` ·
`INT_MIN % -1` = `0` · `nCk(n, k)` = 0 เมื่อ `k > n` หรือค่าติดลบ · `nCk` ที่เกิน 2,147,483,647 → panic

## 6. ทดสอบ

ต้องติดตั้งแบบ `pip install -e ".[dev]"` ก่อน

```bash
ruff check .
mypy --strict c2mips
pytest -q                                   # ~1,500 test, 2-3 นาที
```

test ที่ขาดเครื่องมือ (spim, gcc, MARS) จะถูก **skip** ไม่ใช่ fail — ดูจำนวน `skipped` ท้าย output

```bash
pytest -q -m random --random-count 500      # โปรแกรมสุ่ม: SPIM -O0 = SPIM -O1 = gcc = Python
MARS_JAR=/path/to/Mars4_5.jar pytest -q -m mars   # ความเข้ากันได้กับ MARS
python tests/random/gen.py --seed 42        # ดูโปรแกรมสุ่มของ seed นั้น
```

CI (GitHub Actions) รันทุก push และมี nightly สุ่ม 10,000 โปรแกรม + MARS — รายละเอียดใน
[docs/usage.md](docs/usage.md)

## 7. โครงสร้างโปรเจกต์

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
docs/                usage.md (การทดสอบ), adr/ (Architecture Decision Records)
```

## 8. พัฒนาต่อ

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
