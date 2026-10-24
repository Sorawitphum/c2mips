# c2mips — คอมไพเลอร์ภาษา C (ชุดย่อย) → MIPS32 Assembly

> **สถานะ:** แผนออกแบบ v0.1 — ยังไม่เริ่ม implement · 24 ต.ค. 2026
> **โจทย์:** แปลงโปรแกรม C ที่คำนวณ `+ - * /` และ `nCk` (combination = n! / (k!(n−k)!)) เป็นไฟล์ `.s` ที่รันได้บน SPIM (และ MARS)
> **เครื่องหมาย ✅** = ข้อเท็จจริงที่ทดลองรันจริงแล้วบน SPIM 8.0 ระหว่างทำแผนนี้ (ดู [§13](#13-ผลการ-spike-ที่ยืนยันแล้ว))

---

## สารบัญ

1. [TL;DR](#1-tldr)
2. [Quick start (เป้าหมายเมื่อจบ M3)](#2-quick-start-เป้าหมายเมื่อจบ-m3)
3. [Requirements](#3-requirements)
4. [ภาษาที่รองรับ (MiniC)](#4-ภาษาที่รองรับ-minic)
5. [สถาปัตยกรรม](#5-สถาปัตยกรรม)
6. [Code generation (deep dive)](#6-code-generation-deep-dive)
7. [Architecture Decision Records](#7-architecture-decision-records)
8. [Grill-me: ถามจี้ตัวเอง-ตอบเอง](#8-grill-me-ถามจี้ตัวเอง-ตอบเอง)
9. [Testing strategy](#9-testing-strategy)
10. [Diagnostics (ข้อความ error)](#10-diagnostics-ข้อความ-error)
11. [แผนงาน (Milestones)](#11-แผนงาน-milestones)
12. [ความเสี่ยง](#12-ความเสี่ยง)
13. [ผลการ spike ที่ยืนยันแล้ว](#13-ผลการ-spike-ที่ยืนยันแล้ว)
14. [Conventions สำหรับผู้ร่วมพัฒนา](#14-conventions-สำหรับผู้ร่วมพัฒนา)
- [ภาคผนวก A: runtime.s](#ภาคผนวก-a-runtimes-ทดสอบแล้ว)
- [ภาคผนวก B: ตัวอย่าง example.c → example.s](#ภาคผนวก-b-ตัวอย่าง-examplec--examples-ทดสอบแล้ว)
- [ภาคผนวก C: c2mips.h และ ref/nck_ref.c](#ภาคผนวก-c-c2mipsh-และ-refnck_refc)
- [ภาคผนวก D: เอกสารอ้างอิง](#ภาคผนวก-d-เอกสารอ้างอิง)

---

## 1. TL;DR

- `c2mips` เขียนด้วย **Python 3.11+** (ตอนรันใช้แค่ stdlib; pytest/hypothesis ใช้ตอนทดสอบ)
- Pipeline: **Lexer → Parser (recursive descent) → AST → Sema → Fold (-O1) → Codegen → Emitter → `out.s` + `runtime.s`**
- Codegen v1 เป็นแบบ **accumulator (`$t0`) + stack** สำหรับค่าชั่วคราว — เน้นถูกต้องก่อน ค่อยเร็วทีหลัง
- `nCk(n, k)` เป็น **ฟังก์ชันใน runtime library** ที่เขียนด้วย MIPS มือ ใช้ **สูตรคูณสะสม + gcd** จึง **ไม่ overflow ระหว่างทาง** ตราบใดที่ผลลัพธ์จริงพอดี int32 และวนไม่เกิน 17 รอบ ✅
- Runtime error (หารด้วยศูนย์, nCk เกิน int32) → พิมพ์ข้อความแล้ว **exit code 70**
- โปรแกรมทดสอบทุกตัวเป็น C ที่ gcc คอมไพล์ได้ด้วย → ทำ **differential testing** เทียบกับ gcc ได้

| เรื่อง | ตัดสินใจ | อ่านต่อ |
|---|---|---|
| ภาษาที่ใช้เขียนคอมไพเลอร์ | Python, parser เขียนมือ | [ADR-001](#adr-001-ภาษาที่ใช้เขียนคอมไพเลอร์) |
| IR | ไม่มีใน v1 (AST → asm ตรง) | [ADR-002](#adr-002-ไม่มี-ir-ใน-v1) |
| อัลกอริทึม nCk | คูณสะสม + gcd | [ADR-003](#adr-003-อัลกอริทึม-nck) |
| วิธีเปิดให้ใช้ nCk | ฟังก์ชัน `int nCk(int, int)` ใน `c2mips.h` | [ADR-004](#adr-004-nck-เป็นฟังก์ชัน-library-ไม่ใช่-operator) |
| Simulator เป้าหมาย | SPIM 8.0 (CI) + ชุดคำสั่งร่วมกับ MARS 4.5 | [ADR-005](#adr-005-simulator-เป้าหมาย) |
| นโยบาย runtime error | panic + exit 70; `x / -1` = `-x` | [ADR-006](#adr-006-นโยบาย-runtime-error) |

---

## 2. Quick start (เป้าหมายเมื่อจบ M3)

> ✅ รันได้จริงตั้งแต่ M3 — คำสั่งและผลลัพธ์ด้านล่างถูกตรวจทุกครั้งโดย `tests/test_example.py::test_quick_start_as_written`
> (บน Windows: ใช้ spim ใน WSL ผ่าน `tools/spim.cmd` — ตั้ง `SPIM=tools\spim.cmd` ให้ `--run` หาเจอ)

```bash
sudo apt install spim             # ✅ Ubuntu 24.04 มีแพ็กเกจ spim 8.0
pip install -e ".[dev]"
c2mips examples/hello_nck.c -o hello_nck.s
spim -file hello_nck.s            # หรือ: c2mips examples/hello_nck.c --run
```

`examples/hello_nck.c`

```c
#include <stdio.h>
#include "c2mips.h"

int main(void) {
    printf("C(10,3) = %d\n", nCk(10, 3));
    return 0;
}
```

ผลลัพธ์ (SPIM พิมพ์ banner 5 บรรทัดก่อนเสมอ ✅ — `--run` ตัดออกให้)

```
C(10,3) = 120
```

### CLI

| คำสั่ง | ความหมาย |
|---|---|
| `c2mips in.c -o out.s` | คอมไพล์ (ไม่ระบุ `-o` → `in.s`) |
| `--emit=tokens\|ast\|asm` | พิมพ์ผลของแต่ละ stage เพื่อ debug |
| `-O0` (ค่าเริ่มต้น) / `-O1` | `-O1` = constant folding + leaf operand + ตัด guard ของตัวหารคงที่ |
| `--run` | คอมไพล์แล้วรัน `spim -stext 4194304` ส่งต่อ stdout และ exit code |
| `--no-runtime` | ไม่แนบ `runtime.s` (ใช้ทดสอบ runtime แยก) |

Exit code ของ `c2mips`: `0` สำเร็จ · `1` compile error · `2` ใช้งานผิด / อ่านไฟล์ไม่ได้

---

## 3. Requirements

### 3.1 Functional

| ID | ความต้องการ | Milestone |
|---|---|---|
| FR-1 | int literal ฐานสิบ (0..2147483647), วงเล็บ, unary `-` `+` | M1 |
| FR-2 | binary `+ - * /` ตาม precedence และ associativity ของ C | M1 |
| FR-3 | `printf` ที่ format เป็น string literal และมีแค่ `%d`, `%%` | M1 |
| FR-4 | `int main(void)` / `int main()` และ `return expr;` → exit code | M1 |
| FR-5 | ตัวแปร local `int`, initializer, assignment, block scope + shadowing | M2 |
| FR-6 | `nCk(n, k)` | M3 |
| FR-7 | `< <= > >= == !=`, `&& \|\| !`, `if/else`, `while`, `for` | M4 |
| FR-8 | ฟังก์ชันของผู้ใช้ (≤ 4 พารามิเตอร์ int), recursion, prototype | M4 |
| FR-9 | `%` (modulo) — stretch | M4 |
| FR-10 | `scanf("%d", &x)` รูปเดียว → syscall 5 — stretch | M6 |

### 3.2 Non-functional

| ID | ความต้องการ | วัดอย่างไร |
|---|---|---|
| NFR-1 | **Correctness:** stdout ตรงกับ `gcc -fwrapv` + `ref/nck_ref.c` สำหรับโปรแกรมที่ไม่มี UB | differential tests |
| NFR-2 | **Determinism:** input เดิมได้ `.s` เหมือนเดิมทุกไบต์ | compile ซ้ำแล้ว diff |
| NFR-3 | **Diagnostics:** ทุก error มี `file:line:col` + รหัส | error tests |
| NFR-4 | **ความเร็ว:** คอมไพล์ 1,000 บรรทัด < 1 วินาที | benchmark (ไม่ block CI) |
| NFR-5 | **Portability ของ output:** รันบน SPIM 8.0; MARS 4.5 (ตรวจใน M0) | E2E |
| NFR-6 | **Output เป็น ASCII ล้วน** (เหตุผลดู Q21) | unit test สแกนไบต์ > 0x7F |
| NFR-7 | ไม่มี runtime dependency นอก Python stdlib | `pyproject.toml` |

### 3.3 Constraints

- Target คือ MIPS32 แบบที่ **SPIM/MARS** เข้าใจ (ใช้ syscall ของ SPIM) — ไม่ใช่ Linux ELF หรือ GNU `as`
- ทีม 1–2 คน (งานวิชา Computer Architecture), เวลาประมาณ 3 สัปดาห์
- ใช้ convention เดียวกับเอกสารวิชา (COANotes2014 บทที่ 2 หัวข้อ 2.6 และตาราง 2.2): args `$a0–$a3`, ผลลัพธ์ `$v0`, `$fp` เป็น frame pointer, `$t*` ไม่ถูกรักษาค่าข้ามการเรียก

### 3.4 Out of scope (v1)

`char/long/unsigned/float/double`, pointer, array, struct, ตัวแปร global, preprocessor จริง (`#define`, `#if`), varargs ทั่วไป, การ link กับ object อื่น, o32 ABI เต็มรูปแบบ (home space 16 ไบต์), optimizer จริงจัง (register allocation)

---

## 4. ภาษาที่รองรับ (MiniC)

**กฎเหล็ก:** ทุกโปรแกรม MiniC ต้องเป็น C99 ที่ถูกต้อง (MiniC ⊂ C) — เพื่อให้ gcc เป็น oracle ได้

### 4.1 Lexical

- Keywords: `int void return if else while for`
- Identifier: `[A-Za-z_][A-Za-z0-9_]*`
- Integer literal: ฐานสิบเท่านั้น; ค่า > 2147483647 → `E003` (รวมถึง `-2147483648` — ให้เขียน `-2147483647 - 1`)
- String literal: ใช้ได้เฉพาะใน `printf`; escape ที่รองรับ `\n \t \\ \"`; ข้อความไทย/UTF-8 ได้ (emit เป็น `.byte`)
- Comment: `//` และ `/* */`
- บรรทัด `#include <stdio.h>` และ `#include "c2mips.h"` → ข้าม; `#` อื่นทั้งหมด → `E031`

### 4.2 Grammar (EBNF)

```ebnf
program     = { function } EOF ;
function    = "int" IDENT "(" params ")" ( block | ";" ) ;        (* ";" = prototype *)
params      = [ "void" | param { "," param } ] ;
param       = "int" IDENT ;
block       = "{" { stmt } "}" ;
stmt        = decl
            | "return" expr ";"
            | printf_stmt
            | block
            | "if" "(" expr ")" stmt [ "else" stmt ]              (* M4 *)
            | "while" "(" expr ")" stmt                           (* M4 *)
            | "for" "(" ( decl | [ expr ] ";" ) [ expr ] ";" [ expr ] ")" stmt   (* M4 *)
            | expr ";"
            | ";" ;
decl        = "int" declarator { "," declarator } ";" ;
declarator  = IDENT [ "=" expr ] ;
printf_stmt = "printf" "(" STRING { "," expr } ")" ";" ;
expr        = assign ;
assign      = IDENT "=" assign | logic_or ;                       (* right-assoc *)
logic_or    = logic_and { "||" logic_and } ;                      (* M4 *)
logic_and   = equality  { "&&" equality } ;                       (* M4 *)
equality    = relational { ( "==" | "!=" ) relational } ;         (* M4 *)
relational  = additive { ( "<" | "<=" | ">" | ">=" ) additive } ; (* M4 *)
additive    = term  { ( "+" | "-" ) term } ;                      (* left-assoc *)
term        = unary { ( "*" | "/" | "%" ) unary } ;               (* "%" = M4 *)
unary       = ( "-" | "+" | "!" ) unary | primary ;               (* "!" = M4 *)
primary     = INT | IDENT | call | "(" expr ")" ;
call        = IDENT "(" [ expr { "," expr } ] ")" ;
```

Parser ใช้ recursive descent หนึ่งฟังก์ชันต่อหนึ่งกฎ (precedence มาจากโครงสร้าง grammar โดยตรง ไม่ต้องใช้ตาราง)

### 4.3 ความหมาย (semantics)

| Construct | ความหมายใน c2mips | มาตรฐาน C | หมายเหตุ |
|---|---|---|---|
| `a + b`, `a - b`, `a * b` | wrap modulo 2³² (`addu`, `subu`, `mult`+`mflo`) | signed overflow = UB | เหมือน `gcc -fwrapv`; ห้ามใช้ `add`/`sub` เพราะ trap เมื่อ overflow |
| `a / b` | ปัดเศษเข้าหาศูนย์ | เหมือนกัน (C99) | ✅ SPIM: `-7/2 = -3`, `7/-2 = -3` |
| `a / 0` | panic `runtime error: division by zero`, exit 70 | UB | ✅ `div` ดิบของ SPIM ไม่ trap และ LO ค้างค่าเดิม |
| `INT_MIN / -1` | ได้ `INT_MIN` (คอมไพล์ `x / -1` เป็น `-x`) | UB | ✅ `div` ดิบของ SPIM ให้ LO ค้างค่าเดิม |
| `-a` | wrap (`-INT_MIN == INT_MIN`) | UB ที่ INT_MIN | |
| `a % b` (M4) | เศษมีเครื่องหมายตาม `a` (`-7 % 3 == -1`) — `div` แล้ว `mfhi` | เหมือนกัน (C99) | ✅ SPIM; ADR-008 |
| `a % 0` (M4) | panic `runtime error: division by zero`, exit 70 | UB | guard เดียวกับ `/` (ADR-008) |
| `INT_MIN % -1` (M4) | ได้ `0` (คอมไพล์ `x % -1` เป็น `0`) | UB | คู่กับ `x / -1 == -x` ให้ `(a/b)*b + a%b == a` ยังจริง (ADR-008) |
| `< <= > >= == !=`, `!` (M4) | ได้ `0` หรือ `1` แบบ signed | เหมือนกัน | ใช้ `slt`/`sltu`/`sltiu`/`xori` ซึ่งเป็นคำสั่งจริงทั้ง SPIM และ MARS |
| `a && b`, `a \|\| b` (M4) | short-circuit: ไม่ประเมิน `b` ถ้ารู้ผลแล้ว; ได้ `0` หรือ `1` | เหมือนกัน | ✅ `0 && nCk(34, 16)` ไม่ panic |
| ลำดับการประเมิน | ซ้ายไปขวา; arguments ทั้งหมดก่อนเรียก | unspecified | test ห้ามพึ่งลำดับ |
| ตัวแปรที่ยังไม่กำหนดค่า | ค่าขยะบน stack | indeterminate | ไม่ทดสอบ |
| `main` จบโดยไม่มี `return` | คืน 0 | C99 §5.1.2.2.3 | |
| ฟังก์ชันอื่นจบโดยไม่มี `return` | คืน 0 + warning `W001` | UB ถ้าใช้ค่า | M4 |

### 4.4 ความหมายของ `nCk`

`int nCk(int n, int k);` (ประกาศใน `c2mips.h`)

| เงื่อนไข | ผลลัพธ์ |
|---|---|
| `n < 0` หรือ `k < 0` หรือ `k > n` | `0` (ธรรมเนียมคณิตศาสตร์ C(n,k)=0 เมื่อ k>n) |
| `0 ≤ k ≤ n` และ C(n,k) ≤ 2147483647 | C(n,k) แบบ exact |
| C(n,k) > 2147483647 | panic `runtime error: nCk overflow`, exit 70 |

ตัวเลขขอบที่คำนวณยืนยันแล้ว ✅

- ทุก C(n,k) พอดี int32 เมื่อ **n ≤ 33** (ค่ากลางที่ใหญ่สุด C(33,16) = 1,166,803,110)
- n = 34: C(34,15) = 1,855,967,520 ยังพอดี แต่ C(34,16) = 2,203,961,430 ล้นแล้ว
- C(65536,2) = 2,147,450,880 พอดี; C(65537,2) = 2,147,516,416 ล้น
- **13! = 6,227,020,800 ล้น int32 แล้ว** → ใช้สูตร factorial ตรง ๆ ไม่ได้ (ดู Q10)

ชื่อ `nCk` เป็นชื่อสงวน: ประกาศ prototype ที่ตรง signature ได้ (มาจาก `c2mips.h`), แต่ถ้าเขียน body เอง → `E024`

### 4.5 `printf` ชุดย่อย

- format ต้องเป็น string literal; รองรับแค่ `%d` และ `%%`; อย่างอื่น → `E026`; จำนวน argument ไม่ตรง → `E027`
- แปลงตอน compile เป็น syscall `4` (print_string) และ `1` (print_int)
- **ประเมิน argument ทั้งหมดก่อนพิมพ์อะไรออกไป** (push ลง stack ก่อน) — รักษาความหมายของ C
- ใช้เป็น statement เท่านั้น (ไม่รองรับค่าที่ `printf` คืน)

---

## 5. สถาปัตยกรรม

### 5.1 Pipeline

```
source.c (UTF-8)
   │
   ▼
[1] Lexer ......... lexer.py      → list[Token]
   │
   ▼
[2] Parser ........ parser.py     → ast.Program
   │
   ▼
[3] Sema .......... sema.py       → ast.Program (ผูก Symbol แล้ว) + FuncInfo ต่อฟังก์ชัน
   │
   ▼
[4] Fold (-O1) .... fold.py       → ast.Program (พับค่าคงที่แล้ว)
   │
   ▼
[5] Codegen ....... codegen.py    → list[AsmLine]
   │
   ▼
[6] Emitter ....... emitter.py    → out.s  (ASCII ล้วน) + ต่อท้ายด้วย runtime/runtime.s

Diagnostics (diagnostics.py) — ทุก stage รายงานผ่านที่นี่ → stderr, exit 1
```

### 5.2 หน้าที่ของแต่ละส่วน

| Stage | Input → Output | รับผิดชอบ | ล้มเหลวด้วย |
|---|---|---|---|
| Lexer | text → tokens | ตัด token, ตำแหน่ง line:col, ข้าม comment/`#include`, ตรวจช่วง literal | E001–E003, E031 |
| Parser | tokens → AST | ตาม grammar §4.2, แตก format ของ printf เป็น segments | E010–E011, E025–E027 |
| Sema | AST → AST + symbols | scope/shadowing, จัด slot ให้ตัวแปร, ตรวจ arity, ตรวจ `main`, ชื่อสงวน `nCk` | E020–E030 |
| Fold | AST → AST | พับค่าคงที่ด้วย semantics ของ §4.3 (ห้ามพับ `/0` และ nCk ที่ล้น) | — |
| Codegen | AST → AsmLine | ตาม template §6 | — |
| Emitter | AsmLine → text | จัดรูปแบบ, intern string, บังคับ ASCII, นับคำสั่ง, ต่อ runtime | E040 |

**ขอบเขตระหว่าง stage:** แต่ละ stage เป็น pure function (`lex(src) -> list[Token]`, `parse(tokens) -> Program`, …) ไม่มี global state → unit test ทีละ stage ได้ และ `--emit=` ดึงผลกลางทางออกมาได้

### 5.3 Data model หลัก

```python
@dataclass(frozen=True)
class Pos:   file: str; line: int; col: int
@dataclass(frozen=True)
class Token: kind: TokKind; text: str; value: int | str | None; pos: Pos

# ast.py — ทุก node มี .pos
Program(functions: list[Function])
Function(name, params: list[str], body: Block | None)   # None = prototype
Block(stmts) | Decl(items: list[tuple[str, Expr | None]]) | Return(expr)
ExprStmt(expr) | If(cond, then, else_) | While(cond, body) | For(init, cond, step, body)
Printf(segments: list[str | FmtD], args: list[Expr])
IntLit(value) | Var(name) | Assign(name, value)
Unary(op, operand) | Binary(op, left, right) | Call(name, args)

# sema.py
Symbol(name, kind: LOCAL | PARAM | FUNC | BUILTIN, slot: int | None)  # slot i → offset -4*(i+1) จาก $fp
FuncInfo(name, n_params, n_slots, label)                                # label = "f_" + name
```

`Var`, `Assign`, `Call` มี field `resolved: Symbol | None` ที่ Sema เติมให้

### 5.4 โครงสร้างไดเรกทอรี

```
c2mips/
├── README.md
├── pyproject.toml
├── include/c2mips.h              # prototype ของ nCk (ใช้ทั้ง c2mips และ gcc)
├── c2mips/
│   ├── __main__.py               # CLI
│   ├── diagnostics.py
│   ├── tokens.py   lexer.py
│   ├── ast.py      parser.py
│   ├── sema.py     fold.py
│   ├── codegen.py  emitter.py
│   ├── cvalue.py                 # reference evaluator (wrap32, trunc div, nCk) — ใช้โดย fold + tests
│   └── runtime/runtime.s         # __rt_nCk, __rt_div0, __rt_panic
├── ref/nck_ref.c                 # nCk ภาษา C สำหรับ differential test บน host
├── examples/
├── tests/
│   ├── unit/                     # lexer, parser, sema, fold, emitter
│   ├── runtime/                  # exhaustive nCk บน SPIM
│   ├── programs/*.c + *.expected # E2E golden (stdout + exit code)
│   ├── errors/*.c + *.err        # compile-error golden
│   ├── random/gen.py             # random program generator
│   └── conftest.py               # run_spim(), run_gcc(), markers
└── docs/adr/                     # ADR ฉบับเต็มแยกไฟล์ (สำเนาจาก §7)
```

---

## 6. Code generation (deep dive)

### 6.1 การใช้ register

| Register | การใช้ใน c2mips | Preserved on call? (COANotes ตาราง 2.2) |
|---|---|---|
| `$t0` | accumulator — ผลของ expression ล่าสุด | no |
| `$t1` | operand ซ้ายหลัง pop | no |
| `$t2` | scratch (guard ของการหาร) | no |
| `$t3–$t7` | ใช้เฉพาะใน runtime | no |
| `$a0–$a3` | argument; argument ของ syscall | no |
| `$v0` | ค่าคืน; หมายเลข syscall | no |
| `$sp` | ยอด stack; push/pop ค่าชั่วคราว | yes |
| `$fp` | ฐานของ frame | yes (เก็บใน prologue) |
| `$ra` | return address | yes (เก็บใน prologue) |
| `$s0–$s7` | ไม่ใช้ใน v1 | yes |
| `$at`, `$k0`, `$k1`, `$gp` | ไม่แตะ (assembler / OS) | — |

### 6.2 Calling convention และ frame layout

```
 high address
 ┌───────────────────────────┐
 │ frame ของ caller ...       │
 ├───────────────────────────┤ ← $sp ของ caller ตอน jal
 │ saved $ra                 │  4($fp)
 │ saved $fp (ของ caller)     │  0($fp)   ← $fp
 ├───────────────────────────┤
 │ slot 0  (param / local)   │ -4($fp)
 │ slot 1                    │ -8($fp)
 │ ...                       │ -4N($fp)
 ├───────────────────────────┤ ← $sp หลัง prologue
 │ ค่าชั่วคราว (push/pop)      │  ขยับขึ้นลงระหว่างคำนวณ
 └───────────────────────────┘ ← $sp
 low address
```

```asm
f_name:                              # prologue
        addiu $sp, $sp, -8
        sw    $ra, 4($sp)
        sw    $fp, 0($sp)
        move  $fp, $sp
        addiu $sp, $sp, -4N          # N = params + every decl in the function
        sw    $a0, -4($fp)           # spill params into their slots right away
        ...
L_epi_name:                          # epilogue (every return branches here)
        move  $sp, $fp
        lw    $fp, 0($sp)
        lw    $ra, 4($sp)
        addiu $sp, $sp, 8
        jr    $ra
```

- ทุก declaration ได้ slot ของตัวเอง ไม่ reuse ข้าม block (ง่ายและพิสูจน์ได้ว่าไม่ชนกัน)
- **ต่างจาก o32 โดยตั้งใจ:** ไม่มี home space 16 ไบต์ และ `$sp` ไม่ align 8 ไบต์ระหว่าง push/pop — SPIM ไม่สนใจ; เราไม่ต้อง link กับ object ของ gcc
- พารามิเตอร์ตัวที่ 5 ขึ้นไป (หลัง M4): วางบน stack เหนือ `$fp` ตาม Elaboration ใน COANotes หัวข้อ 2.6.3 → param ตัวที่ 5 อยู่ที่ `8($fp)`

### 6.3 Template ของ expression (ผลอยู่ใน `$t0`)

| Node | Code |
|---|---|
| `IntLit v` | `li $t0, v` |
| `Var x` | `lw $t0, off_x($fp)` |
| `Assign x = e` | gen(e); `sw $t0, off_x($fp)` |
| `Unary - e` | gen(e); `subu $t0, $zero, $t0` |
| `Binary a ⊕ b` | gen(a); **push**; gen(b); **pop `$t1`**; ⊕ |
| ⊕ = `+` | `addu $t0, $t1, $t0` |
| ⊕ = `-` | `subu $t0, $t1, $t0` |
| ⊕ = `*` | `mult $t1, $t0` · `mflo $t0` |
| ⊕ = `/` | guard sequence §6.4 |
| `Call f(a₁..aₙ)` | gen(aᵢ)+push ทีละตัว; `lw $aᵢ` จาก stack; `addiu $sp,$sp,4n`; `jal label`; `move $t0, $v0` |
| `Return e` | gen(e); `move $v0, $t0`; `b L_epi_<fn>` |

push = `addiu $sp,$sp,-4` + `sw $t0,0($sp)` · pop = `lw $t1,0($sp)` + `addiu $sp,$sp,4`

**ทำไมปลอดภัยกับการเรียกฟังก์ชัน:** ค่าชั่วคราวทั้งหมดอยู่ในหน่วยความจำ ไม่ได้ค้างใน register → callee จะเขียนทับ `$t*` ก็ไม่เสียหาย ไม่ต้องมี logic caller-save เลย

### 6.4 การหาร

```asm
        beq   $t0, $zero, __rt_div0      # divisor == 0 -> panic
        li    $t2, -1
        bne   $t0, $t2, L<n>_div
        subu  $t0, $zero, $t1            # x / -1 == -x  (INT_MIN stays INT_MIN)
        b     L<n>_end
L<n>_div:
        div   $t1, $t0                   # 2-operand form = real instruction in SPIM/MARS
        mflo  $t0
L<n>_end:
```

- `-O1`: ตัวหารเป็นค่าคงที่ c ∉ {0, −1} → เหลือแค่ `div` + `mflo`; c = −1 → `subu`; c = 0 → คง jump ไป panic (ไม่พับ)
- `div $d, $s, $t` แบบ 3 operand ใน SPIM/MARS เป็น pseudo-instruction ที่แทรก check เอง ส่วน GNU `as` ตีความ `div` 2 operand เป็น macro ด้วย — อีกเหตุผลที่เราประกาศ target เป็น SPIM/MARS เท่านั้น

### 6.5 กฎการตั้งชื่อ label (ห้ามชนกัน)

| ชนิด | รูปแบบ | ตัวอย่าง |
|---|---|---|
| ฟังก์ชันของผู้ใช้ | `f_<name>` | `f_main`, `f_add` |
| epilogue | `L_epi_<name>` | `L_epi_main` |
| label ภายใน | `L<n>_<tag>` (ตัวนับต่อไฟล์) | `L7_div` |
| string | `__str<n>` (intern: ข้อความเดียวกันใช้ label เดียว) | `__str0` |
| runtime | `__rt_<name>` | `__rt_nCk`, `__rt_div0` |
| entry | `main` (stub) | |

**Invariant:** มีแค่ชื่อของผู้ใช้ที่ขึ้นต้นด้วย `f_` → ไม่มีทางชนกับชื่อของคอมไพเลอร์ ✅ จำเป็นจริง: label ชื่อ `add:` ทำให้ SPIM ฟ้อง parse error

### 6.6 String และกฎ ASCII

- ✅ **อักขระ non-ASCII (เช่นภาษาไทย) แม้อยู่ใน comment ทำให้ SPIM 8.0 ค้าง** → Emitter รับประกันว่า output เป็น ASCII ล้วน; comment ที่สะท้อนบรรทัด C จะ escape non-ASCII เป็น `ส`
- ✅ `.asciiz` ของ SPIM รองรับ `\n \t \"` แต่ **พิมพ์ `\\` ออกมาเป็นสองตัว** → กฎ: ใช้ `.asciiz` เมื่อ string มีแต่ ASCII พิมพ์ได้ (0x20–0x7E) ยกเว้น `\` บวก `\n`/`\t`; นอกนั้นใช้ `.byte` + `0` (ไบต์ ≥ 0x80 เขียนเป็นค่าลบ เช่น 0xE0 → `-32` — [ADR-007](#adr-007-ไบต์--0x80-ใน-byte-เขียนเป็นค่าลบ))
- ✅ ข้อความไทยผ่าน `.byte` (UTF-8 bytes) พิมพ์ออกมาถูกต้อง

### 6.7 Entry stub

```asm
        .text
        .globl main
main:   jal   f_main
        move  $a0, $v0
        li    $v0, 17            # exit2: exit code = return value of main
        syscall
```

- SPIM: `__start` ใน `exceptions.s` จะ `jal main` → เข้า stub; ✅ exit code จาก syscall 17 ออกมาเป็น exit status ของ process จริง
- MARS: ค่าเริ่มต้นเริ่มรันที่คำสั่งแรกของ `.text` → stub **ต้องเป็นคำสั่งแรกเสมอ** (ยืนยันใน M0)

### 6.8 Runtime library (`runtime/runtime.s`)

ต่อท้ายทุกไฟล์ output มี `__rt_nCk`, `__rt_div0`, `__rt_panic` เป็น leaf routine ใช้แค่ `$t0–$t7`, `$a0`, `$a1`, `$v0` ไม่แตะ stack — listing เต็มที่ทดสอบแล้วอยู่ใน [ภาคผนวก A](#ภาคผนวก-a-runtimes-ทดสอบแล้ว)

**คณิตศาสตร์ของ `__rt_nCk`:** ให้ k' = min(k, n−k) และ rᵢ = C(n−k'+i, i)

1. rᵢ = rᵢ₋₁ · (n−k'+i) / i — หารลงตัวเสมอ แต่ผลคูณก่อนหารอาจล้น
2. ให้ g = gcd(rᵢ₋₁, i) → gcd(i/g, rᵢ₋₁/g) = 1 และ i/g หาร rᵢ₋₁·(n−k'+i)/g ลงตัว ⇒ **i/g หาร (n−k'+i) ลงตัว**
3. ดังนั้น rᵢ = (rᵢ₋₁ / g) · ((n−k'+i) / (i/g)) — ผลคูณสุดท้าย **เท่ากับ rᵢ พอดี** ไม่มีค่ากลางที่ใหญ่กว่า
4. rᵢ ไม่ลดลง (เพราะ (n−k'+i)/i ≥ 1) ⇒ ล้นที่รอบใด ⇔ ผลลัพธ์สุดท้ายล้น → **ตรวจ overflow ได้ exact ไม่มี false positive**
5. ตรวจ overflow ด้วย `multu` แล้วดู `HI ≠ 0` หรือบิต 31 ของ `LO` เป็น 1 ✅ ทดสอบครบทั้งสองเส้นทาง
6. จำนวนรอบ: C(2i, i) ≤ rᵢ และ C(34,17) > INT_MAX ⇒ **วนไม่เกิน 17 รอบ** ไม่ว่า n จะใหญ่แค่ไหน ✅

### 6.9 Optimization (`-O1`, M5)

1. Constant folding ด้วย `cvalue.py` (wrap32, ปัดเข้าหาศูนย์) — **ห้ามพับ** `x/0` และ nCk ที่ล้น เพื่อให้พฤติกรรม runtime เหมือน `-O0`
2. พับ `nCk(const, const)` เมื่อผลพอดี int32
3. Leaf operand: ถ้า operand ขวาเป็น `IntLit`/`Var` → gen(a); `move $t1, $t0`; โหลด b เข้า `$t0` ตรง ๆ (ประหยัด push/pop = 4 คำสั่ง)
4. ตัด guard ของการหารเมื่อตัวหารเป็นค่าคงที่ (รวม `%` ตาม ADR-008: c = −1 → `li $t0, 0`; c = 0 → `b __rt_div0`)

เพิ่มใน M5 — ✅ ข้อ 1–4 อย่างเดียวลดได้แค่ 13.3% บน `examples/` (ไม่ถึงเกณฑ์ 30%) เพราะคำสั่งส่วนใหญ่อยู่ที่การ push argument ของ call/printf จึงขยายหลักการ leaf operand ข้อ 3 ไปที่จุดอื่น — calling convention (§6.2) ไม่เปลี่ยน:

5. Call ที่ argument **ทุกตัว** เป็น leaf → โหลดเข้า `$a0..$a3` ตรง ๆ (ไม่มีอะไรต้องกันจาก callee)
6. argument ของ `printf` ที่เป็น leaf → อ่านตอนพิมพ์แทนการ push — ทำเฉพาะเมื่อไม่มี argument ใดมี assignment จึงสังเกตไม่ได้ว่าอ่านช้ากว่า (§4.5; ตัวแปร local แก้จาก callee ไม่ได้เพราะไม่มี pointer/global)
7. `return <leaf>` → โหลดเข้า `$v0` ตรง ๆ; peephole ตัด `b L` ที่ตามด้วย `L:` ทันที
8. เงื่อนไขของ `if/while/for` ที่เป็น comparison → branch ตรง (`==` → `bne`, `!=` → `beq`, `<=`/`>=` ไม่ต้อง `xori`)

✅ ผล: 1,119 → 758 คำสั่ง (−32.3%) บน `examples/` (`tests/test_optimize.py` วัดทุกครั้ง)

**สัญญา:** `-O0` และ `-O1` ต้องให้ stdout + exit code เหมือนกันทุกโปรแกรม (property test) — ✅ ทุก golden, ทุก example, และ expression สุ่มเทียบ `cvalue.py` ทั้งสองระดับ

---

## 7. Architecture Decision Records

### ADR-001: ภาษาที่ใช้เขียนคอมไพเลอร์

**Status:** Accepted · **Date:** 2026-10-24 · **Deciders:** ทีมโปรเจกต์ (+ ผู้สอน ถ้าวิชากำหนดภาษา)

**Context:** เวลา ~3 สัปดาห์, ทีมเล็ก, ต้องการทดสอบจำนวนมาก (random, property-based) มากกว่าความเร็วของตัวคอมไพเลอร์

**Options Considered**

| มิติ | A: Python + parser เขียนมือ | B: C + flex/bison | C: Rust / OCaml |
|---|---|---|---|
| ความซับซ้อน | ต่ำ | กลาง (จัดการ memory, ไฟล์ generated) | กลาง–สูง |
| เวลาถึง M3 | สั้นสุด | กลาง | ยาว (ถ้าทีมไม่คุ้น) |
| เครื่องมือทดสอบ | pytest, hypothesis, subprocess ง่าย | ต้องเขียน harness เอง | ดี (cargo test / dune) แต่ต้องเรียน |
| ความคุ้นเคยของทีม | สูง | กลาง | ต่ำ |
| ข้อความ error ของ parser | ควบคุมเองได้เต็มที่ | bison ทำให้ดียาก | ดี |

**Decision:** A
**Consequences:** ง่ายขึ้น — iterate เร็ว, AST เป็น dataclass, ทดสอบ property ได้ทันที · ยากขึ้น — ไม่มี type check ตอน compile → บังคับ `mypy --strict` ใน CI · Revisit ถ้าวิชาบังคับให้เขียนด้วย C

### ADR-002: ไม่มี IR ใน v1

**Status:** Accepted · **Date:** 2026-10-24

**Context:** โจทย์คือ correctness ของ expression + nCk ไม่ใช่ประสิทธิภาพของโค้ด

| มิติ | A: AST → asm (accumulator + stack) | B: TAC IR + linear-scan regalloc | C: AST → asm + Sethi–Ullman บน `$t0–$t9` |
|---|---|---|---|
| ความซับซ้อน | ต่ำ | สูง | กลาง |
| expression ลึกไม่จำกัด | ได้ฟรี | ได้ (spill) | ต้อง spill เอง |
| การเรียกฟังก์ชันซ้อน | ไม่ต้อง caller-save | ต้องจัดการ | ต้อง save/restore |
| คุณภาพโค้ด | แย่ (~2–3× ยาว) | ดี | กลาง |

**Decision:** A — ส่วน `-O1` (leaf operand) กู้ส่วนที่แย่ที่สุดคืนมา
**Consequences:** โค้ดยาวกว่าที่คนเขียน แต่ตรวจด้วยตาได้ง่าย (เหมาะกับงานวิชา) · Revisit ถ้าต้องการ optimization จริงหรือหลาย target → แทรก TAC หลัง Sema โดยไม่กระทบ Lexer/Parser

### ADR-003: อัลกอริทึม nCk

**Status:** Accepted · **Date:** 2026-10-24

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: n! / (k!(n−k)!) ตรงสูตร | ตรงกับนิยามในโจทย์ | ✅ 13! ล้น int32 → C(13,1) ก็ผิดแล้ว |
| B: คูณสะสม r = r·(n−k+i)/i | ง่าย, O(k) | ✅ C(30,15)=155,117,520 พอดี แต่ค่ากลาง r·num = 2,326,762,800 ล้นที่ i=15; MIPS32 ไม่มี div 64/32 |
| **C: คูณสะสม + gcd** | ไม่มีค่ากลางล้น, ตรวจ overflow exact, ≤ 17 รอบ | โค้ดยาวขึ้น ~10 คำสั่ง |
| D: Pascal triangle (DP) | ไม่มีการหาร | O(n·k) เวลา + ต้องใช้ array/heap; n ใหญ่ไม่ได้ |
| E: ตารางค่าที่คำนวณไว้ | O(1) | n ≤ 33 ได้ แต่ C(65536,2) ใส่ตารางไม่ได้ |

**Decision:** C · สูตร n!/(k!(n−k)!) ยังเป็น **spec** และ oracle (`math.comb`) แต่ไม่ใช่ implementation
**Consequences:** ต้องมี proof สั้น ๆ (§6.8) และ test ทั้งสองเส้นทาง overflow

### ADR-004: nCk เป็นฟังก์ชัน library ไม่ใช่ operator

**Status:** Accepted · **Date:** 2026-10-24

| Option | ผลต่อ differential test | ผลต่อ parser |
|---|---|---|
| A: operator ใหม่ เช่น `n C k` | gcc คอมไพล์ไม่ได้ → เสีย oracle | ชนกับ identifier ชื่อ `C` |
| **B: `int nCk(int, int)` ใน `c2mips.h` + `runtime.s`** | gcc ลิงก์กับ `ref/nck_ref.c` ได้ | เป็นแค่ `Call` ปกติ |
| C: ให้ผู้ใช้เขียน nCk เองด้วย factorial | ได้ | ต้องรอ M4, และติดปัญหา 13! |

**Decision:** B — C กลายเป็นตัวอย่างใน `examples/` หลัง M4 (ใช้เทียบผลกับ builtin สำหรับ n ≤ 12)

### ADR-005: Simulator เป้าหมาย

**Status:** Accepted (ส่วน MARS ยืนยันใน M0 แล้ว — §13 S14–S20) · **Date:** 2026-10-24

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| **SPIM 8.0** | ✅ `apt install spim`, CLI headless, exit code ส่งต่อได้ | banner 5 บรรทัด, text segment 64 KB, ค้างเมื่อเจอ non-ASCII |
| **MARS 4.5** | นิยมในวิชา, GUI ดี | ต้องมี Java + ดาวน์โหลด jar; พฤติกรรม CLI ยังไม่ได้ตรวจ |
| QEMU + GNU toolchain | รันบน "เครื่องจริง" | ต้องใช้ o32 ABI เต็ม + crt + libc — เกินโจทย์ |

**Decision:** emit เฉพาะชุดคำสั่ง/directive ที่ทั้ง SPIM และ MARS รู้จัก; CI รันบน SPIM; ตรวจ MARS ใน M0 และก่อน release

### ADR-006: นโยบาย runtime error

**Status:** Accepted · **Date:** 2026-10-24

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: UB ตาม C (ไม่ check) | โค้ดสั้นสุด | ✅ SPIM ไม่ trap, LO ค้างค่าเก่า → ได้เลขผิดแบบเงียบ ๆ แย่ที่สุดสำหรับผู้เรียน |
| **B: panic + ข้อความ + exit 70** | ชัด, ทดสอบได้, ตรงกับ `nck_ref.c` | +5 คำสั่งต่อการหารที่ตัวหารไม่คงที่ |
| C: คืนค่า sentinel (−1) | ไม่หยุดโปรแกรม | −1 เป็นผลลัพธ์ปกติของ arithmetic ได้ → แยกไม่ออก |

**Decision:** B สำหรับ `/0` และ nCk overflow; `x / -1` นิยามเป็น `-x` · exit code 70 = `EX_SOFTWARE` ของ `sysexits.h` · ข้อความออก stdout เพราะ syscall ของ SPIM มีแค่ stdout

### ADR-007: ไบต์ ≥ 0x80 ใน `.byte` เขียนเป็นค่าลบ

**Status:** Accepted · **Date:** 2026-10-24 (M1)

**Context:** string ที่มี non-ASCII (เช่นไทย) ต้องออกเป็น `.byte` ของ UTF-8 (§6.6) ✅ MARS 4.5 รับค่า 128–255 ได้ถูก แต่พิมพ์ warning `out-of-range for a signed value` ลง **stdout** ทุกไบต์ ซึ่งปน output ของโปรแกรม (S17)

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: ค่าบวก 0–255 | อ่านง่าย ตรงกับ hex dump | MARS ปน warning ลง stdout |
| **B: ค่า signed −128…127** | ไบต์เดียวกันทุกตัว; ✅ ไม่มี warning บน MARS และ ✅ SPIM พิมพ์ถูก | อ่านยากกว่าเล็กน้อย |
| C: `.word` / แยก string ไทยเป็นตารางเอง | — | ซับซ้อนเกินจำเป็น |

**Decision:** B · ไม่กระทบ semantics (§4) หรือ calling convention (§6.2) เพราะไบต์ในหน่วยความจำเหมือนเดิมทุกตัว
**Consequences:** `tests/unit/test_emitter.py` ล็อกรูปแบบนี้; ✅ `printf_utf8` ให้ผลเหมือนกันบน SPIM, MARS และ gcc

### ADR-008: ความหมายของ `%`

**Status:** Accepted · **Date:** 2026-10-25 (M4)

**Context:** FR-9 เพิ่ม `%` แต่ §4.3 ยังไม่นิยาม C99 ให้ `(a/b)*b + a%b == a` และเศษมีเครื่องหมายตามตัวตั้ง แต่ `a % 0` และ `INT_MIN % -1` เป็น UB · `div` ของ MIPS ให้เศษใน HI ตามเครื่องหมายตัวตั้งอยู่แล้ว และไม่ trap ตอนหารศูนย์ (S5) — เหมือนปัญหาของ `/` ใน ADR-006

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: ใช้ `div` + `mfhi` ดิบ | สั้นสุด | หารศูนย์ได้เลขขยะเงียบ ๆ (เหตุผลเดียวกับ ADR-006 A) |
| **B: guard แบบเดียวกับ `/`** | `x % 0` → panic ข้อความเดียวกับ `/0`, exit 70; `x % -1` → `0` | +5 คำสั่งต่อ `%` ที่ตัวหารไม่คงที่ |
| C: เรียก routine ใหม่ใน runtime | โค้ดสั้นที่จุดเรียก | ต้องแก้ `runtime.s` ซึ่งห้ามเขียนใหม่ |

**Decision:** B · ใช้ `__rt_div0` เดิม (ไม่แตะ `runtime.s`) · `x % -1 == 0` คู่กับ `x / -1 == -x` (ADR-006) ทำให้ `(a/b)*b + a%b == a` จริงทุกค่า รวม `INT_MIN`
**Consequences:** golden `mod_by_zero` / `mod_int_min_minus_one` ติด `// no-gcc-oracle:` เพราะ gcc เป็น UB (x86 trap); `-O1` (M5) ตัด guard ได้เมื่อตัวหารเป็นค่าคงที่เหมือน `/`

---

## 8. Grill-me: ถามจี้ตัวเอง-ตอบเอง

> ใช้ `/grill-me` — ตั้งคำถามที่แทงจุดอ่อนของแผนให้มากที่สุด แล้วตอบเองโดยต้องจบด้วย **การตัดสินใจที่ชัด** ทุกข้อ ข้อที่มี ✅ คือคำตอบที่พิสูจน์ด้วยการรันจริง

### A. ขอบเขต

**Q1. "คอมไพเลอร์แปลง C" — C แค่ไหน? ทำไมไม่ทำ C เต็ม?**
C99 เต็มต้องมี preprocessor, ระบบ type, pointer, struct, ABI — ใหญ่กว่าโจทย์หลายเท่า โจทย์ต้องการแค่ `+ - * /` และ nCk → ต้องมีแค่ expression ของ int, ตัวแปร และทางแสดงผล
**ตัดสินใจ:** MiniC ตาม §4 และทุกโปรแกรม MiniC ต้องเป็น C ที่ gcc คอมไพล์ได้

**Q2. ถ้าโจทย์มีแค่ `+ - * /` ทำไมต้องมีตัวแปรและ printf? ไม่ใช่ scope creep หรือ?**
ไม่มี output = ทดสอบไม่ได้, ไม่มีตัวแปร = เขียนโปรแกรมที่สมจริงไม่ได้ แต่จำกัด printf แค่ `%d` ส่วน `if/while`/ฟังก์ชันของผู้ใช้ย้ายไป M4 ซึ่ง **ไม่จำเป็นต่อการผ่านโจทย์**
**ตัดสินใจ:** Definition of Done ของโจทย์ = M0–M3

**Q3. รองรับ type อื่นนอกจาก int ไหม?**
ไม่ int 32-bit signed อย่างเดียวทำให้ทุก expression ใช้ register เดียวได้และไม่มี conversion
**ตัดสินใจ:** เจอ `char/float/...` → `E030` พร้อมข้อความว่า "ยังไม่รองรับ" (ไม่ใช่ syntax error งง ๆ)

**Q4. ทำไม `-2147483648` ถึงเป็น error?**
ใน C มันคือ unary minus ของ `2147483648` ซึ่งไม่ใช่ `int` (เป็น `long`) ภาษาเรามีแค่ int ถ้ายอมรับก็เท่ากับโกหกเรื่อง type
**ตัดสินใจ:** `E003` พร้อมคำแนะนำ `-2147483647 - 1`

### B. ความหมาย (semantics)

**Q5. Overflow ของ `+ - *` ทำอย่างไร ในเมื่อ C บอกว่าเป็น UB?**
คำสั่ง `add`/`sub` ของ MIPS จะเกิด exception เมื่อ signed overflow ส่วน `addu`/`subu`/`mflo` wrap เงียบ ๆ
**ตัดสินใจ:** wrap modulo 2³² ทุกที่ (ตรงกับ `gcc -fwrapv` ที่ใช้เป็น oracle)

**Q6. หารด้วยศูนย์ล่ะ?**
✅ บน SPIM คำสั่ง `div` แบบ 2 operand ไม่ trap และ `LO` ยังเป็นค่าเก่า → ได้ตัวเลขผิดแบบไม่รู้ตัว
**ตัดสินใจ:** ใส่ guard ทุกการหาร → panic `runtime error: division by zero`, exit 70 (ADR-006)

**Q7. `INT_MIN / -1`?**
✅ บน SPIM ก็ได้ `LO` ค้างค่าเก่าเช่นกัน บน x86 คำสั่ง `idiv` จะ trap ถ้าตัวหารเป็นตัวแปร
**ตัดสินใจ:** `x / -1` คอมไพล์เป็น `-x` (wrap) ✅ ได้ `-2147483648` และ random generator หลีกเลี่ยงกรณีนี้เมื่อเทียบกับ gcc

**Q8. `f(a(), b())` ประเมินอะไรก่อน?**
C บอก unspecified
**ตัดสินใจ:** ซ้ายไปขวา; argument ของ printf ประเมินครบก่อนพิมพ์ตัวแรก; test ห้ามพึ่งลำดับนี้ (เพราะ gcc อาจไม่เหมือน)

**Q9. ทำไมแปลง printf ตอน compile ไม่เขียน printf ใน runtime?**
format เป็น literal จึงรู้ตอน compile ทั้งหมด การเขียน printf ใน asm ต้องทำ varargs + parse string ตอน runtime = ที่เกิดบั๊กเพิ่ม
**ตัดสินใจ:** lower เป็น syscall 4/1 ตอน compile; ไม่รองรับ format แบบ dynamic

### C. nCk

**Q10. ทำไมไม่ใช้สูตร n! / (k!(n−k)!) ตรง ๆ ตามโจทย์?**
✅ 13! = 6,227,020,800 > 2,147,483,647 → แค่ `nCk(13, 1)` (ซึ่งควรได้ 13) ก็ผิดแล้ว
**ตัดสินใจ:** สูตรเป็น spec/oracle ไม่ใช่ implementation (ADR-003)

**Q11. สูตรคูณสะสมธรรมดา `r = r*(n-k+i)/i` ไม่พอหรือ?**
✅ ไม่พอ: C(30,15) = 155,117,520 พอดี int32 แต่ค่ากลาง `r*num` = 2,326,762,800 ล้นที่ i = 15 และ MIPS32 ไม่มีคำสั่งหาร 64/32 บิต
**ตัดสินใจ:** หาร gcd ก่อนคูณ (§6.8)

**Q12. แน่ใจได้อย่างไรว่า (n−k+i) หารด้วย i/g ลงตัวเสมอ?**
i หาร rᵢ₋₁·(n−k+i) ลงตัว (เพราะผลคือ rᵢ ที่เป็นจำนวนเต็ม) หารทั้งสองข้างด้วย g ได้ i/g หาร (rᵢ₋₁/g)·(n−k+i) และ gcd(i/g, rᵢ₋₁/g) = 1 ⇒ i/g หาร (n−k+i) (Euclid's lemma)
**ตัดสินใจ:** ใส่ proof นี้เป็น comment ใน `runtime.s` และ ✅ ทดสอบ exhaustive 1,819 กรณี + overflow 84 กรณี

**Q13. `nCk(2000000000, 1000000000)` จะวนพันล้านรอบจนค้างไหม?**
ไม่ เพราะ rᵢ ≥ C(2i, i) และ C(34,17) > INT_MAX ⇒ ถ้าล้นจะเจอภายในรอบที่ 17; ถ้าไม่ล้นแปลว่า k' ≤ 16
**ตัดสินใจ:** ✅ ขอบบน 17 รอบ ไม่ต้องใส่ timeout ใน runtime

**Q14. `nCk(5, 7)` หรือ `nCk(-1, 0)` ได้อะไร?**
ธรรมเนียม C(n,k) = 0 เมื่อ k > n (`math.comb(5,7)` ก็ได้ 0) ค่าติดลบไม่มีนิยามเชิง combinatorics (`math.comb` โยน `ValueError`)
**ตัดสินใจ:** คืน 0 ทั้งหมด; oracle ใน test ห่อ `math.comb` ด้วยกฎเดียวกัน

**Q15. ล้นแล้วควร wrap เหมือน `*` ไหม จะได้สม่ำเสมอ?**
binomial ที่ wrap ไม่มีความหมายทางคณิตศาสตร์ และการหาค่า "จริง mod 2³²" ต้องใช้ bigint ใน asm
**ตัดสินใจ:** panic + exit 70 และ `ref/nck_ref.c` ทำแบบเดียวกันทุกตัวอักษร → differential test ยังใช้ได้

**Q16. ผู้ใช้ประกาศฟังก์ชันชื่อ `nCk` เองได้ไหม?**
prototype ที่ตรง signature ต้องยอมรับ (มาจาก `c2mips.h` และจำเป็นต่อ gcc)
**ตัดสินใจ:** prototype ตรง → ยอมรับ; signature ไม่ตรงหรือมี body → `E024`

### D. Codegen / Runtime

**Q17. ทำไมใช้ accumulator + stack ที่ช้า แทน register allocation?**
ถูกต้องง่ายกว่ามาก: expression ลึกเท่าไรก็ได้ และไม่ต้อง caller-save ตอนเรียกฟังก์ชัน (ADR-002)
**ตัดสินใจ:** v1 แบบนี้; `-O1` ทำ leaf operand ลด push/pop ส่วนใหญ่

**Q18. ถ้าผู้ใช้ตั้งชื่อฟังก์ชันชนกับ mnemonic หรือชื่อใน runtime?**
✅ label `add:` ทำให้ SPIM ฟ้อง syntax error ทันที
**ตัดสินใจ:** mangle เป็น `f_<name>` และชื่อภายในไม่มีวันขึ้นต้นด้วย `f_` (§6.5)

**Q19. SPIM เรียก `main` ให้อยู่แล้ว ทำไมต้องมี entry stub?**
(1) MARS เริ่มรันที่คำสั่งแรกของ `.text` (2) ต้องการให้ค่าที่ `main` คืนเป็น exit code
**ตัดสินใจ:** stub ชื่อ `main` อยู่บนสุดของ `.text`, `main` ของผู้ใช้กลายเป็น `f_main`; ✅ SPIM ส่ง exit code จาก syscall 17 ออกมาจริง

**Q20. ทำไม runtime ไม่ใช้ stack เลย?**
leaf routine ที่ใช้แค่ `$t*` ไม่มีทางทำ frame ของ caller พัง และ caller ของเราไม่เก็บค่าใน `$t*` ข้ามการเรียกอยู่แล้ว
**ตัดสินใจ:** runtime ห้ามแตะ `$sp`, `$fp`, `$s*` (ตรวจด้วย grep ใน unit test)

**Q21. เขียนภาษาไทยในโค้ด C (comment หรือข้อความใน printf) ได้ไหม?**
✅ **อันตราย:** SPIM 8.0 ค้างทันทีเมื่อเจออักขระ non-ASCII แม้อยู่ใน comment ของ `.s` ✅ แต่ถ้าเป็น `.byte` ของ UTF-8 จะพิมพ์ไทยออกมาถูกต้อง
**ตัดสินใจ:** Emitter บังคับ ASCII ล้วน (NFR-6), string ที่มี non-ASCII ใช้ `.byte`, test harness มี timeout 10 วินาทีเผื่อหลุด

**Q22. ถ้าโปรแกรมใหญ่ขึ้นเรื่อย ๆ จะพังตรงไหนก่อน?**
✅ text segment ดีฟอลต์ของ SPIM คือ 64 KB (16,384 คำสั่ง) เกินแล้วขึ้น `Invalid address (0x00410000)` ✅ แก้ได้ด้วย `spim -stext <bytes>` จุดถัดไปคือ branch แบบ PC-relative 16 บิต ไปได้ ±2¹⁵ คำสั่ง (COANotes บทที่ 2) → `beq ... __rt_div0` ที่อยู่ท้ายไฟล์อาจไกลเกิน
**ตัดสินใจ:** `--run` ใส่ `-stext 4194304` ให้; Emitter ฟ้อง `E040` เมื่อเกิน 32,000 คำสั่ง (ไกลเกินโจทย์มาก) แทนการทำ far branch

### E. Testing

**Q23. จะรู้ได้อย่างไรว่า output "ถูก"? ใช้อะไรเป็น oracle?**
มี 4 ตัว: (1) ไฟล์ `.expected` เขียนมือสำหรับโปรแกรมเล็ก (2) gcc `-fwrapv` + `nck_ref.c` (3) `cvalue.py` reference evaluator (4) `math.comb` สำหรับ nCk
**ตัดสินใจ:** ทุก oracle ถูกเทียบกันเองด้วย — ✅ `runtime.s` เทียบ `math.comb` ผ่าน, ✅ `nck_ref.c` เทียบ `math.comb` ผ่าน

**Q24. ถ้า `runtime.s` กับ `nck_ref.c` ผิดเหมือนกันทั้งคู่ (common-mode bug) ล่ะ?**
ทั้งสองถูกเทียบกับ `math.comb` (bigint ของ Python, implementation คนละสาย) **แยกกัน** ไม่ได้เทียบกันเองอย่างเดียว
**ตัดสินใจ:** exhaustive test ของทั้งคู่ชี้ไปที่ `math.comb` เสมอ

**Q25. random testing จะไปชน UB ของ gcc จนเกิด false alarm ไหม?**
ชนได้ถ้าไม่ระวัง: `/0`, `INT_MIN / -1` (x86 trap), nCk ล้น
**ตัดสินใจ:** generator ประเมินทุก sub-expression ด้วย `cvalue.py` ก่อน แล้วทิ้งโปรแกรมที่เข้ากรณีเหล่านี้; gcc คอมไพล์ด้วย `-fwrapv -O0`; บันทึก seed ทุกครั้ง

**Q26. SPIM ช้าและต้องติดตั้ง — unit test จะยังเร็วไหม?**
ตาม pyramid: unit test ไม่เรียก SPIM เลย (ms); test ที่ใช้ SPIM ติด marker `@pytest.mark.spim` และรวมหลายกรณีในโปรแกรมเดียว ✅ (exhaustive nCk 1,819 กรณีรันใน SPIM ครั้งเดียว — แต่ต้องใช้ data table + loop ไม่ใช่ straight-line เพราะเกิน 64 KB)
**ตัดสินใจ:** CI ติดตั้ง SPIM ผ่าน apt ✅

**Q27. ทดสอบ codegen ด้วยการเทียบ asm ทีละบรรทัดดีไหม?**
เปราะ — เปลี่ยน optimization นิดเดียว test แตกทั้งชุด
**ตัดสินใจ:** golden asm เฉพาะ 3–5 ไฟล์ (เพื่อ NFR-2 determinism) ที่เหลือทดสอบ **พฤติกรรม** (stdout + exit code)

### F. กระบวนการ

**Q28. อะไรคือ "เสร็จ"?**
**ตัดสินใจ:** Core DoD = M0–M3 เสร็จ + test ใน §9.3 ทุกข้อผ่าน + ส่วน Quick start ของ README รันได้จริงตามที่เขียน

**Q29. ความเสี่ยงใหญ่สุดคืออะไร?**
(1) ยังไม่ได้รันบน MARS จริง (2) M4 บานปลาย
**ตัดสินใจ:** M0 เป็น spike ตรวจ MARS ก่อนเขียนโค้ดคอมไพเลอร์บรรทัดแรก; M4 เป็น optional ตัดได้โดยไม่กระทบโจทย์

**Q30. ถ้าผู้สอนบังคับใช้ MARS อย่างเดียว?**
output อยู่ในชุดคำสั่งร่วมอยู่แล้ว
**ตัดสินใจ:** M0 รันชุดทดสอบเดิมด้วย `java -jar Mars4_5.jar nc file.s`; ถ้าพบความต่างค่อยเพิ่ม `--target mars` (ไม่ทำล่วงหน้า)

---

## 9. Testing strategy

### 9.1 Pyramid

```
            /  E2E บน SPIM  \         ~60+ golden + differential + random   (วินาที–นาที)
           /   Integration    \       runtime exhaustive, stage คู่ (parse+sema)
          /     Unit tests      \     ~300 tests: lexer, parser, sema, fold, emitter (ms)
```

### 9.2 ชั้นของการทดสอบ

| ชั้น | ครอบคลุม | เครื่องมือ | Oracle | เป้า | Milestone |
|---|---|---|---|---|---|
| Unit: lexer | token, ตำแหน่ง, ช่วง literal, comment, `#include` | pytest | เขียนมือ | ทุก TokKind + ทุก error ของ lexer | M1 |
| Unit: parser | precedence, associativity, รูป AST | pytest + AST เป็น s-expression | เขียนมือ | ทุกกฎ grammar + E010/E011 | M1–M4 |
| Unit: sema | scope, shadowing, slot, arity, prototype nCk | pytest | เขียนมือ | ทุก E02x | M2–M4 |
| Unit: fold | semantics ของ C | hypothesis | `cvalue.py` | 10k expression สุ่ม | M5 |
| Unit: emitter | ASCII ล้วน, กฎ `.asciiz`/`.byte`, intern | pytest | เขียนมือ | | M1 |
| Integration: runtime | `__rt_nCk` exhaustive + overflow + div0 | SPIM | `math.comb` | ✅ 1,819 ok + 84 overflow | M0/M3 |
| E2E golden | `programs/*.c` → stdout + exit code | SPIM | `*.expected` | ≥ 1 ต่อ feature, ≥ 60 โปรแกรม | M1–M4 |
| E2E differential | `.c` ชุดเดียวกันบน gcc | SPIM + gcc | gcc | ทุก golden ที่ไม่มี runtime error | M3 |
| E2E random | โปรแกรมสุ่ม | SPIM + gcc + Python | 3 ทางต้องตรงกัน | 500 / CI run, 10k nightly | M6 |
| Compile errors | `errors/*.c` → stderr + exit 1 | pytest | `*.err` | ทุกรหัส diagnostic | M1–M4 |
| Determinism | compile 2 ครั้ง → ไบต์เท่ากัน | pytest | — | ทุกโปรแกรม | M1 |
| -O equivalence | `-O0` vs `-O1` | SPIM | ซึ่งกันและกัน | ทุกโปรแกรม | M5 |
| MARS compat | ชุดย่อย 10 โปรแกรม | Java + MARS | `*.expected` | ผ่านทั้งหมด | M0, M6 |

### 9.3 Test case หลัก (Core DoD)

**Arithmetic**

| # | โปรแกรม/expression | คาดหวัง | ทดสอบอะไร |
|---|---|---|---|
| A1 | `1 + 2 * 3` | `7` | precedence |
| A2 | `(1 + 2) * 3` | `9` | วงเล็บ |
| A3 | `10 - 4 - 3` | `3` | left-assoc ของ `-` |
| A4 | `100 / 10 / 5` | `2` | left-assoc ของ `/` |
| A5 | `-7 / 2` | `-3` | ปัดเข้าหาศูนย์ ✅ |
| A6 | `7 / -2` | `-3` | ✅ |
| A7 | `2147483647 + 1` | `-2147483648` | wrap |
| A8 | `(-2147483647 - 1) / -1` | `-2147483648` | guard `-1` ✅ |
| A9 | `65536 * 65536` | `0` | `mflo` = 32 บิตล่าง |
| A10 | `- - 5` | `5` | unary ซ้อน |
| A11 | `1 / 0` | `runtime error: division by zero` + exit 70 | ✅ |
| A12 | `x / y` โดย `y = 0` ตอน runtime | เหมือน A11 | ตัวหารไม่คงที่ |
| A13 | `(n + k) * 2 - 7 / 2` โดย n=10, k=3 | `23` | ✅ ภาคผนวก B |

**nCk**

| # | Call | คาดหวัง | เหตุผล |
|---|---|---|---|
| N1 | `nCk(10, 3)` | `120` | ✅ ภาคผนวก B |
| N2 | `nCk(0, 0)` | `1` | ✅ |
| N3 | `nCk(5, 0)`, `nCk(5, 5)` | `1` | ขอบ ✅ |
| N4 | `nCk(5, 7)` | `0` | k > n ✅ |
| N5 | `nCk(-1, 0)`, `nCk(5, -1)`, `nCk(-2147483648, 0)` | `0` | ค่าลบ ✅ |
| N6 | `nCk(33, 16)` | `1166803110` | ค่ากลางใหญ่สุดที่พอดี ✅ |
| N7 | `nCk(34, 15)` | `1855967520` | ✅ |
| N8 | `nCk(34, 16)` | overflow, exit 70 | ✅ เส้นทาง bit31 |
| N9 | `nCk(65536, 2)` | `2147450880` | ✅ |
| N10 | `nCk(65537, 2)` | overflow, exit 70 | ✅ เส้นทาง bit31 |
| N11 | `nCk(100000, 2)` | overflow, exit 70 | ✅ เส้นทาง HI ≠ 0 |
| N12 | `nCk(2147483647, 1)` | `2147483647` | ✅ n ใหญ่สุด |
| N13 | `nCk(2147483647, 2147483646)` | `2147483647` | ✅ สลับเป็น k' = 1 |
| N14 | `nCk(30, 15)` | `155117520` | ✅ ค่าที่สูตรคูณธรรมดาพัง |
| N15 | `nCk(nCk(4, 2), 2)` | `15` | call ซ้อน |
| N16 | `nCk(n, k) + nCk(n, k + 1) == nCk(n + 1, k + 1)` | จริงทุก n ≤ 32 | Pascal (property) |
| N17 | `nCk(n, k) == nCk(n, n - k)` | จริง | symmetry (property) |

**Compile errors (ตัวอย่าง)**

| Source | stderr คาดหวัง |
|---|---|
| `int main(void){ return x; }` | `t.c:1:24: error[E020]: undeclared identifier 'x'` |
| `nCk(1)` | `error[E023]: 'nCk' expects 2 arguments, got 1` |
| `printf("%s", 1);` | `error[E026]: unsupported conversion '%s' (only %d and %%)` |
| `return -2147483648;` | `error[E003]: integer literal 2147483648 out of range; write -2147483647 - 1` |
| `int nCk(int n, int k) { return 0; }` | `error[E024]: 'nCk' is a builtin and cannot be defined` |

### 9.4 Random differential testing

```
gen.py --seed S ─▶ prog.c + expected (จาก cvalue.py)
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
   c2mips → spim            gcc -fwrapv -O0 prog.c ref/nck_ref.c → ./a.out
         │                        │
         └──────── เทียบ 3 ทาง (spim == gcc == expected) ────────┘
```

- สุ่ม expression tree ลึก ≤ 5; ใบเลือกจาก {0, 1, −1, 2, 7, INT_MAX, INT_MIN+1, สุ่ม} และตัวแปร
- operator: `+ - * /` และ `nCk(a, b)` ที่ a ∈ [0, 40], b ∈ [−2, 42]
- ประเมินทุก sub-expression ด้วย `cvalue.py` ก่อน → ทิ้งถ้าเจอ `/0`, `INT_MIN / -1`, nCk ล้น
- เมื่อพัง: บันทึก seed + ย่อโปรแกรมอัตโนมัติ (แทน subtree ด้วยใบ ทีละขั้น จนเหลือโปรแกรมเล็กสุดที่ยังพัง)

### 9.5 Test harness

✅ ทุกข้อด้านล่างมาจากการทดลองกับ SPIM 8.0

- ตัด banner: ลบทุกบรรทัดจนถึงและรวมบรรทัดที่ขึ้นต้นด้วย `Loaded:`
- รันด้วย `-stext 4194304` และ timeout 10 วินาที (กันค้างจาก non-ASCII หรือ infinite loop)
- เทียบ stdout ตรงตัว + exit code

```python
# tests/conftest.py
def run_spim(asm: Path, timeout: float = 10) -> tuple[str, int]:
    p = subprocess.run(["spim", "-stext", "4194304", "-file", str(asm)],
                       capture_output=True, text=True, timeout=timeout)
    lines = p.stdout.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("Loaded:")) + 1
    return "\n".join(lines[start:]), p.returncode
```

### 9.6 Coverage targets

- `c2mips/`: line ≥ 90%, branch ≥ 85% (pytest-cov)
- 100% ของรหัส diagnostic มี test
- 100% ของชนิด AST node ปรากฏใน E2E อย่างน้อย 1 โปรแกรม
- `runtime.s`: ทุก label ถูกเดินผ่าน — zero path (N4, N5), สลับ k (N13), loop + gcd (N6), overflow ทาง bit31 (N8), overflow ทาง HI (N11), div0 (A11)

### 9.7 CI (GitHub Actions)

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: sudo apt-get update && sudo apt-get install -y spim gcc
      - run: pip install -e ".[dev]"
      - run: ruff check . && mypy --strict c2mips
      - run: pytest -q --cov=c2mips --cov-branch --cov-fail-under=90
      - run: pytest -q -m random --random-count 500     # option กำหนดใน conftest.py
```

---

## 10. Diagnostics (ข้อความ error)

รูปแบบเดียวกับ gcc เพื่อให้ editor จับได้:

```
prog.c:3:12: error[E020]: undeclared identifier 'x'
    return x + 1;
           ^
```

| รหัส | Stage | ความหมาย |
|---|---|---|
| E001 | lexer | อักขระที่ไม่รู้จัก |
| E002 | lexer | comment หรือ string ไม่ปิด |
| E003 | lexer | integer literal เกิน 2147483647 |
| E010 | parser | คาดหวัง X แต่เจอ Y |
| E011 | parser | จบไฟล์ก่อนเวลา |
| E020 | sema | ใช้ identifier ที่ไม่ได้ประกาศ |
| E021 | sema | ประกาศซ้ำใน scope เดียวกัน |
| E022 | sema | เรียกฟังก์ชันที่ไม่ได้ประกาศ |
| E023 | sema | จำนวน argument ไม่ตรง |
| E024 | sema | นิยาม `nCk` เอง / prototype ไม่ตรง |
| E025 | parser | format ของ printf ไม่ใช่ string literal หรือใช้ printf ใน expression |
| E026 | parser | conversion ที่ไม่รองรับ |
| E027 | parser | จำนวน argument ของ printf ไม่ตรงกับ `%d` |
| E028 | sema | พารามิเตอร์เกิน 4 ตัว (จนกว่าจะทำ stack params) |
| E029 | sema | ไม่มี `main` หรือ signature ของ `main` ผิด |
| E030 | parser | feature/type ที่ยังไม่รองรับ (`char`, pointer, array, ...) |
| E031 | lexer | preprocessor directive ที่ไม่รองรับ |
| E040 | emitter | โปรแกรมเกิน 32,000 คำสั่ง |
| W001 | sema | ฟังก์ชันที่ไม่ใช่ `main` อาจจบโดยไม่มี `return` |

นโยบาย: lexer/parser หยุดที่ error แรก (ไม่ทำ error recovery ใน v1); sema รวบรวม error ทั้งหมดก่อนหยุด

---

## 11. แผนงาน (Milestones)

| Milestone | ส่งมอบ | Exit criteria | ประมาณการ |
|---|---|---|---|
| **M0** Spike + โครง | repo, `pyproject.toml`, CI, `conftest.run_spim`, ย้าย `runtime.s` จาก spike, ตรวจ MARS | CI เขียว (runtime tests), ผล MARS บันทึกใน §13 | 1 วัน |
| **M1** Expressions | lexer, parser (`+ - * /`, unary, วงเล็บ), printf `%d`, return, codegen, emitter, diagnostics | A1–A12 ผ่าน, error test ของ lexer/parser ครบ | 2–3 วัน |
| **M2** ตัวแปร | decl, assign, scope, frame slot | golden ที่มีตัวแปร + A13, E020/E021 | 1–2 วัน |
| **M3** nCk | resolve builtin, ตรวจ prototype, codegen ของ call, `c2mips.h`, differential harness | N1–N17 ผ่าน, differential ผ่านทุก golden | 1–2 วัน |
| — | **Core DoD (ผ่านโจทย์)** | | **5–8 วัน** |
| **M4** Control flow + ฟังก์ชัน | comparison, `&& \|\| !`, `if/while/for`, ฟังก์ชัน ≤ 4 params, recursion, `%`, W001 | ตัวอย่าง fact/fib/gcd; nCk แบบผู้ใช้เขียนเอง = builtin ทุก n ≤ 12 | 3–4 วัน |
| **M5** `-O1` | fold, leaf operand, ตัด guard | -O equivalence ผ่าน; จำนวนคำสั่งลด ≥ 30% บนชุดตัวอย่าง | 2 วัน |
| **M6** Hardening | random generator + shrinker, รัน MARS ก่อน release, `scanf` (stretch), เอกสาร | random 500/run เขียว, nightly 10k | 2 วัน |

รวม ≈ 12–16 วันทำงาน

### Checklist ราย milestone

**M0**
- [x] โครง repo ตาม §5.4, `ruff` + `mypy --strict` ผ่านตั้งแต่วันแรก
- [x] `tests/runtime/`: ย้าย exhaustive nCk จาก spike (data table + loop)
- [x] ตรวจ MARS 4.5 (ผลใน §13 S14–S20): (1) เริ่มที่คำสั่งแรกของ `.text` จริงไหม (2) syscall 17 ส่ง exit code ไหม (3) `.asciiz` escape เหมือน SPIM ไหม (4) non-ASCII ทำอะไร (5) `div` 2 operand ไม่ใส่ check จริงไหม
- [ ] CI บน GitHub Actions

**M1**
- [x] `tokens.py`, `lexer.py` + test ตำแหน่ง line:col
- [x] `parser.py` (additive/term/unary/primary) + AST snapshot test — parse grammar §4.2 ทุกกฎที่ไม่ได้ติด M4; ส่วน M4 → `E030`
- [x] `codegen.py`: IntLit, Unary, Binary, Return, Printf
- [x] `emitter.py`: entry stub, intern string, กฎ ASCII, ต่อ runtime
- [x] `diagnostics.py` + `errors/*.c` — ระหว่าง M1 sema รายงานตัวแปร (M2) / call (M3) / ฟังก์ชันของผู้ใช้ (M4) เป็น `E030` "not supported yet"

**M2**
- [x] `sema.py`: scope stack, Symbol, slot allocation, FuncInfo — scope ของตัวแปรเริ่มทันทีหลัง declarator (C99 §6.2.1p7) และ param อยู่ scope เดียวกับ block นอกสุดของฟังก์ชัน (§6.2.1p4); call (M3) / ฟังก์ชันของผู้ใช้ (M4) ยังเป็น `E030`
- [x] Decl/Assign/Var ใน codegen, frame prologue/epilogue — ภาคผนวก B (ตัด printf ที่เรียก nCk) ตรงทีละคำสั่ง

**M3**
- [x] builtin table `{"nCk": BuiltinFunc(arity=2, label="__rt_nCk")}` — E022 (ไม่ได้ประกาศ / ตัวแปรบัง), E023 (arity)
- [x] ตรวจ prototype ของ nCk (E024)
- [x] `run_gcc()` ใน conftest + differential test — ทุก golden ยกเว้น 4 ไฟล์ที่ผลขึ้นกับ UB ของ C (ติด `// no-gcc-oracle:`); `nck_ref.c` เทียบ `math.comb` แยก (S13)
- [x] อัปเดต Quick start ให้เป็นผลจริง — ภาคผนวก B ทั้งไฟล์ตรงทีละคำสั่ง

**M4** (§11 ไม่มี checklist เดิม — รายการนี้สรุปสิ่งที่ส่งมอบ)
- [x] parser: `\|\| && == != < <= > >=` และ `%` `!` ตามลำดับชั้นของ §4.2 (หนึ่ง method ต่อหนึ่งกฎ); `if/else` (else จับ `if` ที่ใกล้สุด), `while`, `for` (init เป็น decl ได้); declaration เป็นตัว body ของ if/while/for ไม่ได้ (เหมือน C) → `E010`
- [x] codegen: comparison เป็น 0/1 ด้วยคำสั่งจริง, `&& \|\|` short-circuit, `%` ตาม ADR-008; label `L<n>_else/endif/while/wend/for/fend`
- [x] ฟังก์ชันของผู้ใช้ ≤ 4 params (`E028`), recursion, prototype; param spill เข้า slot ทันทีหลัง prologue (§6.2); ต้องประกาศก่อนเรียก (C99) → `E022`; นิยามซ้ำ / prototype ไม่ตรง → `E021`; `E023` สำหรับ arity
- [x] `W001` เมื่อท้ายฟังก์ชัน (ที่ไม่ใช่ `main`) ไปถึงได้ — ตรวจตาม flow (if/else ทั้งสองทาง, loop ที่เงื่อนไขเป็นค่าคงที่ไม่ใช่ 0 ไม่มีวันจบเพราะไม่มี `break`); คอมไพล์ผ่าน exit 0 และฟังก์ชันคืน 0
- [x] `examples/fact.c`, `fib.c`, `gcd.c` และ `nck_user.c` (n!/(k!(n−k)!) ที่ผู้ใช้เขียน = builtin ทุก n ≤ 12) ผลตรงกับ Python และ gcc
- [x] ไม่มี placeholder `E030 … not supported yet` เหลือ — `E030` ใช้เฉพาะสิ่งที่อยู่นอก MiniC (type อื่น, pointer, array, `++`, `+=`, `break`, …)

**M5** (§11 ไม่มี checklist เดิม — รายการนี้สรุปสิ่งที่ส่งมอบ)
- [x] `cvalue.py` (wrap32, หารปัดเข้าหาศูนย์, `%` ตาม ADR-008, nCk) — เทียบกับนิยามอิสระ (ctypes int32, `Fraction`, `math.comb`) ด้วย hypothesis
- [x] `fold.py` (AST → AST ใหม่, ไม่แก้ input) — 10k expression สุ่ม (hypothesis) ยืนยันว่าความหมายไม่เปลี่ยน, ไม่พับ `/0` `%0` และ nCk ที่ล้น, `0 && e` / `1 \|\| e` พับได้เพราะ `e` ไม่ถูกประเมินอยู่แล้ว
- [x] codegen `-O1`: §6.9 ข้อ 3–8; golden asm ของ `example_m1.c` และภาคผนวก B (`tests/golden/*_O1.s`)
- [x] -O equivalence: ทุก golden, ทุก example (SPIM) และ expression สุ่ม 6 seed × 40 ทั้ง `-O0`/`-O1` เทียบ `cvalue.py`; ✅ ตัวอย่างหลักรันบน MARS ด้วย
- [x] จำนวนคำสั่งลด 32.3% บน `examples/` (เกณฑ์ ≥ 30%)

---

## 12. ความเสี่ยง

| ความเสี่ยง | โอกาส | ผลกระทบ | การรับมือ |
|---|---|---|---|
| MARS ทำงานต่างจาก SPIM (entry, exit2, escape) | กลาง | กลาง | spike M0; ใช้ชุดคำสั่งร่วม; `--target mars` ถ้าจำเป็น |
| ✅ non-ASCII ทำ SPIM ค้าง | สูง (ผู้ใช้ไทย) | สูง (ค้างเงียบ) | Emitter ASCII ล้วน + test + timeout |
| ✅ text segment 64 KB | ต่ำ | กลาง | `-stext` ใน `--run`, E040 |
| UB ทำให้ differential test แจ้งผิด | กลาง | ต่ำ | กรองด้วย `cvalue.py`, `-fwrapv` |
| Scope creep (pointer, array) | กลาง | สูง | รายการ out-of-scope + E030 |
| branch `beq` ไกลเกิน ±2¹⁵ คำสั่ง | ต่ำ | กลาง | E040 ที่ 32,000 คำสั่ง |
| common-mode bug ใน ref และ runtime | ต่ำ | สูง | ทั้งคู่เทียบ `math.comb` แยกกัน |
| M4 บานปลายกินเวลา core | กลาง | กลาง | M4 optional, core DoD ไม่ขึ้นกับมัน |

---

## 13. ผลการ spike ที่ยืนยันแล้ว

สภาพแวดล้อม: Ubuntu 24.04, `spim 8.0+dfsg-7` (apt), gcc ของ host, Python 3.13 — 24 ต.ค. 2026

| # | ข้อเท็จจริง | ผลต่อการออกแบบ |
|---|---|---|
| S1 | SPIM พิมพ์ banner 5 บรรทัด จบด้วย `Loaded: /usr/lib/spim/exceptions.s` | harness ตัด banner |
| S2 | syscall 17 (exit2) → exit status ของ process จริง | exit code ทดสอบได้ |
| S3 | `runtime.s` ให้ผลตรง `math.comb` ทั้ง 1,819 กรณี (n ∈ [−1, 40], k ∈ [−2, 42] + ค่าใหญ่) | ADR-003 ใช้ได้ |
| S4 | ทุกกรณีที่ควรล้น 84 กรณี → ข้อความถูก + exit 70; ทั้งเส้นทาง bit31 (34,16 · 65537,2) และ HI ≠ 0 (100000,2) | ADR-006 |
| S5 | `div` ดิบ: `-7/2 = -3`; `INT_MIN/-1` และ `5/0` ไม่ trap, LO ค้างค่าเก่า | ต้องมี guard §6.4 |
| S6 | guard sequence: `INT_MIN / -1` → `-2147483648`, หารศูนย์ → panic exit 70 | §6.4 ถูกต้อง |
| S7 | label ชื่อ `add` → SPIM syntax error | name mangling §6.5 |
| S8 | **อักขระไทยใน comment → SPIM ค้าง**; ไทยผ่าน `.byte` พิมพ์ถูก | NFR-6, §6.6 |
| S9 | `.asciiz`: `\n \t \"` ถูก แต่ `\\` ออกมาสองตัว | กฎ `.asciiz`/`.byte` |
| S10 | text segment ดีฟอลต์ 64 KB (เกินแล้ว `Invalid address (0x00410000)`); `-stext 1000000` แก้ได้ | `--run`, Q22, Q26 |
| S11 | `example.s` (ภาคผนวก B) บน SPIM ให้ stdout ตรงกับ gcc + `nck_ref.c` ทุกไบต์ | ยืนยัน frame + call + printf lowering |
| S12 | recursion `fact(12)` ตาม frame layout §6.2 ได้ `479001600` | ยืนยัน prologue/epilogue/param slot |
| S13 | `nck_ref.c` ตรง `math.comb` บน n ∈ [−1, 33], k ∈ [−2, 35] และ `nCk(65537,2)` → exit 70 | oracle ของ differential |

**MARS (M0):** Windows 11, Java 21.0.5, `Mars4_5.jar` v.4.5.1 (sha256 `ac340b676ba2b62246b9df77e62f81ad4447bcfd329ab539716bcd09950b7096`) รันด้วย `java -jar Mars4_5.jar nc file.s`; ฝั่งเทียบคือ `spim 8.0+dfsg-7` (Debian `.deb`) ใน WSL2 — 24 ต.ค. 2026

| # | ข้อเท็จจริง | ผลต่อการออกแบบ |
|---|---|---|
| S14 | (1) MARS เริ่มรันที่ **คำสั่งแรกของ `.text`** ไม่ใช่ที่ `main` (ยกเว้นใส่ option `sm`); SPIM เข้าที่ `main` ผ่าน `__start` | ✅ stub §6.7 ต้องอยู่บนสุดของ `.text` |
| S15 | (2) syscall 17 → exit status ของ process `java` จริง (ทดสอบ 42 และ 70); ถ้าตกท้าย `.text` โดยไม่ exit: MARS exit 0 เงียบ ๆ, SPIM เตือนทาง stderr แล้ว exit 0 | ✅ exit code ทดสอบได้บน MARS; stub จบด้วย syscall 17 เสมอ |
| S16 | (3) `.asciiz` บน MARS: `\n \t \"` ถูก แต่ `\\` ได้ `\` **ตัวเดียว** (ต่างจาก SPIM ที่ได้สองตัว — S9; และ `"[\\]"` ทำ SPIM parse error) · `.byte 92` ได้ `\` ตัวเดียวทั้งคู่ | ✅ กฎ §6.6 (มี `\` → `.byte`) จำเป็นและใช้ได้ทั้งคู่ |
| S17 | (4) non-ASCII บน MARS: ไทยใน comment **ไม่ค้าง** (ต่างจาก S8); ไทยใน `.asciiz` **เพี้ยน** (MARS เก็บแค่ไบต์ล่างของแต่ละอักขระ); `.byte` ค่า 128–255 เก็บถูกแต่ MARS พิมพ์ warning `out-of-range for a signed value and possibly truncated` **ลง stdout** ทุกไบต์; `.byte` ค่าลบ (เช่น 0xE0 → `-32`) ได้ไบต์เดียวกัน ไม่มี warning และ SPIM พิมพ์ไทยถูก · stdout ของ Java บน Windows แปลงไบต์ ≥ 0x80 เป็น `?` ต้องรันด้วย `-Dstdout.encoding=ISO-8859-1` จึงได้ไบต์ตรง | ASCII ล้วน (NFR-6) ยังจำเป็นเพราะ SPIM · Emitter เขียนไบต์ ≥ 0x80 ใน `.byte` เป็นค่าลบ (ADR-007) |
| S18 | (5) `div $t1, $t0` บน MARS เป็นคำสั่งจริง 1 คำสั่ง (4 ไบต์ เท่ากับ SPIM) ไม่แทรก check: `5/0` ไม่ trap, LO ค้างค่าเก่า (เหมือน SPIM); `INT_MIN/-1` MARS ได้ `-2147483648` แต่ SPIM LO ค้างค่าเก่า; `-7/2 = -3` ทั้งคู่ | ✅ ผลดิบต่างกัน แต่ guard §6.4 ให้ผลเดียวกันทั้งคู่ |
| S19 | `runtime.s` บน MARS: exhaustive 1,819 กรณีตรง `math.comb` (0.6 วินาที); overflow (34,16 · 65537,2 · 100000,2 · 2147483647,1073741823) → ข้อความถูก + exit 70; `__rt_div0` → exit 70; `example.s` (ภาคผนวก B) → `a = 23` / `C(10,3) = 120` exit 0 | ✅ S3/S4/S11 เป็นจริงบน MARS ด้วย — ยังไม่ต้องมี `--target mars` (Q30) |
| S20 | harness ของ MARS: หลังโปรแกรมจบ MARS พิมพ์บรรทัดว่างเพิ่ม 1 บรรทัด (`\r\n` บน Windows); error ตอน assemble ออก stdout แต่ **exit 0** ถ้าไม่ใส่ `ae<n>` | MARS harness (M6) ต้องตัดบรรทัดท้าย และใช้ `nc ae<n>` |

---

## 14. Conventions สำหรับผู้ร่วมพัฒนา

- Python: `ruff` + `mypy --strict`; ทุก stage เป็น pure function
- ทุก feature ใหม่ต้องมาพร้อม: golden program 1 ไฟล์ + error test 1 ไฟล์ + อัปเดต §4
- เพิ่ม builtin ใหม่: (1) routine `__rt_<name>` ใน `runtime.s` (leaf, ไม่แตะ stack) (2) entry ใน builtin table (3) prototype ใน `c2mips.h` (4) C reference ใน `ref/` (5) exhaustive/boundary test เทียบ Python
- ห้าม commit `.s` ที่มีไบต์ > 0x7F (pre-commit hook)
- ADR ใหม่ทุกครั้งที่เปลี่ยน semantics ของภาษาหรือ calling convention

---

## ภาคผนวก A: `runtime.s` (ทดสอบแล้ว)

✅ ผ่าน S3, S4, S6 บน SPIM 8.0

```asm
# ---------------- c2mips runtime (v0.1) ----------------
        .data
__rt_msg_div0:    .asciiz "runtime error: division by zero\n"
__rt_msg_nckovf:  .asciiz "runtime error: nCk overflow\n"
        .text
# int nCk(int n, int k)   in: $a0=n $a1=k   out: $v0
# 0 if n<0 || k<0 || k>n ; panic if result > INT_MAX
# r_i = C(n-k+i, i); step: g=gcd(r,i); r=(r/g)*((n-k+i)/(i/g))
# uses only $t0-$t7,$a0,$a1,$v0 (leaf, no stack)
__rt_nCk:
        bltz  $a0, __rt_nCk_zero
        bltz  $a1, __rt_nCk_zero
        slt   $t0, $a0, $a1            # n < k ?
        bne   $t0, $zero, __rt_nCk_zero
        subu  $t1, $a0, $a1            # t1 = n-k
        slt   $t0, $t1, $a1            # n-k < k ?
        beq   $t0, $zero, __rt_nCk_kok
        move  $a1, $t1                 # k = min(k, n-k)
__rt_nCk_kok:
        subu  $t1, $a0, $a1            # base = n-k
        li    $v0, 1                   # r = 1
        li    $t2, 1                   # i = 1
__rt_nCk_loop:
        slt   $t0, $a1, $t2            # k < i ?
        bne   $t0, $zero, __rt_nCk_ret
        addu  $t3, $t1, $t2            # num = base + i
        move  $t4, $v0                 # gcd(r, i) -> $t4
        move  $t5, $t2
__rt_nCk_gcd:
        beq   $t5, $zero, __rt_nCk_gcd_end
        divu  $t4, $t5
        mfhi  $t6
        move  $t4, $t5
        move  $t5, $t6
        b     __rt_nCk_gcd
__rt_nCk_gcd_end:
        divu  $v0, $t4
        mflo  $v0                      # r /= g
        divu  $t2, $t4
        mflo  $t7                      # d = i / g
        divu  $t3, $t7
        mflo  $t3                      # num /= d  (exact)
        multu $v0, $t3
        mfhi  $t6
        mflo  $v0                      # r = r * num
        bne   $t6, $zero, __rt_nCk_ovf
        bltz  $v0, __rt_nCk_ovf        # > INT_MAX
        addiu $t2, $t2, 1
        b     __rt_nCk_loop
__rt_nCk_ret:
        jr    $ra
__rt_nCk_zero:
        move  $v0, $zero
        jr    $ra
__rt_nCk_ovf:
        la    $a0, __rt_msg_nckovf
        b     __rt_panic
__rt_div0:
        la    $a0, __rt_msg_div0
__rt_panic:
        li    $v0, 4                   # print_string
        syscall
        li    $a0, 70                  # EX_SOFTWARE
        li    $v0, 17                  # exit2
        syscall
```

---

## ภาคผนวก B: ตัวอย่าง `example.c` → `example.s` (ทดสอบแล้ว)

นี่คือ **ผลลัพธ์อ้างอิง** ที่ `c2mips -O0` ต้อง emit (เขียนมือตาม template §6 แล้วรันจริง) ✅ S11

`example.c`

```c
#include <stdio.h>
#include "c2mips.h"

int main(void) {
    int n = 10;
    int k = 3;
    int a = (n + k) * 2 - 7 / 2;
    printf("a = %d\n", a);
    printf("C(%d,%d) = %d\n", n, k, nCk(n, k));
    return 0;
}
```

`example.s` (ต่อท้ายด้วย `runtime.s` จากภาคผนวก A)

```asm
# generated by c2mips 0.1 (-O0) from example.c
        .data
__str0: .asciiz "a = "
__str1: .asciiz "\n"
__str2: .asciiz "C("
__str3: .asciiz ","
__str4: .asciiz ") = "

        .text
        .globl main
main:                               # entry stub (SPIM __start and MARS both enter here)
        jal   f_main
        move  $a0, $v0
        li    $v0, 17               # exit2(return value of main)
        syscall

f_main:
        addiu $sp, $sp, -8          # prologue
        sw    $ra, 4($sp)
        sw    $fp, 0($sp)
        move  $fp, $sp
        addiu $sp, $sp, -12         # locals: n@-4  k@-8  a@-12
# int n = 10;
        li    $t0, 10
        sw    $t0, -4($fp)
# int k = 3;
        li    $t0, 3
        sw    $t0, -8($fp)
# int a = (n + k) * 2 - 7 / 2;
        lw    $t0, -4($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # push n
        lw    $t0, -8($fp)
        lw    $t1, 0($sp)
        addiu $sp, $sp, 4           # pop
        addu  $t0, $t1, $t0         # n + k
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)
        li    $t0, 2
        lw    $t1, 0($sp)
        addiu $sp, $sp, 4
        mult  $t1, $t0
        mflo  $t0                   # (n + k) * 2
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)
        li    $t0, 7
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)
        li    $t0, 2
        lw    $t1, 0($sp)
        addiu $sp, $sp, 4
        beq   $t0, $zero, __rt_div0 # divisor == 0 -> panic
        li    $t2, -1
        bne   $t0, $t2, L1_div
        subu  $t0, $zero, $t1       # x / -1 == -x (wraps for INT_MIN)
        b     L1_end
L1_div:
        div   $t1, $t0
        mflo  $t0                   # 7 / 2
L1_end:
        lw    $t1, 0($sp)
        addiu $sp, $sp, 4
        subu  $t0, $t1, $t0         # ... - ...
        sw    $t0, -12($fp)
# printf("a = %d\n", a);
        lw    $t0, -12($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # arg0 (args are evaluated before any output)
        la    $a0, __str0
        li    $v0, 4
        syscall
        lw    $a0, 0($sp)
        li    $v0, 1
        syscall
        la    $a0, __str1
        li    $v0, 4
        syscall
        addiu $sp, $sp, 4
# printf("C(%d,%d) = %d\n", n, k, nCk(n, k));
        lw    $t0, -4($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # arg0 = n
        lw    $t0, -8($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # arg1 = k
        lw    $t0, -4($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # nCk arg n
        lw    $t0, -8($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # nCk arg k
        lw    $a1, 0($sp)
        lw    $a0, 4($sp)
        addiu $sp, $sp, 8
        jal   __rt_nCk
        move  $t0, $v0
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)           # arg2 = nCk(n, k)
        la    $a0, __str2
        li    $v0, 4
        syscall
        lw    $a0, 8($sp)
        li    $v0, 1
        syscall
        la    $a0, __str3
        li    $v0, 4
        syscall
        lw    $a0, 4($sp)
        li    $v0, 1
        syscall
        la    $a0, __str4
        li    $v0, 4
        syscall
        lw    $a0, 0($sp)
        li    $v0, 1
        syscall
        la    $a0, __str1
        li    $v0, 4
        syscall
        addiu $sp, $sp, 12
# return 0;
        li    $t0, 0
        move  $v0, $t0
        b     L_epi_main
L_epi_main:
        move  $sp, $fp              # epilogue
        lw    $fp, 0($sp)
        lw    $ra, 4($sp)
        addiu $sp, $sp, 8
        jr    $ra
```

ผลลัพธ์ — เหมือนกันทั้ง SPIM 8.0 (exit 0) และ `gcc -std=c99 -fwrapv -O0 -Iinclude example.c ref/nck_ref.c` ✅

```
a = 23
C(10,3) = 120
```

สังเกต: โค้ด -O0 มี push/pop ซ้ำซ้อนเยอะ (เช่น `n + k` ใช้ 7 คำสั่ง ขณะที่ `-O1` leaf operand (§6.9) เหลือ 4: `lw` · `move $t1,$t0` · `lw` · `addu`)

---

## ภาคผนวก C: `c2mips.h` และ `ref/nck_ref.c`

`include/c2mips.h`

```c
#ifndef C2MIPS_H
#define C2MIPS_H
int nCk(int n, int k);
#endif
```

`ref/nck_ref.c` — ✅ S13 (ต้องตรงกับ `runtime.s` ทุกตัวอักษร รวมถึงเส้นทาง error)

```c
/* Reference implementation for differential testing on the host (gcc).
   Must match runtime/runtime.s bit-for-bit, including the error path. */
#include <stdio.h>
#include <stdlib.h>
#include "c2mips.h"

static unsigned gcd_u(unsigned a, unsigned b) {
    while (b != 0) { unsigned t = a % b; a = b; b = t; }
    return a;
}

int nCk(int n, int k) {
    if (n < 0 || k < 0 || k > n) return 0;
    if (n - k < k) k = n - k;
    unsigned base = (unsigned)(n - k), r = 1;
    for (unsigned i = 1; i <= (unsigned)k; i++) {
        unsigned num = base + i;
        unsigned g = gcd_u(r, i);
        r /= g;
        num /= (i / g);
        unsigned long long p = (unsigned long long)r * num;
        if (p > 2147483647ULL) {
            printf("runtime error: nCk overflow\n");
            fflush(stdout);
            exit(70);
        }
        r = (unsigned)p;
    }
    return (int)r;
}
```

---

## ภาคผนวก D: เอกสารอ้างอิง

- **COANotes2014** (เอกสารใน Project วิชา) บทที่ 2 — หัวข้อ 2.6 Supporting Procedures (caller/callee, `jal`/`jr $ra`), 2.6.3 procedure frame และพารามิเตอร์ตัวที่ 5+ เหนือ `$fp`, ตาราง 2.2 การรักษาค่า register, รูป 2.6 การแบ่งหน่วยความจำ (text เริ่ม 0x00400000, static data 0x10000000), หัวข้อ PC-relative addressing (ระยะ branch ±2¹⁵ คำสั่ง)
- SPIM (James Larus) — แพ็กเกจ Ubuntu `spim` 8.0
- [MARS MIPS Assembler and Runtime Simulator — Missouri State University](https://computerscience.missouristate.edu/mars-mips-simulator.htm)
- MARS 4.5.1 release jar: `https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar` (ที่มา: [Homebrew cask `mars`](https://formulae.brew.sh/api/cask/mars.json))
- ISO/IEC 9899:1999 (C99) — §6.5.5 การหารปัดเข้าหาศูนย์, §5.1.2.2.3 `main` คืน 0 โดยปริยาย
