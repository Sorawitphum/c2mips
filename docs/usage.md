# c2mips — วิธีใช้และวิธีทดสอบ

Spec.md คือ spec ฉบับเต็ม เอกสารนี้สรุปเฉพาะสิ่งที่ต้องใช้ทุกวัน

## ติดตั้ง

```bash
sudo apt install spim gcc        # Ubuntu 24.04: spim 8.0
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

**Windows:** ไม่มี spim ตัว native มีสองทาง
- **ไม่ใช้ WSL:** ติดตั้ง Java แล้วตั้ง `MARS_JAR` ชี้ไปที่ `Mars4_5.jar` — `c2mips --run` และ test ทุกตัว
  จะใช้ MARS เมื่อไม่เจอ spim (ดูวิธีดาวน์โหลดใน README §3)
- **ใช้ WSL:** ติดตั้ง spim ใน WSL (`apt install spim` หรือ `.deb` ของ Debian) แล้ว test จะใช้ shim
  `tools\spim.cmd` เอง (ลำดับ: `$SPIM` → `spim` บน PATH → shim ถ้า WSL มี spim) · distro อื่นที่ไม่ใช่ค่าเริ่มต้น:
  `C2MIPS_WSL_DISTRO=<ชื่อ>` · สำหรับ `c2mips --run` ให้ตั้ง `SPIM=<repo>\tools\spim.cmd`

simulator ของ test: spim ถ้าเจอ ไม่งั้น MARS — บังคับได้ด้วย `C2MIPS_SIMULATOR=spim|mars`

gcc ต้องเป็นรุ่นใหม่ (ตั้ง `$GCC` ได้): **MinGW gcc 6.3.0 คำนวณ `-(INT_MIN / x)` ผิดภายใต้ `-fwrapv`**
(Spec S23) จึงทำให้ random seed 371 ไม่ผ่านทั้งที่ c2mips ถูก

## ใช้งาน

```bash
c2mips prog.c -o prog.s          # คอมไพล์ (ไม่ใส่ -o ได้ prog.s)
c2mips prog.c -O1 --run          # -O1 แล้วรัน (spim ถ้ามี ไม่งั้น MARS), ส่ง stdin/stdout/exit code ต่อ
c2mips prog.c --run --sim mars   # บังคับใช้ MARS
c2mips prog.c --emit=tokens      # หรือ ast / asm: พิมพ์ผลกลางทางของแต่ละ stage
```

Exit code: `0` สำเร็จ (warning เช่น `W001` ยังได้ 0) · `1` compile error · `2` ใช้งานผิด / อ่านไฟล์ไม่ได้

ภาษา: Spec §4 · `scanf("%d", &x)` อ่านจำนวนเต็ม **บรรทัดละหนึ่งตัว** (S21)

## ทดสอบ

```bash
ruff check . && mypy --strict c2mips && pytest -q      # ต้องผ่านก่อนบอกว่าเสร็จ (CLAUDE.md)
```

| ชุด | ไฟล์ | ต้องมี |
|---|---|---|
| unit (lexer, parser, sema, fold, emitter, cvalue, CLI) | `tests/unit/` | — |
| runtime exhaustive nCk | `tests/runtime/` | simulator, gcc |
| golden programs / compile errors | `tests/programs/`, `tests/errors/` | simulator |
| differential vs gcc | `tests/test_differential.py` | gcc |
| `-O1` (golden asm, equivalence, −30%) | `tests/test_optimize.py` | simulator |
| random 3 ทาง | `tests/random/` | simulator, gcc |
| MARS compat | `tests/test_mars.py` | java, `MARS_JAR` |

"simulator" = spim หรือ MARS · test ที่ขาดเครื่องมือจะถูก skip (ไม่ fail) — ดูบรรทัด `s` ใน output ของ pytest

### เพิ่ม golden program

`tests/programs/x.c` + `x.expected` (บรรทัดแรก `exit: <code>` ที่เหลือคือ stdout ตรงตัว)
และ `x.stdin` ถ้าใช้ `scanf` · ถ้าผลขึ้นกับ UB ของ C (เช่นหารศูนย์) ให้บรรทัดแรกของ `x.c` เป็น
`// no-gcc-oracle: <เหตุผล>` และเพิ่มชื่อใน `test_only_documented_ub_cases_are_excluded`

### เพิ่ม compile-error test

`tests/errors/eNNN_xxx.c` + `.err` (stderr ตรงตัว รวมบรรทัด source และ `^`) — ถ้า `.err` มีแต่
warning โปรแกรมต้องคอมไพล์ผ่าน (exit 0)

## Random differential testing (Spec §9.4)

```bash
pytest -m random --random-count 500 --random-seed 1000     # seeds 1000..1499
python tests/random/gen.py --seed 1234                     # ดูโปรแกรมของ seed นั้น
python tests/random/gen.py --seed 1234 --expected          # และผลที่ต้องได้
```

ทุก seed ต้องให้ผลเหมือนกัน 4 ทาง: SPIM `-O0`, SPIM `-O1`, `gcc -fwrapv` + `ref/nck_ref.c`,
และ `cvalue.py` · ถ้าไม่ตรง test จะย่อโปรแกรมอัตโนมัติ บันทึกไว้ที่
`tests/random/failures/seed_<S>.c` และบอก seed ใน error · CI รัน 500 ต่อ push (seed เริ่มที่
run number × 500) และ nightly 10k (seed เริ่มที่วันที่ × 10000) — artifact `random-failures`

## ก่อน release: MARS 4.5

```bash
curl -fsSLO https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar
sha256sum Mars4_5.jar   # ac340b676ba2b62246b9df77e62f81ad4447bcfd329ab539716bcd09950b7096
MARS_JAR=$PWD/Mars4_5.jar pytest -m mars
```

รันมือ: `java -Dstdout.encoding=ISO-8859-1 -jar Mars4_5.jar nc ae2 prog.s` — `ae2` ทำให้
assemble error ได้ exit 2 (ไม่อย่างนั้น MARS ได้ 0) และ MARS พิมพ์บรรทัดว่างเพิ่ม 1 บรรทัดท้าย
output (S20)
