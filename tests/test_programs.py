"""E2E golden: programs/*.c -> SPIM stdout + exit code == *.expected (Spec 9.2, 9.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import read_expected, run_sim, stdin_for

from c2mips.driver import compile_source

PROGRAMS = sorted((Path(__file__).parent / "programs").glob("*.c"))


def compile_file(src: Path) -> str:
    return compile_source(src.read_text(encoding="utf-8"), src.name)


@pytest.mark.sim
@pytest.mark.parametrize("src", PROGRAMS, ids=lambda p: p.stem)
def test_program(src: Path, tmp_path: Path) -> None:
    asm = tmp_path / f"{src.stem}.s"
    asm.write_bytes(compile_file(src).encode("ascii"))
    assert run_sim(asm, stdin=stdin_for(src)) == read_expected(src.with_suffix(".expected"))


@pytest.mark.parametrize("src", PROGRAMS, ids=lambda p: p.stem)
def test_output_is_ascii_and_deterministic(src: Path) -> None:
    # NFR-6 (SPIM hangs on bytes > 0x7F, S8) and NFR-2 (same input -> same bytes)
    first = compile_file(src)
    assert first.isascii()
    assert compile_file(src) == first
