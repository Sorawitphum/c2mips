"""E2E differential (README 9.2, NFR-1): gcc -fwrapv + ref/nck_ref.c agrees with every golden.

test_programs.py checks SPIM == *.expected; this checks gcc == *.expected, so SPIM == gcc.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import read_expected, run_gcc

PROGRAMS = sorted((Path(__file__).parent / "programs").glob("*.c"))
NO_ORACLE = "// no-gcc-oracle:"
DIFFERENTIAL = [p for p in PROGRAMS
                if not p.read_text(encoding="utf-8").startswith(NO_ORACLE)]


@pytest.mark.gcc
@pytest.mark.parametrize("src", DIFFERENTIAL, ids=lambda p: p.stem)
def test_gcc_agrees_with_golden(src: Path, tmp_path: Path) -> None:
    assert run_gcc(src, tmp_path) == read_expected(src.with_suffix(".expected"))


def test_only_documented_ub_cases_are_excluded() -> None:
    # Only programs whose result is undefined in C may skip the oracle (ADR-006, Q25);
    # nCk overflow is not one of them: nck_ref.c panics exactly like runtime.s (Q15).
    excluded = {p.stem for p in PROGRAMS} - {p.stem for p in DIFFERENTIAL}
    assert excluded == {"a11_div_by_zero", "a12_div_by_runtime_zero",
                        "expr_div_by_computed_zero", "var_int_min_div_minus_one",
                        "mod_by_zero", "mod_int_min_minus_one",  # ADR-008
                        "func_fallthrough_returns_zero"}  # README 4.3: UB if the value is used
