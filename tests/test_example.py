"""Emitted assembly has the same shape as Spec appendix B (6.3-6.7, NFR-2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import REPO, SPIM, run_gcc, run_spim

from c2mips import RUNTIME_S
from c2mips.__main__ import main
from c2mips.driver import compile_source

EXAMPLE_M1 = REPO / "examples" / "example_m1.c"
GOLDEN_M1 = REPO / "tests" / "golden" / "example_m1.s"
EXAMPLE = REPO / "examples" / "example.c"
APPENDIX_B_OUT = "a = 23\nC(10,3) = 120\n"


def appendix(heading: str, fence: str) -> str:
    """First fenced block of the given kind after a Spec heading."""
    spec = (REPO / "Spec.md").read_text(encoding="utf-8")
    section = spec.split(heading, 1)[1]
    return section.split(f"```{fence}\n", 1)[1].split("```", 1)[0]


APPENDIX_B_S = appendix("## ภาคผนวก B", "asm")
APPENDIX_B_C = appendix("## ภาคผนวก B", "c")


def block(asm: str, first: str, last: str) -> list[str]:
    """Lines from the one starting with `first` through the next one starting with `last`."""
    lines = asm.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith(first))
    j = next(n for n in range(i, len(lines)) if lines[n].startswith(last))
    return lines[i:j + 1]


def code_only(lines: list[str]) -> list[str]:
    """Drop comments and alignment so only instructions/labels/directives remain."""
    out = []
    for ln in lines:
        ln = re.sub(r"\s+", " ", ln.split("#", 1)[0]).strip()
        if ln:
            out.append(ln)
    return out


def m1_asm(runtime: bool = False) -> str:
    return compile_source(EXAMPLE_M1.read_text(encoding="utf-8"), EXAMPLE_M1.name,
                          runtime=runtime)


def test_example_m1_matches_golden() -> None:
    assert m1_asm() == GOLDEN_M1.read_text(encoding="utf-8")


def test_runtime_is_appended_verbatim() -> None:
    full = m1_asm(runtime=True)
    assert full == m1_asm() + "\n" + RUNTIME_S.read_text(encoding="ascii")


@pytest.mark.parametrize(("first", "last"), [
    ("        .text", "        syscall"),             # entry stub (6.7), byte for byte
    ("f_main:", "        move  $fp, $sp"),            # prologue (6.2)
    ("L_epi_main:", "        jr    $ra"),             # epilogue (6.2)
    ("        beq   $t0, $zero, __rt_div0", "L1_end:"),  # divide guard (6.4)
    ("# return 0;", "        b     L_epi_main"),      # return (6.3)
])
def test_blocks_identical_to_appendix_b(first: str, last: str) -> None:
    assert block(m1_asm(), first, last) == block(APPENDIX_B_S, first, last)


def test_header_and_data_layout_like_appendix_b() -> None:
    ours, theirs = m1_asm().splitlines(), APPENDIX_B_S.splitlines()
    assert ours[0] == theirs[0].replace("example.c", "example_m1.c")
    assert ours[1] == theirs[1] == "        .data"
    assert ours[2:4] == theirs[2:4]  # __str0 "a = ", __str1 "\n"


def test_printf_lowering_like_appendix_b() -> None:
    # printf("a = %d\n", ...): arg pushed first, then string/int syscalls, then pop.
    ours = block(m1_asm(), "        la    $a0, __str0", "        addiu $sp, $sp, 4")
    theirs = block(APPENDIX_B_S, "        la    $a0, __str0", "        addiu $sp, $sp, 4")
    assert code_only(ours) == code_only(theirs)


def test_appendix_b_example_instruction_for_instruction() -> None:
    # M3: the whole appendix B listing, instruction by instruction (its comments are
    # hand-written, so they are not compared).
    asm = compile_source(APPENDIX_B_C, "example.c", runtime=False)
    assert code_only(asm.splitlines()) == code_only(APPENDIX_B_S.splitlines())


def test_appendix_b_byte_identical_lines() -> None:
    ours = compile_source(APPENDIX_B_C, "example.c", runtime=False).splitlines()
    for line in [
        "        addiu $sp, $sp, -12         # locals: n@-4  k@-8  a@-12",
        "        jal   __rt_nCk",
        "# printf(\"C(%d,%d) = %d\\n\", n, k, nCk(n, k));",
        "__str4: .asciiz \") = \"",
    ]:
        assert line in APPENDIX_B_S.splitlines()
        assert line in ours


def test_examples_example_c_is_appendix_b() -> None:
    assert EXAMPLE.read_text(encoding="utf-8") == APPENDIX_B_C


@pytest.mark.spim
def test_example_c_on_spim(tmp_path: Path) -> None:
    # S11: appendix B output on SPIM ...
    asm = tmp_path / "example.s"
    asm.write_bytes(compile_source(APPENDIX_B_C, "example.c").encode("ascii"))
    assert run_spim(asm) == (APPENDIX_B_OUT, 0)


@pytest.mark.gcc
def test_example_c_on_gcc(tmp_path: Path) -> None:
    # ... is the same as gcc -std=c99 -fwrapv -O0 -Iinclude example.c ref/nck_ref.c
    assert run_gcc(EXAMPLE, tmp_path) == (APPENDIX_B_OUT, 0)


@pytest.mark.spim
def test_quick_start_as_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                capfd: pytest.CaptureFixture[str]) -> None:
    # Spec 2: `c2mips examples/hello_nck.c -o hello_nck.s` then spim (or --run)
    spec = (REPO / "Spec.md").read_text(encoding="utf-8")
    section = spec.split("## 2. Quick start", 1)[1].split("### CLI", 1)[0]
    quick = section.split("\nผลลัพธ์ (", 1)[1].split("```\n", 1)[1].split("```", 1)[0]
    assert quick == "C(10,3) = 120\n"
    out = tmp_path / "hello_nck.s"
    assert main([str(REPO / "examples" / "hello_nck.c"), "-o", str(out)]) == 0
    assert run_spim(out) == (quick, 0)
    assert SPIM is not None
    monkeypatch.setenv("SPIM", SPIM)
    capfd.readouterr()
    assert main([str(REPO / "examples" / "hello_nck.c"), "-o", str(out), "--run"]) == 0
    assert capfd.readouterr().out == quick


def test_readme_examples_exist_and_hello_output_is_right(tmp_path: Path) -> None:
    # README.md is the user manual: the examples it names must exist, and the output it
    # shows for hello_nck.c must be what c2mips really prints.
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    named = set(re.findall(r"`([a-z_0-9]+\.c)`", readme))
    assert {"hello_nck.c", "example.c", "fact.c", "fib.c", "gcd.c", "nck_user.c"} <= named
    for name in named - {"prog.c"}:
        assert (REPO / "examples" / name).exists(), name
    assert "$ c2mips examples/hello_nck.c --run\nC(10,3) = 120\n" in readme
    if SPIM is not None:
        asm = tmp_path / "hello.s"
        asm.write_bytes(compile_source((REPO / "examples" / "hello_nck.c").read_text(
            encoding="utf-8"), "hello_nck.c").encode("ascii"))
        assert run_spim(asm) == ("C(10,3) = 120\n", 0)
