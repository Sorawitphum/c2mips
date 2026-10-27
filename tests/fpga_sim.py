"""A model of the FPGA Studio / openmips target (ADR-009) for tests: assembler + CPU.

`assemble(text)` turns c2mips `--target fpga` output (labels and whitelist instructions only)
into real MIPS32 machine words at PC 0, 4, 8, ... (two passes, standard encodings).
`run(words)` executes those words, not the text: every branch/jump has a delay slot (the
next instruction always runs, as on openmips), memory is word addressed, and the I/O of
the board is memory mapped:

    0xF0000000  LED     write
    0xF0000004  SWITCH  read  (values come from the test)
    0xF0000008  SEG7    write

It stops on a `j` to itself (`_halt`, `_panic`) or after max_steps instructions.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

LED, SWITCH, SEG7 = 0xF0000000, 0xF0000004, 0xF0000008
MASK = 0xFFFFFFFF

REGS = {"$zero": 0, "$at": 1, "$v0": 2, "$v1": 3, "$a0": 4, "$a1": 5, "$a2": 6, "$a3": 7,
        **{f"$t{i}": 8 + i for i in range(8)}, **{f"$s{i}": 16 + i for i in range(8)},
        "$t8": 24, "$t9": 25, "$k0": 26, "$k1": 27, "$gp": 28, "$sp": 29, "$fp": 30, "$ra": 31}

# mnemonic -> (format, opcode, funct/rt)
R3 = {"addu": 0x21, "subu": 0x23, "and": 0x24, "or": 0x25, "xor": 0x26, "nor": 0x27,
      "slt": 0x2A, "sltu": 0x2B}                      # rd, rs, rt
SHIFT = {"sll": 0x00, "srl": 0x02, "sra": 0x03}       # rd, rt, sa
MULDIV = {"mult": 0x18, "multu": 0x19, "div": 0x1A, "divu": 0x1B}  # rs, rt
MFHL = {"mfhi": 0x10, "mflo": 0x12}                   # rd
IMM = {"addiu": 0x09, "slti": 0x0A, "sltiu": 0x0B, "andi": 0x0C, "ori": 0x0D, "xori": 0x0E}
SIGNED_IMM = {"addiu", "slti", "sltiu"}
MEM = {"lw": 0x23, "sw": 0x2B}
BR2 = {"beq": 0x04, "bne": 0x05}                      # rs, rt, label
BR1 = {"blez": (0x06, 0), "bgtz": (0x07, 0), "bltz": (0x01, 0), "bgez": (0x01, 1)}
JUMP = {"j": 0x02, "jal": 0x03}
MNEMONICS = (set(R3) | set(SHIFT) | set(MULDIV) | set(MFHL) | set(IMM) | set(MEM) | set(BR2)
             | set(BR1) | set(JUMP) | {"jr", "lui", "nop"})


class AsmError(Exception):
    pass


def _reg(tok: str) -> int:
    if tok not in REGS:
        raise AsmError(f"bad register {tok!r}")
    return REGS[tok]


def _int(tok: str) -> int:
    return int(tok, 0)


def parse(text: str) -> tuple[list[tuple[str, list[str], int]], dict[str, int]]:
    """Instructions (mnemonic, operands, line number) and label -> address."""
    insns: list[tuple[str, list[str], int]] = []
    labels: dict[str, int] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        while (m := re.match(r"^([A-Za-z_.$][\w.$]*):\s*(.*)$", line)):
            if m.group(1) in labels:
                raise AsmError(f"line {n}: duplicate label {m.group(1)}")
            labels[m.group(1)] = 4 * len(insns)
            line = m.group(2)
        if not line:
            continue
        if line.startswith("."):
            raise AsmError(f"line {n}: directive {line.split()[0]!r} (the IDE has none)")
        op, _, rest = line.partition(" ")
        args = [a.strip() for a in rest.split(",")] if rest.strip() else []
        insns.append((op, args, n))
    return insns, labels


def assemble(text: str) -> list[int]:
    insns, labels = parse(text)
    words = []
    for i, (op, a, n) in enumerate(insns):
        pc = 4 * i
        try:
            words.append(_encode(op, a, pc, labels))
        except (AsmError, ValueError, KeyError, IndexError) as e:
            raise AsmError(f"line {n}: {op} {', '.join(a)}: {e}") from None
    return words


def _encode(op: str, a: list[str], pc: int, labels: dict[str, int]) -> int:
    def rtype(rs: int, rt: int, rd: int, sa: int, funct: int) -> int:
        return (rs << 21) | (rt << 16) | (rd << 11) | (sa << 6) | funct

    def imm16(v: int, signed: bool) -> int:
        lo, hi = (-0x8000, 0x7FFF) if signed else (0, 0xFFFF)
        if not lo <= v <= hi:
            raise AsmError(f"immediate {v} out of range")
        return v & 0xFFFF

    def branch_off(label: str) -> int:
        off = (labels[label] - (pc + 4)) >> 2
        if not -0x8000 <= off <= 0x7FFF:
            raise AsmError("branch out of range")
        return off & 0xFFFF

    if op == "nop":
        return 0
    if op in R3:
        return rtype(_reg(a[1]), _reg(a[2]), _reg(a[0]), 0, R3[op])
    if op in SHIFT:
        return rtype(0, _reg(a[1]), _reg(a[0]), _int(a[2]) & 31, SHIFT[op])
    if op in MULDIV:
        return rtype(_reg(a[0]), _reg(a[1]), 0, 0, MULDIV[op])
    if op in MFHL:
        return rtype(0, 0, _reg(a[0]), 0, MFHL[op])
    if op == "jr":
        return rtype(_reg(a[0]), 0, 0, 0, 0x08)
    if op in IMM:
        return ((IMM[op] << 26) | (_reg(a[1]) << 21) | (_reg(a[0]) << 16)
                | imm16(_int(a[2]), op in SIGNED_IMM))
    if op == "lui":
        return (0x0F << 26) | (_reg(a[0]) << 16) | imm16(_int(a[1]), False)
    if op in MEM:
        m = re.fullmatch(r"(-?\w+)\((\$\w+)\)", a[1])
        if not m:
            raise AsmError("expected offset($base)")
        return ((MEM[op] << 26) | (_reg(m.group(2)) << 21) | (_reg(a[0]) << 16)
                | imm16(_int(m.group(1)), True))
    if op in BR2:
        return (BR2[op] << 26) | (_reg(a[0]) << 21) | (_reg(a[1]) << 16) | branch_off(a[2])
    if op in BR1:
        opc, rt = BR1[op]
        return (opc << 26) | (_reg(a[0]) << 21) | (rt << 16) | branch_off(a[1])
    if op in JUMP:
        return (JUMP[op] << 26) | ((labels[a[0]] >> 2) & 0x3FFFFFF)
    raise AsmError(f"unknown mnemonic {op!r}")


def _s32(v: int) -> int:
    v &= MASK
    return v - (1 << 32) if v & 0x80000000 else v


@dataclass
class Result:
    seg7: int | None                  # last value written to SEG7 (None: never)
    writes: list[tuple[str, int]] = field(default_factory=list)  # ("LED"|"SEG7", value)
    steps: int = 0
    halted: bool = False              # stopped on `j` to itself
    halt_pc: int = -1

    @property
    def leds(self) -> list[int]:
        return [v for k, v in self.writes if k == "LED"]

    @property
    def seg7s(self) -> list[int]:
        return [v for k, v in self.writes if k == "SEG7"]


class SimError(Exception):
    pass


def run(words: list[int], switch: Callable[[int], int] | Iterable[int] | int = 0,
        max_steps: int = 2_000_000) -> Result:
    """Execute words from PC 0. `switch` is a constant, an iterable (one value per read,
    the last one repeats), or a function of the read number."""
    if isinstance(switch, int):
        value = switch
        read_switch: Callable[[int], int] = lambda _n: value  # noqa: E731
    elif callable(switch):
        read_switch = switch
    else:
        values = list(switch)
        read_switch = lambda n: values[min(n, len(values) - 1)]  # noqa: E731
    reads = 0
    r = [0] * 32
    hi = lo = 0
    mem: dict[int, int] = {}
    res = Result(None)
    pc, npc = 0, 4
    while res.steps < max_steps:
        if pc % 4 or not 0 <= pc // 4 < len(words):
            raise SimError(f"pc 0x{pc:08x} outside the program")
        w = words[pc // 4]
        res.steps += 1
        op, rs, rt, rd = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        sa, funct, imm = (w >> 6) & 31, w & 63, w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        nnpc = npc + 4
        if op == 0:
            a, b = r[rs], r[rt]
            if funct == 0x21:
                r[rd] = (a + b) & MASK
            elif funct == 0x23:
                r[rd] = (a - b) & MASK
            elif funct == 0x24:
                r[rd] = a & b
            elif funct == 0x25:
                r[rd] = a | b
            elif funct == 0x26:
                r[rd] = a ^ b
            elif funct == 0x27:
                r[rd] = ~(a | b) & MASK
            elif funct == 0x2A:
                r[rd] = int(_s32(a) < _s32(b))
            elif funct == 0x2B:
                r[rd] = int(a < b)
            elif funct == 0x00:
                r[rd] = (b << sa) & MASK
            elif funct == 0x02:
                r[rd] = b >> sa
            elif funct == 0x03:
                r[rd] = (_s32(b) >> sa) & MASK
            elif funct == 0x08:
                nnpc = a
            elif funct in (0x18, 0x19):
                p = _s32(a) * _s32(b) if funct == 0x18 else a * b
                hi, lo = (p >> 32) & MASK, p & MASK
            elif funct in (0x1A, 0x1B):
                if b != 0:  # MIPS: division by zero leaves HI/LO unpredictable; keep them
                    x, y = (_s32(a), _s32(b)) if funct == 0x1A else (a, b)
                    q = abs(x) // abs(y) * (1 if (x < 0) == (y < 0) else -1)
                    lo, hi = q & MASK, (x - y * q) & MASK
            elif funct == 0x10:
                r[rd] = hi
            elif funct == 0x12:
                r[rd] = lo
            else:
                raise SimError(f"unknown funct 0x{funct:02x} at 0x{pc:08x}")
        elif op in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E):
            a = r[rs]
            if op == 0x09:
                r[rt] = (a + simm) & MASK
            elif op == 0x0A:
                r[rt] = int(_s32(a) < simm)
            elif op == 0x0B:
                r[rt] = int(a < (simm & MASK))
            elif op == 0x0C:
                r[rt] = a & imm
            elif op == 0x0D:
                r[rt] = a | imm
            else:
                r[rt] = a ^ imm
        elif op == 0x0F:
            r[rt] = imm << 16
        elif op in (0x23, 0x2B):
            addr = (r[rs] + simm) & MASK
            if addr % 4:
                raise SimError(f"unaligned access 0x{addr:08x} at 0x{pc:08x}")
            if op == 0x23:
                if addr == SWITCH:
                    r[rt] = read_switch(reads) & MASK
                    reads += 1
                else:
                    r[rt] = mem.get(addr, 0)
            else:
                v = r[rt]
                if addr in (LED, SEG7):
                    res.writes.append(("LED" if addr == LED else "SEG7", v))
                    if addr == SEG7:
                        res.seg7 = v
                else:
                    mem[addr] = v
        elif op in (0x04, 0x05):
            if (r[rs] == r[rt]) == (op == 0x04):
                nnpc = (npc + (simm << 2)) & MASK
        elif op in (0x06, 0x07, 0x01):
            s = _s32(r[rs])
            take = {0x06: s <= 0, 0x07: s > 0}.get(op, s < 0 if rt == 0 else s >= 0)
            if take:
                nnpc = (npc + (simm << 2)) & MASK
        elif op in (0x02, 0x03):
            target = ((npc & 0xF0000000) | ((w & 0x3FFFFFF) << 2)) & MASK
            if op == 0x02 and target == pc:
                res.halted, res.halt_pc = True, pc
                return res
            if op == 0x03:
                r[31] = (pc + 8) & MASK  # the delay slot is skipped on return
            nnpc = target
        else:
            raise SimError(f"unknown opcode 0x{op:02x} at 0x{pc:08x}")
        r[0] = 0
        pc, npc = npc, nnpc
    return res


def run_asm(text: str, **kw: object) -> Result:
    return run(assemble(text), **kw)  # type: ignore[arg-type]
