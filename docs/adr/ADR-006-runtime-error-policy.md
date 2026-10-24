# ADR-006: นโยบาย runtime error

> สำเนาจาก README.md §7 — README เป็นต้นฉบับ


**Status:** Accepted · **Date:** 2026-10-24

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| A: UB ตาม C (ไม่ check) | โค้ดสั้นสุด | ✅ SPIM ไม่ trap, LO ค้างค่าเก่า → ได้เลขผิดแบบเงียบ ๆ แย่ที่สุดสำหรับผู้เรียน |
| **B: panic + ข้อความ + exit 70** | ชัด, ทดสอบได้, ตรงกับ `nck_ref.c` | +5 คำสั่งต่อการหารที่ตัวหารไม่คงที่ |
| C: คืนค่า sentinel (−1) | ไม่หยุดโปรแกรม | −1 เป็นผลลัพธ์ปกติของ arithmetic ได้ → แยกไม่ออก |

**Decision:** B สำหรับ `/0` และ nCk overflow; `x / -1` นิยามเป็น `-x` · exit code 70 = `EX_SOFTWARE` ของ `sysexits.h` · ข้อความออก stdout เพราะ syscall ของ SPIM มีแค่ stdout
