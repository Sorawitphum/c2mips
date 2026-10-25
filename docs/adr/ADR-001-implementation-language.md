# ADR-001: ภาษาที่ใช้เขียนคอมไพเลอร์

> สำเนาจาก Spec.md §7 — Spec เป็นต้นฉบับ


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
