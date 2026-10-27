"""--target fpga (ADR-009 / ADR-010), checked without the IDE: fpga_sim assembles c2mips's
output into real machine words and runs them with a branch delay slot and MMIO."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import fpga_sim as F
import pytest
from conftest import REPO, read_expected, run_sim, stdin_for

from c2mips.diagnostics import CompileError
from c2mips.driver import compile_source
from c2mips.fpga import BRANCHES, WHITELIST

FPGA_PROGRAMS = sorted((REPO / "tests" / "programs_fpga").glob("*.c"))
CHECKED = [p for p in FPGA_PROGRAMS if p.with_suffix(".seg7").exists()]
PROGRAMS = sorted((REPO / "tests" / "programs").glob("*.c"))
EXAMPLES = sorted((REPO / "examples").glob("*.c"))
DIV0, OVF = 0xDEAD0001, 0xDEAD0002
PANIC_MESSAGE = {DIV0: "runtime error: division by zero\n", OVF: "runtime error: nCk overflow\n"}


def fpga_asm(src: Path | str, opt: int = 0, name: str = "t.c") -> str:
    text = src.read_text(encoding="utf-8") if isinstance(src, Path) else src
    return compile_source(text, src.name if isinstance(src, Path) else name, target="fpga",
                          opt=opt)


def expected_seg7(src: Path) -> tuple[int, str]:
    lines = dict(ln.split(": ") for ln in src.with_suffix(".seg7").read_text().splitlines())
    return int(lines["seg7"], 16), lines["halt"]


def halt_label(asm: str, res: F.Result) -> str:
    _, labels = F.parse(asm)
    return next(name for name, addr in labels.items() if addr == res.halt_pc)


def uses_io(src: Path) -> bool:
    return bool(re.search(r"\b(printf|scanf)\s*\(", src.read_text(encoding="utf-8")))


# -- the simulator itself ------------------------------------------------------------------

def test_sim_executes_the_delay_slot() -> None:
    # Without a nop the instruction after a taken branch still runs: SEG7 = 2, not 1.
    asm = """
_start:
        addiu $t0, $zero, 1
        beq   $zero, $zero, L
        addiu $t0, $zero, 2
        addiu $t0, $zero, 3
L:
        lui   $t1, 0xF000
        sw    $t0, 8($t1)
_halt:
        j     _halt
        nop
"""
    res = F.run_asm(asm)
    assert (res.seg7, res.halted) == (2, True)


def test_sim_jal_links_past_the_delay_slot() -> None:
    # Fact 3 of ADR-009: `jal` at 0x0004 sets $ra = 0x000C.
    asm = """
_start:
        nop
        jal   f
        nop
        lui   $t1, 0xF000
        sw    $ra, 8($t1)
_halt:
        j     _halt
        nop
f:
        jr    $ra
        nop
"""
    assert F.run_asm(asm).seg7 == 0x0C


def test_sim_encodings_are_mips32() -> None:
    words = F.assemble("""
        addiu $t0, $zero, 1
        lui   $sp, 0x8001
        sw    $v0, 8($t0)
        jal   x
        nop
x:
        jr    $ra
