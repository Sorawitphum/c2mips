# ADR-009: target `fpga` (openmips / FPGA Studio / Nexys A7)

> สำเนาจาก Spec.md §7 — Spec เป็นต้นฉบับ

**Status:** Accepted — ผู้ใช้อนุมัติค่าเริ่มต้นของ Q1–Q5 (2026-10-28) · **Date:** 2026-10-28

**Context:** ผู้ใช้จะใช้ c2mips เป็น "custom compiler" ใน FPGA Studio (IDE บน Windows) กับ CPU `openmips` (5-stage pipeline) บนบอร์ด Nexys A7 ข้อเท็จจริงด้านล่าง **ได้จากผู้ใช้และการสังเกต IDE** ยังไม่ได้ทดสอบใน CI (Spec §13 S24–S30):

- IDE เรียก `<compiler> <path>\fpga_studio_temp_src.c` (ส่ง path ไฟล์ต้นทางอย่างเดียว, cwd = โฟลเดอร์ IDE) แล้ว assemble ด้วย assembler ของตัวเอง; ยังไม่รู้ว่าอ่าน asm จาก stdout หรือจากไฟล์ `<src>.s`
- โค้ดเริ่มที่ PC `0x0000`; stack ใกล้ `0x80010000`
- **มี branch delay slot**: คำสั่งถัดจาก branch/jump ถูกทำเสมอ (mips-gcc ของ IDE: `jal` ที่ `0x0004` ตั้ง `$ra = 0x000C` และมี `nop` หลังทุก branch)
- assembler ของ IDE แปลงคำสั่งที่ไม่รู้จักเป็น `0x00000000` **แบบเงียบ ๆ** — ที่พบว่าไม่รู้จัก: `b`, `la`, `syscall` (และน่าจะไม่โหลด `.data`); ที่รู้จักแน่: `addiu addu subu slt lw sw lui jal jr beq bne bltz divu multu mfhi mflo`, `li`/`move` ค่าเล็ก
- ไม่มีระบบปฏิบัติการ: ไม่มี syscall ไม่มี stdout; โปรแกรมจบด้วยการวนค้าง
- I/O แบบ memory-mapped (word): `LED = 0xF0000000` (เขียน), `SWITCH = 0xF0000004` (อ่าน), `SEG7 = 0xF0000008` (เขียน)

ทุกอย่างของ target `spim` (ค่าเริ่มต้น) **คงเดิมทุกไบต์** — target นี้เป็น output แบบที่สองที่เลือกด้วย `--target fpga`

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: ใช้ output ของ SPIM ตรง ๆ | ไม่ต้องทำอะไร | `la`/`syscall`/`b`/`.data` กลายเป็น `0x00000000`; ไม่มี delay slot → ผลผิดเงียบ ๆ |
| B: แปลง output ของ SPIM ทีหลัง (post-processor) | codegen ไม่เปลี่ยน | printf/syscall แปลงไม่ได้; ต้อง parse asm อีกรอบ; ตรวจ whitelist ยาก |
| **C: target ที่สองใน codegen/emitter** | ควบคุมทุกคำสั่ง, ตรวจ whitelist ตอน emit, runtime แยกไฟล์ | โค้ดสองทางใน emitter (แยกด้วย `target`) |

**Decision:** C — รายละเอียด:

1. **CLI:** `--target spim|fpga` (ค่าเริ่มต้น `spim`) ใช้ร่วมกับ `-O0`/`-O1` ได้; `--run` ใช้กับ `fpga` ไม่ได้ (ไม่มี simulator ของบอร์ด) → exit 2
2. **ชุดคำสั่ง:** emit เฉพาะ mnemonic ใน whitelist นี้ — `addu addiu subu and andi or ori xor xori nor slt slti sltu sltiu sll srl sra lui lw sw beq bne bltz bgez blez bgtz j jal jr mult multu div divu mfhi mflo nop` — emitter ตรวจทุกบรรทัด ถ้าเจอนอก whitelist = **error ภายใน (assert)** ไม่ปล่อยออกไปให้ IDE แปลงเป็น 0 เงียบ ๆ · ไม่ใช้ pseudo-instruction ใด ๆ แม้ IDE รู้จักบางตัว:
   - `li r, v` → `addiu r, $zero, v` ถ้า v อยู่ใน int16 ไม่งั้น `lui r, hi16` + `ori r, r, lo16` (ไม่มี `ori` ถ้า lo16 = 0)
   - `move a, b` → `addu a, b, $zero`
   - `b L` → `beq $zero, $zero, L`
   - ไม่มี `la`, `syscall`, `.data`, `.asciiz`, `.byte`
   - **ไม่ใช้ `$at`** (ยังไม่รู้ว่า assembler ของ IDE จองไว้หรือไม่)
