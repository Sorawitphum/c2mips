# CLAUDE.md
- spec หลักคือ README.md ห้ามเปลี่ยน semantics ใน §4 หรือ calling convention ใน §6 โดยไม่ถามก่อน
- ถ้าจำเป็นต้องเปลี่ยน ให้เขียน ADR ใหม่ใน docs/adr/
- ทำทีละ milestone ตาม §11 และถือว่าเสร็จเมื่อ exit criteria ผ่านเท่านั้น
- ทุก feature ต้องมี golden test + error test (§14)
- รันก่อนบอกว่าเสร็จ: ruff check . && mypy --strict c2mips && pytest -q
- ไฟล์ .s ที่ emit ห้ามมีไบต์ > 0x7F (SPIM ค้าง — §13 S8)
- runtime.s ในภาคผนวก A ผ่านการทดสอบแล้ว ให้ใช้ตามนั้น ห้ามเขียนใหม่