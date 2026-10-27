"""Back end for --target fpga (ADR-009): openmips / FPGA Studio / Nexys A7.

The IDE's assembler turns anything it does not know into 0x00000000 without a word, so this
emits real instructions only, fills every delay slot with a nop, attaches only the runtime
routines the program uses, and checks the final text against a whitelist (an internal
error, never a silent bad program). The output has labels and instructions only: no
directives and no comments (ADR-009 Q3).
"""

from __future__ import annotations

import re
from pathlib import Path

from c2mips.codegen import AsmLine, Insn, Label, StrRef

RUNTIME_FPGA_S = Path(__file__).parent / "runtime" / "runtime_fpga.s"

WHITELIST = frozenset(
    "addu addiu subu and andi or ori xor xori nor slt slti sltu sltiu sll srl sra lui lw sw "
    "beq bne bltz bgez blez bgtz j jal jr mult multu div divu mfhi mflo nop".split())
BRANCHES = frozenset("beq bne bltz bgez blez bgtz j jal jr".split())
# routine -> routines it needs (attached in this order)
_RUNTIME_DEPS = {"__rt_nCk": ["__rt_nCk", "__rt_panic"], "__rt_div0": ["__rt_div0", "__rt_panic"]}
_LABEL = re.compile(r"^([A-Za-z_.$][\w.$]*):$")


def hex16(v: int) -> str:
    return f"0x{v:04X}"


def load_imm(reg: str, v: int) -> list[Insn]:
    """`li reg, v` without the pseudo-instruction (and without $at)."""
    if -0x8000 <= v <= 0x7FFF:
        return [Insn("addiu", (reg, "$zero", str(v)))]
    u = v & 0xFFFFFFFF
    out = [Insn("lui", (reg, hex16(u >> 16)))]
    if u & 0xFFFF:
        out.append(Insn("ori", (reg, reg, hex16(u & 0xFFFF))))
    return out


def lower(lines: list[AsmLine]) -> list[AsmLine]:
    """Pseudo-instructions -> real ones, and a nop after every branch/jump."""
    out: list[AsmLine] = []
    for ln in lines:
        if not isinstance(ln, Insn):
            out.append(ln)
            continue
        assert not any(isinstance(a, StrRef) for a in ln.args), "no strings on --target fpga"
        args = [str(a) for a in ln.args]
        if ln.op == "li":
            out += load_imm(args[0], int(args[1]))
        elif ln.op == "move":
            out.append(Insn("addu", (args[0], args[1], "$zero")))
        elif ln.op == "b":
            out.append(Insn("beq", ("$zero", "$zero", args[0])))
        else:
            assert ln.op not in ("la", "syscall"), f"{ln.op} cannot reach --target fpga"
            out.append(Insn(ln.op, tuple(args)))
        last = out[-1]
        if isinstance(last, Insn) and last.op in BRANCHES:
            out.append(Insn("nop"))
    return out


def runtime_routines() -> dict[str, list[str]]:
    """runtime_fpga.s split at its `# @routine NAME` markers, comments and blanks removed."""
    routines: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw in RUNTIME_FPGA_S.read_text(encoding="ascii").splitlines():
        if m := re.match(r"#\s*@routine\s+(\S+)", raw.strip()):
            current = routines.setdefault(m.group(1), [])
            continue
        line = raw.split("#", 1)[0].rstrip()
        if current is not None and line.strip():
            current.append(line)
    return routines


def needed_routines(lines: list[AsmLine]) -> list[str]:
    used = {a for ln in lines if isinstance(ln, Insn) for a in ln.args if isinstance(a, str)}
    names: list[str] = []
    for entry, deps in _RUNTIME_DEPS.items():
        if entry in used:
            names += [d for d in deps if d not in names]
    return names


def format_lines(lines: list[AsmLine]) -> list[str]:
    out = []
    for ln in lines:
        if isinstance(ln, Label):
            out.append(f"{ln.name}:")
        elif isinstance(ln, Insn):
            ops = ", ".join(str(a) for a in ln.args)
            out.append(f"        {ln.op:<6}{ops}" if ops else f"        {ln.op}")
        # Comment / Directive / Blank: not for the IDE's assembler (ADR-009 Q3)
    return out


def emit_fpga(lines: list[AsmLine], *, runtime: bool = True) -> str:
    lowered = lower(lines)
    text_lines = format_lines(lowered)
    if runtime:
        routines = runtime_routines()
        for name in needed_routines(lowered):
            text_lines += routines[name]
    check(text_lines)
    return "\n".join(text_lines) + "\n"


def check(text_lines: list[str]) -> None:
    """ADR-009: whitelist mnemonics only, no $at, a nop after every branch/jump. Breaking
    any of these is a compiler bug, so it is an assertion, not a user diagnostic."""
    for i, line in enumerate(text_lines):
        assert line.isascii() and "#" not in line, f"comment or non-ASCII: {line!r}"
        if _LABEL.match(line):
            continue
        assert line.startswith("        ") and not line.strip().startswith("."), line
        op = line.split()[0]
        assert op in WHITELIST, f"mnemonic {op!r} is not in the --target fpga whitelist"
        assert "$at" not in line, f"$at is not used on --target fpga: {line!r}"
        if op in BRANCHES:
            nxt = text_lines[i + 1].split() if i + 1 < len(text_lines) else []
            assert nxt == ["nop"], f"delay slot of {line.strip()!r} is not a nop"