3. **Delay slot:** ใส่ `nop` หลัง branch/jump ทุกตัว (`beq bne bltz bgez blez bgtz j jal jr`) — ยังไม่เติมคำสั่งที่มีประโยชน์ลงช่อง (ทำทีหลังได้โดยไม่เปลี่ยน ADR นี้) · ถือว่า **ไม่มี load delay slot** และ HI/LO มี interlock (เป็น MIPS32; openmips stall ตอน div) — ถ้าผิด ต้องแก้ ADR นี้
4. **Startup** (ตาม mips-gcc ของ IDE แต่เรียก `f_main` ตาม Spec §6.5 และส่งค่าที่ `main` คืนไป SEG7):

   ```asm
   _start:
           lui   $sp, 0x8001
           jal   f_main
           nop
           lui   $t0, 0xF000
           sw    $v0, 8($t0)            # SEG7 = return value of main
   _halt:
           j     _halt
           nop
   ```

5. **Calling convention / frame:** เหมือน Spec §6.2 ทุกอย่าง (`$a0–$a3`, `$v0`, `$fp`, slot `-4*(i+1)($fp)`) — ต่างแค่ template ตามข้อ 2–3
6. **printf / scanf:** compile error ใหม่ `E032` — `'printf' is not available on --target fpga; write to SEG7/LED instead` (`scanf` ทำนองเดียวกัน; อ่าน SWITCH แทน)
7. **Runtime error** (หาร 0, `%` 0, nCk ล้น): เขียนรหัสลง SEG7 แล้ววนค้างที่ `_panic` — `0xDEAD0001` = หาร 0 (รวม `%` 0 ตาม ADR-008), `0xDEAD0002` = nCk ล้น
8. **Runtime:** ไฟล์ใหม่ `c2mips/runtime/runtime_fpga.s` (ห้ามแตะ `runtime.s`) — อัลกอริทึม nCk เหมือนเดิมทุกขั้น ต่างแค่ (ก) `nop` หลังทุก branch/jump (ข) แทน pseudo ตามข้อ 2 (ค) panic ตามข้อ 7 · แนบเฉพาะเมื่อโปรแกรมใช้ `nCk` / `/` / `%` และ **แนบเฉพาะ routine ที่ใช้** (`__rt_nCk`, `__rt_div0`, `__rt_panic`)
9. **ค่าที่ `main` คืน:** `$v0` ตอน `f_main` return → SEG7 แล้ว `_halt` (main ที่ไม่มี `return` คืน 0 ตาม C99 → SEG7 = 0); โปรแกรม `while (1)` ไม่ถึง `_halt`
10. **ข้อความใน output:** ดูคำถามที่ยังเปิด ข้อ Q3

**Consequences:**
- test บน CI ใช้ตัวจำลองใน Python (`tests/fpga_sim.py`) ที่จำลอง delay slot และ MMIO + ตรวจ encoding ด้วย GNU as (ถ้ามี) — ไม่มี IDE จริงใน CI
- คำสั่งที่ **ไม่อยู่ในชุดที่ยืนยันแล้ว** แต่อยู่ใน whitelist (`div mult ori sltu sltiu xori and or ...` และ `nop`/`j`) ยังต้องยืนยันบน IDE จริง — อยู่ใน checklist ท้ายงาน
- ขนาด RAM ของบอร์ดยังไม่รู้ → ความลึกของ recursion ที่ใช้ได้จริงยังไม่รู้

**คำถามที่ตัดสินแล้ว (ใช้ค่าเริ่มต้นทั้งหมด):**
- **Q2 — SEG7 ตอนจบ:** ค่าที่ `main` คืน **เขียนทับ** ค่าที่โปรแกรมเขียน SEG7 เองไว้เสมอ (เช่น `SEG7 = 42; return 0;` → บอร์ดแสดง 0) · ค่าเริ่มต้น: เขียนทับเสมอ ตามที่สั่ง (โปรแกรมที่อยากโชว์ค่าเองให้ `return` ค่านั้น หรือวน `while (1)`)
- **Q3 — directive และ comment:** ยังไม่รู้ว่า assembler ของ IDE รับ `.text` / `.globl` / comment `#` หรือไม่ (ถ้าไม่รับอาจกลายเป็น `0x00000000`) · ค่าเริ่มต้น: output ของ `fpga` มีแค่ label กับคำสั่ง — **ไม่มี directive และไม่มี comment**; register ใช้ชื่อ (`$t0`) แบบที่ mips-gcc ของ IDE ใช้
