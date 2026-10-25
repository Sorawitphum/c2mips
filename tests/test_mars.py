"""MARS compatibility (Spec 9.2 "MARS compat", ADR-005): a subset of the goldens must give
the same stdout + exit code on MARS 4.5 as on SPIM, at -O0 and -O1. Opt-in: set MARS_JAR.

The subset covers every feature and both runtime panics; panics and scanf are included
because they are where the simulators could differ (exit2, syscall 5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REPO, read_expected, run_mars, stdin_for

from c2mips.driver import compile_source

SUBSET = [
    "a01_precedence", "a05_div_trunc_neg_dividend", "a08_int_min_div_minus_one",
    "a11_div_by_zero", "n06_nck_largest_middle", "n08_nck_overflow_bit31",
    "n11_nck_overflow_hi", "n13_nck_symmetric_k", "printf_formats", "printf_utf8",
    "var_shadowing", "if_else", "for_loop", "func_recursion", "logic_short_circuit",
    "mod_semantics", "scanf_basic", "scanf_extremes",
]
PROGRAMS = REPO / "tests" / "programs"


def test_subset_exists() -> None:
    assert len(SUBSET) >= 10  # Spec 9.2: at least 10 programs
    for stem in SUBSET:
        assert (PROGRAMS / f"{stem}.c").exists(), stem


@pytest.mark.mars
@pytest.mark.parametrize("opt", [0, 1])
@pytest.mark.parametrize("stem", SUBSET)
def test_mars_matches_golden(stem: str, opt: int, tmp_path: Path) -> None:
    src = PROGRAMS / f"{stem}.c"
    asm = tmp_path / f"{stem}.s"
    asm.write_bytes(compile_source(src.read_text(encoding="utf-8"), src.name, opt=opt)
                    .encode("ascii"))
    assert run_mars(asm, stdin=stdin_for(src)) == read_expected(src.with_suffix(".expected"))