""")
    assert words == [0x24080001, 0x3C1D8001, 0xAD020008, 0x0C000005, 0x00000000, 0x03E00008]


def test_sim_rejects_what_the_ide_would_turn_into_zero() -> None:
    for line in ["la $a0, x", "syscall", "b x", ".data", "li $t0, 1", "move $t0, $t1"]:
        with pytest.raises(F.AsmError):
            F.assemble(f"x:\n        {line}\n")


# -- IDE example 1 (ADR-010) ---------------------------------------------------------------

def test_ide_example1_golden() -> None:
    src = REPO / "tests" / "programs_fpga" / "ide_example1_switch_to_led.c"
    assert fpga_asm(src) == (REPO / "tests" / "golden" / "fpga_switch_to_led.s").read_text()


@pytest.mark.parametrize("opt", [0, 1])
def test_ide_example1_led_and_seg7_follow_the_switches(opt: int) -> None:
    src = REPO / "tests" / "programs_fpga" / "ide_example1_switch_to_led.c"
    switches = [0, 1, 7, 0xFFFF, -1, 0x7FFFFFFF, 41]
    res = F.run(F.assemble(fpga_asm(src, opt)), switch=switches, max_steps=3000)
    assert not res.halted  # while (1)
    pairs = list(zip(res.writes[0::2], res.writes[1::2], strict=False))
    assert len(pairs) >= len(switches)
    for i, (led, seg7) in enumerate(pairs):
        want = (switches[min(i, len(switches) - 1)] + 1) & F.MASK
        assert led == ("LED", want) and seg7 == ("SEG7", want)


# -- programs: SEG7 = what main returns ----------------------------------------------------

@pytest.mark.parametrize("opt", [0, 1])
@pytest.mark.parametrize("src", CHECKED, ids=lambda p: p.stem)
def test_fpga_program_seg7(src: Path, opt: int) -> None:
    value, halt = expected_seg7(src)
    asm = fpga_asm(src, opt)
    res = F.run(F.assemble(asm))
    assert res.halted and halt_label(asm, res) == halt
    assert res.seg7s == [value]  # written once: by _halt or by _panic


@pytest.mark.sim
@pytest.mark.parametrize("src", CHECKED, ids=lambda p: p.stem)
def test_fpga_copy_agrees_with_spim(src: Path, tmp_path: Path) -> None:
    # The same file on the old target: SPIM's exit code is main's value (8 bits) and a panic
    # prints its message and exits 70.
    value, _ = expected_seg7(src)
    asm = tmp_path / f"{src.stem}.s"
    asm.write_bytes(compile_source(src.read_text(encoding="utf-8"), src.name).encode("ascii"))
    want = (PANIC_MESSAGE[value], 70) if value in PANIC_MESSAGE else ("", value & 0xFF)
    assert run_sim(asm, timeout=60) == want


@pytest.mark.sim
@pytest.mark.parametrize("src", [p for p in PROGRAMS if not uses_io(p)], ids=lambda p: p.stem)
def test_programs_without_io_agree_with_spim(src: Path) -> None:
    out, code = read_expected(src.with_suffix(".expected"))
    asm = fpga_asm(src)
    res = F.run(F.assemble(asm))
    assert res.halted
    if code == 70 and out.startswith("runtime error"):
        assert res.seg7 is not None and PANIC_MESSAGE[res.seg7] == out
    else:
        assert out == "" and res.seg7 is not None and res.seg7 & 0xFF == code


# -- delay slots ---------------------------------------------------------------------------

def without_nops(asm: str) -> str:
    return "\n".join(ln for ln in asm.splitlines() if ln.split() != ["nop"]) + "\n"


@pytest.mark.parametrize("stem", ["ctrl_fact_fib_gcd", "n14_nck_30_15", "n16_pascal_rule",
                                  "a13_vars_appendix_b_expr"])
def test_programs_go_wrong_without_the_nops(stem: str) -> None:
    # The delay slot is real in the model, so the nops c2mips inserts are what makes these
    # right: drop them and the result changes (or the program never reaches _halt).
    src = REPO / "tests" / "programs_fpga" / f"{stem}.c"
    value, _ = expected_seg7(src)
    good = F.run(F.assemble(fpga_asm(src)))
    try:
        bad = F.run(F.assemble(without_nops(fpga_asm(src))), max_steps=200_000)
        broken = not bad.halted or bad.seg7s != [value]
    except F.SimError:
        broken = True
    assert good.seg7s == [value] and broken


# -- what the IDE's assembler gets ---------------------------------------------------------

ALL_SOURCES = PROGRAMS + EXAMPLES + FPGA_PROGRAMS


@pytest.mark.parametrize("opt", [0, 1])
@pytest.mark.parametrize("src", ALL_SOURCES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_whitelist_no_at_and_nop_after_every_branch(src: Path, opt: int) -> None:
    try:
        asm = fpga_asm(src, opt)
    except CompileError as e:  # only printf/scanf may stop a program on this target
        errors = {d.code for d in e.diagnostics if not d.code.startswith("W")}
        assert uses_io(src) and errors == {"E032"}
        return
    lines = asm.splitlines()
    for i, line in enumerate(lines):
        assert line.isascii() and "#" not in line and not line.strip().startswith(".")
        if line.endswith(":"):
            continue
        op = line.split()[0]
        assert op in WHITELIST, line
        assert "$at" not in line, line
        if op in BRANCHES:
            assert lines[i + 1].split() == ["nop"], f"{line} is not followed by nop"
    F.assemble(asm)  # and every line encodes


def test_runtime_routines_only_when_used() -> None:
    def routines(src: str) -> set[str]:
        return set(re.findall(r"^(__rt_\w+):", fpga_asm(src), flags=re.M)) & {
            "__rt_nCk", "__rt_div0", "__rt_panic"}

    assert routines("int main(void) { return 1 + 2; }") == set()
    assert routines("int main(void) { int x = 3; return 7 / x; }") == {"__rt_div0", "__rt_panic"}
    assert routines('#include "c2mips.h"\nint main(void) { int n = 5; return nCk(n, 2); }') == {
        "__rt_nCk", "__rt_panic"}


def test_spim_target_is_unchanged() -> None:
    for src in PROGRAMS + EXAMPLES:
        text = src.read_text(encoding="utf-8")
        assert compile_source(text, src.name, target="spim") == compile_source(text, src.name)


def test_mmio_is_never_folded_merged_or_moved() -> None:
    # ADR-010 volatile: two reads stay two reads, and x * 0 still reads.
    src = ("#define SWITCH (*(volatile int*)0xF0000004)\n"
           "int main(void) { int a = SWITCH + SWITCH; int b = SWITCH * 0; return a + b; }\n")
    for opt in (0, 1):
        res = F.run(F.assemble(fpga_asm(src, opt)), switch=[5, 6, 7])
        assert res.seg7 == 11  # 5 + 6 + 7 * 0
        assert fpga_asm(src, opt).count("lw    $t0, ") >= 3


def test_mmio_o1_puts_the_low_half_in_the_offset() -> None:
    # ADR-010 Q5: SEG7 is one lui + sw 8($t2) at -O1; lo16 >= 0x8000 adjusts the hi part.
    src = ("int main(void) { *(volatile int*)0xF0000008 = 1; *(volatile int*)0x1234FFFC = 2;"
           " return 0; }\n")
    asm = fpga_asm(src, 1)
    assert "        lui   $t2, 0xF000\n        sw    $t0, 8($t2)" in asm
    assert "        lui   $t2, 0x1235\n        sw    $t0, -4($t2)" in asm
    assert "ori   $t2" not in asm


def test_cli_target_fpga(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from c2mips.__main__ import main
    src = tmp_path / "p.c"
    src.write_text("int main() { int a = 5; int b = a + 1; return b; }\n", encoding="utf-8")
    assert main([str(src), "--target", "fpga"]) == 0
    assert F.run(F.assemble(src.with_suffix(".s").read_text())).seg7 == 6
    assert main([str(src), "--target", "fpga", "--run"]) == 2
    assert "--run is not available for --target fpga" in capsys.readouterr().err


# -- encodings checked by GNU as, when a MIPS binutils is installed -------------------------

GNU_AS = next((t for t in ("mips-linux-gnu-as", "mips64-elf-as", "mips-elf-as")
               if shutil.which(t)), None)


@pytest.mark.skipif(GNU_AS is None, reason="no mips-linux-gnu-as / mips64-elf-as on PATH")
@pytest.mark.parametrize("src", CHECKED[:12] + [FPGA_PROGRAMS[0]], ids=lambda p: p.stem)
def test_gnu_as_accepts_the_output(src: Path, tmp_path: Path) -> None:
    assert GNU_AS is not None
    s = tmp_path / "t.s"
    s.write_text(".set noreorder\n.set noat\n" + fpga_asm(src), encoding="ascii")
    p = subprocess.run([GNU_AS, "-march=mips32", "-EB", str(s), "-o", str(tmp_path / "t.o")],
                       capture_output=True, text=True)
    assert p.returncode == 0 and p.stderr == "", p.stderr


def test_stdin_for_is_unused_on_fpga() -> None:
    # scanf is E032 on this target, so no fpga program may need an input file.
    assert all(stdin_for(p) == "" for p in FPGA_PROGRAMS)


# -- the FPGA Studio wrapper (step 4) ------------------------------------------------------

WRAPPER = REPO / "tools" / "c2mips_fpga.bat"


@pytest.mark.skipif(shutil.which("cmd") is None, reason="Windows only (FPGA Studio)")
def test_wrapper_prints_asm_and_keeps_the_file(tmp_path: Path) -> None:
    # Called like the IDE does: one source path, cwd = somewhere else (the IDE's folder).
    src = tmp_path / "fpga_studio_temp_src.c"
    src.write_text("int main() { int a = 5; int b = a + 1; return b; }\n", encoding="utf-8")
    elsewhere = tmp_path / "ide"
    elsewhere.mkdir()
    p = subprocess.run([str(WRAPPER), str(src)], capture_output=True, text=True, cwd=elsewhere)
    assert p.returncode == 0, p.stderr
    kept = Path(f"{src}.s").read_text(encoding="ascii")
    assert p.stdout.replace("\r\n", "\n") == kept == fpga_asm(src)
    assert F.run(F.assemble(p.stdout)).seg7 == 6


@pytest.mark.skipif(shutil.which("cmd") is None, reason="Windows only (FPGA Studio)")
def test_wrapper_reports_errors_on_stderr(tmp_path: Path) -> None:
    src = tmp_path / "bad.c"
    src.write_text('#include <stdio.h>\nint main() { printf("x"); return 0; }\n', encoding="utf-8")
    p = subprocess.run([str(WRAPPER), str(src)], capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == ""
    assert "error[E032]" in p.stderr
    usage = subprocess.run([str(WRAPPER)], capture_output=True, text=True)
    assert usage.returncode == 2 and "usage" in usage.stderr
