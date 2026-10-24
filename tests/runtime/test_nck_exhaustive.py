"""__rt_nCk / __rt_div0 on SPIM vs math.comb (README §4.4, §6.8, §9.2, S3/S4).

All non-overflow cases run in ONE SPIM program driven by a .data table + loop:
straight-line code for ~1,900 calls would exceed SPIM's 64 KB text segment (Q26).
Overflow cases panic and exit, so each one needs its own SPIM run.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from conftest import run_spim

from c2mips import RUNTIME_S

INT_MAX = 2**31 - 1
INT_MIN = -(2**31)

GRID = [(n, k) for n in range(-1, 41) for k in range(-2, 43)]
LARGE = [
    (65536, 2), (65537, 2), (100000, 2), (65536, 65534),
    (2147483647, 0), (2147483647, 1), (2147483647, 2),
    (2147483647, 2147483646), (2147483647, 2147483647), (2147483647, -1),
    (2147483647, 1073741823), (2000000000, 1), (2000000000, 1000000000),
    (INT_MIN, 0), (0, INT_MIN), (INT_MIN, INT_MIN), (5, -1), (1, 2147483647),
]
CASES = GRID + LARGE


def oracle(n: int, k: int) -> int | None:
    """Expected nCk(n, k) per README §4.4; None means overflow panic."""
    if n < 0 or k < 0 or k > n:
        return 0
    k = min(k, n - k)
    if k > 17:  # C(n, k) >= C(2k, k) >= C(36, 18) > INT_MAX; skip a huge math.comb
        return None
    v = math.comb(n, k)
    return v if v <= INT_MAX else None


OK = [(n, k) for n, k in CASES if oracle(n, k) is not None]
OVF = [(n, k) for n, k in CASES if oracle(n, k) is None]

OVF_OUT = ("runtime error: nCk overflow\n", 70)
DIV0_OUT = ("runtime error: division by zero\n", 70)


def program(text: str, data: str = "") -> str:
    """Test driver (entry `main`, called by SPIM's __start) + runtime.s."""
    return (
        "        .data\n" + data
        + "        .text\n        .globl main\nmain:\n" + text
        + RUNTIME_S.read_text(encoding="ascii")
    )


def run(tmp_path: Path, src: str) -> tuple[str, int]:
    asm = tmp_path / "t.s"
    asm.write_bytes(src.encode("ascii"))
    return run_spim(asm)


def test_oracle_matches_readme_table() -> None:
    # README §9.3 N1-N14: pins the oracle itself, without SPIM.
    assert oracle(10, 3) == 120
    assert oracle(0, 0) == 1
    assert oracle(5, 0) == oracle(5, 5) == 1
    assert oracle(5, 7) == 0
    assert oracle(-1, 0) == oracle(5, -1) == oracle(INT_MIN, 0) == 0
    assert oracle(33, 16) == 1166803110
    assert oracle(34, 15) == 1855967520
    assert oracle(34, 16) is None
    assert oracle(65536, 2) == 2147450880
    assert oracle(65537, 2) is None
    assert oracle(100000, 2) is None
    assert oracle(2147483647, 1) == 2147483647
    assert oracle(2147483647, 2147483646) == 2147483647
    assert oracle(30, 15) == 155117520


def test_case_counts() -> None:
    # Every runtime.s path from README §9.6 is in the case list.
    assert {(5, 7), (-1, 0), (2147483647, 2147483646), (33, 16)} <= set(OK)
    assert {(34, 16), (65537, 2), (100000, 2)} <= set(OVF)
    assert len(OK) + len(OVF) == len(CASES)


@pytest.mark.spim
def test_nck_exhaustive(tmp_path: Path) -> None:
    table = "".join(f"        .word {n}, {k}\n" for n, k in OK)
    text = f"""\
        la    $s0, cases
        li    $s1, {len(OK)}
loop:   beq   $s1, $zero, done
        lw    $a0, 0($s0)
        lw    $a1, 4($s0)
        jal   __rt_nCk
        move  $a0, $v0
        li    $v0, 1               # print_int
        syscall
        li    $a0, 10
        li    $v0, 11              # print_char '\\n'
        syscall
        addiu $s0, $s0, 8
        addiu $s1, $s1, -1
        b     loop
done:   li    $a0, 0
        li    $v0, 17
        syscall
"""
    out, code = run(tmp_path, program(text, "cases:\n" + table))
    assert code == 0, out[-500:]
    got = out.split("\n")
    assert got[-1] == ""
    got = got[:-1]
    assert len(got) == len(OK), out[-500:]
    bad = [(n, k, g, oracle(n, k)) for (n, k), g in zip(OK, got, strict=True)
           if g != str(oracle(n, k))]
    assert not bad, f"{len(bad)} mismatches (n, k, got, want): {bad[:20]}"


@pytest.mark.spim
@pytest.mark.parametrize(("n", "k"), OVF)
def test_nck_overflow(tmp_path: Path, n: int, k: int) -> None:
    text = f"""\
        li    $a0, {n}
        li    $a1, {k}
        jal   __rt_nCk
        li    $a0, 0               # not reached: overflow must panic
        li    $v0, 17
        syscall
"""
    assert run(tmp_path, program(text)) == OVF_OUT


@pytest.mark.spim
def test_div0(tmp_path: Path) -> None:
    # Same shape as the divide guard in README §6.4.
    text = """\
        li    $t0, 0
        beq   $t0, $zero, __rt_div0
        li    $a0, 0
        li    $v0, 17
        syscall
"""
    assert run(tmp_path, program(text)) == DIV0_OUT


@pytest.mark.spim
def test_nck_preserves_callee_saved(tmp_path: Path) -> None:
    # README §6.8 / Q20: leaf routine, never touches $sp, $fp, $gp, $s*.
    regs = [f"$s{i}" for i in range(8)] + ["$fp", "$gp", "$sp"]
    setup = "".join(f"        li    {r}, {1000 + i}\n" for i, r in enumerate(regs[:-2]))
    calls = "".join(
        f"        li    $a0, {n}\n        li    $a1, {k}\n        jal   __rt_nCk\n"
        for n, k in [(33, 16), (5, 7), (-1, 0), (2147483647, 2147483646), (30, 15)]
    )
    dump = "".join(
        f"        move  $a0, {r}\n        li    $v0, 1\n        syscall\n"
        "        li    $a0, 10\n        li    $v0, 11\n        syscall\n"
        for r in regs
    )
    text = (
        "        sw    $gp, saved_gp\n        sw    $sp, saved_sp\n" + setup + calls
        + "        lw    $t0, saved_gp\n        subu  $gp, $gp, $t0\n"  # $gp -> delta
        + "        lw    $t0, saved_sp\n        subu  $sp, $sp, $t0\n"  # $sp -> delta
        + dump + "        li    $a0, 0\n        li    $v0, 17\n        syscall\n"
    )
    out, code = run(tmp_path, program(text, "saved_gp: .word 0\nsaved_sp: .word 0\n"))
    assert code == 0, out
    want = [str(1000 + i) for i in range(len(regs) - 2)] + ["0", "0", ""]
    assert out.split("\n") == want
