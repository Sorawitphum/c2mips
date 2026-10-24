# ADR-007: ไบต์ ≥ 0x80 ใน `.byte` เขียนเป็นค่าลบ

> สำเนาจาก README.md §7 — README เป็นต้นฉบับ

**Status:** Accepted · **Date:** 2026-10-24 (M1)

**Context:** string ที่มี non-ASCII (เช่นไทย) ต้องออกเป็น `.byte` ของ UTF-8 (§6.6) ✅ MARS 4.5 รับค่า 128–255 ได้ถูก แต่พิมพ์ warning `out-of-range for a signed value` ลง **stdout** ทุกไบต์ ซึ่งปน output ของโปรแกรม (S17)

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: ค่าบวก 0–255 | อ่านง่าย ตรงกับ hex dump | MARS ปน warning ลง stdout |
| **B: ค่า signed −128…127** | ไบต์เดียวกันทุกตัว; ✅ ไม่มี warning บน MARS และ ✅ SPIM พิมพ์ถูก | อ่านยากกว่าเล็กน้อย |
| C: `.word` / แยก string ไทยเป็นตารางเอง | — | ซับซ้อนเกินจำเป็น |

**Decision:** B · ไม่กระทบ semantics (§4) หรือ calling convention (§6.2) เพราะไบต์ในหน่วยความจำเหมือนเดิมทุกตัว
**Consequences:** `tests/unit/test_emitter.py` ล็อกรูปแบบนี้; ✅ `printf_utf8` ให้ผลเหมือนกันบน SPIM, MARS และ gcc
