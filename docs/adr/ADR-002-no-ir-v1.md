# ADR-002: ไม่มี IR ใน v1

> สำเนาจาก README.md §7 — README เป็นต้นฉบับ


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
