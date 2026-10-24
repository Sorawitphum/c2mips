# ADR-005: Simulator เป้าหมาย

> สำเนาจาก README.md §7 — README เป็นต้นฉบับ


**Status:** Accepted (ส่วน MARS = Proposed จนกว่า M0 จะยืนยัน) · **Date:** 2026-10-24

| Option | ข้อดี | ข้อเสีย |
|---|---|---|
| **SPIM 8.0** | ✅ `apt install spim`, CLI headless, exit code ส่งต่อได้ | banner 5 บรรทัด, text segment 64 KB, ค้างเมื่อเจอ non-ASCII |
| **MARS 4.5** | นิยมในวิชา, GUI ดี | ต้องมี Java + ดาวน์โหลด jar; พฤติกรรม CLI ยังไม่ได้ตรวจ |
| QEMU + GNU toolchain | รันบน "เครื่องจริง" | ต้องใช้ o32 ABI เต็ม + crt + libc — เกินโจทย์ |

**Decision:** emit เฉพาะชุดคำสั่ง/directive ที่ทั้ง SPIM และ MARS รู้จัก; CI รันบน SPIM; ตรวจ MARS ใน M0 และก่อน release
