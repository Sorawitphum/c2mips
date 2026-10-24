# ADR-004: nCk เป็นฟังก์ชัน library ไม่ใช่ operator

> สำเนาจาก README.md §7 — README เป็นต้นฉบับ


**Status:** Accepted · **Date:** 2026-10-24

| Option | ผลต่อ differential test | ผลต่อ parser |
|---|---|---|
| A: operator ใหม่ เช่น `n C k` | gcc คอมไพล์ไม่ได้ → เสีย oracle | ชนกับ identifier ชื่อ `C` |
| **B: `int nCk(int, int)` ใน `c2mips.h` + `runtime.s`** | gcc ลิงก์กับ `ref/nck_ref.c` ได้ | เป็นแค่ `Call` ปกติ |
| C: ให้ผู้ใช้เขียน nCk เองด้วย factorial | ได้ | ต้องรอ M4, และติดปัญหา 13! |

**Decision:** B — C กลายเป็นตัวอย่างใน `examples/` หลัง M4 (ใช้เทียบผลกับ builtin สำหรับ n ≤ 12)
