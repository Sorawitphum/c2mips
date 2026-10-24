"""Emitted assembly has the same shape as README appendix B (6.3-6.7, NFR-2)."""

from __future__ import annotations

import re

import pytest
from conftest import REPO

from c2mips import RUNTIME_S
from c2mips.driver import compile_source

EXAMPLE_M1 = REPO / "examples" / "example_m1.c"
GOLDEN_M1 = REPO / "tests" / "golden" / "example_m1.s"


def appendix(heading: str, fence: str) -> str:
    """First fenced block of the given kind after a README heading."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split(heading, 1)[1]
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


def without_nck_printf_c(src: str) -> str:
    return "".join(ln for ln in src.splitlines(keepends=True) if "nCk(n, k)" not in ln)


def without_nck_printf_s(asm: str) -> list[str]:
    """Appendix B's .text without the `printf("C(...)", n, k, nCk(n, k))` block."""
    lines = asm.splitlines()
    text = lines[next(i for i, ln in enumerate(lines) if ln == "        .text"):]
    i = next(n for n, ln in enumerate(text) if ln.startswith('# printf("C('))
    j = next(n for n in range(i, len(text)) if text[n] == "        addiu $sp, $sp, 12")
    return text[:i] + text[j + 1:]


def test_appendix_b_without_nck_instruction_for_instruction() -> None:
    # M2: everything in appendix B except the nCk call (M3) must match, instruction by
    # instruction (comments are hand-written there, so they are not compared).
    ours = compile_source(without_nck_printf_c(APPENDIX_B_C), "example.c", runtime=False)
    text = ours.splitlines()[ours.splitlines().index("        .text"):]
    assert code_only(text) == code_only(without_nck_printf_s(APPENDIX_B_S))


def test_locals_line_identical_to_appendix_b() -> None:
    ours = compile_source(without_nck_printf_c(APPENDIX_B_C), "example.c", runtime=False)
    line = "        addiu $sp, $sp, -12         # locals: n@-4  k@-8  a@-12"
    assert line in APPENDIX_B_S.splitlines()
    assert line in ours.splitlines()


@pytest.mark.xfail(strict=True, reason="appendix B calls nCk (M3)")
def test_appendix_b_example_instruction_for_instruction() -> None:
    asm = compile_source(APPENDIX_B_C, "example.c", runtime=False)
    assert code_only(asm.splitlines()) == code_only(APPENDIX_B_S.splitlines())
