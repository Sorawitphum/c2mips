"""ref/nck_ref.c vs math.comb on the host (README S13, Q24).

runtime.s and nck_ref.c are each checked against math.comb, not only against each other,
so a bug common to both cannot hide.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import run_gcc
from test_nck_exhaustive import INT_MIN, OVF_OUT, oracle

GRID = [(n, k) for n in range(-1, 34) for k in range(-2, 36)]
EXTRA = [(65536, 2), (2147483647, 1), (2147483647, 2147483646), (INT_MIN, 0), (0, INT_MIN)]


def c_int(v: int) -> str:
    return "(-2147483647 - 1)" if v == INT_MIN else str(v)


def driver(calls: list[tuple[int, int]], tmp_path: Path) -> Path:
    body = "".join(f'    printf("%d\\n", nCk({c_int(n)}, {c_int(k)}));\n' for n, k in calls)
    src = tmp_path / "drv.c"
    src.write_text(f'#include <stdio.h>\n#include "c2mips.h"\n\nint main(void) {{\n'
                   f"{body}    return 0;\n}}\n", encoding="utf-8")
    return src


@pytest.mark.gcc
def test_nck_ref_matches_math_comb(tmp_path: Path) -> None:
    calls = [c for c in GRID + EXTRA if oracle(*c) is not None]
    out, code = run_gcc(driver(calls, tmp_path), tmp_path)
    assert code == 0
    assert out.splitlines() == [str(oracle(n, k)) for n, k in calls]


@pytest.mark.gcc
@pytest.mark.parametrize(("n", "k"), [(34, 16), (65537, 2), (100000, 2)])
def test_nck_ref_overflow_panics_like_runtime(n: int, k: int, tmp_path: Path) -> None:
    assert run_gcc(driver([(n, k)], tmp_path), tmp_path) == OVF_OUT
