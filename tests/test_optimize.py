"""-O1 (Spec 6.9, 11 M5): golden asm, -O equivalence on every program, the leaf-operand
and constant-divisor templates, and the >= 30% instruction reduction on examples/."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import REPO, read_expected, run_sim, stdin_for

from c2mips.driver import compile_source

PROGRAMS = sorted((REPO / "tests" / "programs").glob("*.c"))
EXAMPLES = sorted((REPO / "examples").glob("*.c"))
GOLDEN = REPO / "tests" / "golden"


def compile_file(src: Path, opt: int, runtime: bool = True) -> str:
    return compile_source(src.read_text(encoding="utf-8"), src.name, runtime=runtime, opt=opt)


def body_asm(body: str, opt: int = 1) -> list[str]:
    src = f"int main(void) {{\n    int x = 9, y = 2;\n{body}\n}}\n"
    return compile_source(src, "t.c", runtime=False, opt=opt).splitlines()


def code(lines: list[str]) -> list[str]:
    """Instructions only, without alignment and comments."""
    out = []
    for ln in lines:
        ln = ln.split("#", 1)[0].strip()
        if ln and not ln.endswith(":") and not ln.startswith("."):
            out.append(re.sub(r"\s+", " ", ln))
    return out


def count_instructions(asm: str) -> int:
    text = asm.splitlines()
    return len(code(text[text.index("        .text"):]))


@pytest.mark.parametrize(("src", "golden"), [
    (REPO / "examples" / "example_m1.c", GOLDEN / "example_m1_O1.s"),
    (REPO / "examples" / "example.c", GOLDEN / "example_O1.s"),  # Spec appendix B at -O1
])
def test_o1_golden(src: Path, golden: Path) -> None:
    assert compile_file(src, 1, runtime=False) == golden.read_text(encoding="utf-8")


def test_o0_is_unchanged_by_the_opt_parameter() -> None:
    src = (REPO / "examples" / "example.c").read_text(encoding="utf-8")
    assert compile_source(src, "example.c", opt=0) == compile_source(src, "example.c")


@pytest.mark.sim
@pytest.mark.parametrize("src", PROGRAMS, ids=lambda p: p.stem)
def test_o1_program_matches_golden(src: Path, tmp_path: Path) -> None:
    # -O equivalence: *.expected is what -O0 prints (test_programs.py), so -O1 must match it.
    asm = tmp_path / f"{src.stem}.s"
    asm.write_bytes(compile_file(src, 1).encode("ascii"))
    want = read_expected(src.with_suffix(".expected"))
    assert run_sim(asm, timeout=30, stdin=stdin_for(src)) == want


@pytest.mark.sim
@pytest.mark.parametrize("src", EXAMPLES, ids=lambda p: p.stem)
def test_o1_example_matches_o0(src: Path, tmp_path: Path) -> None:
    results = []
    for opt in (0, 1):
        asm = tmp_path / f"{src.stem}_O{opt}.s"
        asm.write_bytes(compile_file(src, opt).encode("ascii"))
        results.append(run_sim(asm, timeout=30))
    assert results[0] == results[1]


@pytest.mark.parametrize("src", PROGRAMS + EXAMPLES, ids=lambda p: p.stem)
def test_o1_output_is_ascii_and_deterministic(src: Path) -> None:
    first = compile_file(src, 1)
    assert first.isascii()
    assert compile_file(src, 1) == first


def test_instruction_count_drops_at_least_30_percent_on_examples() -> None:
    o0 = sum(count_instructions(compile_file(p, 0, runtime=False)) for p in EXAMPLES)
    o1 = sum(count_instructions(compile_file(p, 1, runtime=False)) for p in EXAMPLES)
    assert 1 - o1 / o0 >= 0.30, f"-O0 {o0}, -O1 {o1}: {1 - o1 / o0:.1%}"


def test_leaf_right_operand_skips_push_and_pop() -> None:
    # Spec 6.9.3 / appendix B note: `n + k` is 4 instructions instead of 7
    got = code(body_asm("    return x + y;"))
    i = got.index("addu $t0, $t1, $t0")
    assert got[i - 3:i + 2] == ["lw $t0, -4($fp)", "move $t1, $t0", "lw $t0, -8($fp)",
                                "addu $t0, $t1, $t0", "move $v0, $t0"]
    nonleaf = code(body_asm("    return x + y * y;"))
    assert "sw $t0, 0($sp)" in nonleaf and "lw $t1, 0($sp)" in nonleaf


@pytest.mark.parametrize(("src", "lines"), [
    # all-leaf call arguments go straight into $a0..$a3
    ("    return nCk(x, 3);", ["lw $a0, -4($fp)", "li $a1, 3", "jal __rt_nCk"]),
    # leaf return value goes straight into $v0, and `b L_epi_main` before L_epi_main is gone
    ("    return y;", ["lw $v0, -8($fp)", "move $sp, $fp"]),
    # a leaf printf argument is read when printed (no push), a non-leaf one is pushed
    ('    printf("%d %d", x, x * y);', ["lw $a0, -4($fp)", "li $v0, 1", "syscall"]),
    # a comparison as a condition branches directly
    ("    while (x != y) x = y;", ["lw $t0, -4($fp)", "move $t1, $t0", "lw $t0, -8($fp)",
                                    "beq $t1, $t0, L1_wend"]),
    ("    if (x <= 3) return 1;", ["slt $t0, $t0, $t1", "bne $t0, $zero, L1_endif"]),
])
def test_extended_leaf_rules(src: str, lines: list[str]) -> None:
    got = code(body_asm(src))
    i = got.index(lines[0])
    assert got[i:i + len(lines)] == lines


def test_printf_args_are_all_pushed_when_one_assigns() -> None:
    # Spec 4.5: with an assignment among the arguments, reading x late could see it.
    got = code(body_asm('    printf("%d %d", x, x = 5);'))
    assert got.count("addiu $sp, $sp, -4") == 2


@pytest.mark.parametrize(("expr", "must", "must_not"), [
    ("x / 4", ["div $t1, $t0", "mflo $t0"], ["beq $t0, $zero, __rt_div0", "li $t2, -1"]),
    ("x / -1", ["subu $t0, $zero, $t1"], ["div $t1, $t0", "beq $t0, $zero, __rt_div0"]),
    ("x / 0", ["b __rt_div0"], ["div $t1, $t0"]),
    ("x % 4", ["div $t1, $t0", "mfhi $t0"], ["beq $t0, $zero, __rt_div0", "li $t2, -1"]),
    ("x % -1", ["li $t0, 0"], ["div $t1, $t0", "mfhi $t0"]),
    ("x % 0", ["b __rt_div0"], ["div $t1, $t0"]),
    ("x / y", ["beq $t0, $zero, __rt_div0", "li $t2, -1", "div $t1, $t0"], []),  # not const
])
def test_constant_divisor_guard(expr: str, must: list[str], must_not: list[str]) -> None:
    got = code(body_asm(f"    return {expr};"))
    for line in must:
        assert line in got
    for line in must_not:
        assert line not in got


def test_header_says_o1() -> None:
    assert body_asm("    return 0;")[0] == "# generated by c2mips 0.1 (-O1) from t.c"
