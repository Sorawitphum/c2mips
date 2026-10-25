"""Spec 9.3 N16 (Pascal) and N17 (symmetry), compiled by c2mips and run on SPIM.

M3 has no loops, so the checks are generated as straight-line C; each prints the
difference of the two sides, which must be 0. Chunks keep each program far below the
E040 limit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import run_sim

from c2mips.driver import compile_source


def run_checks(checks: list[str], tmp_path: Path) -> tuple[str, int]:
    body = "".join(f'    printf("%d\\n", {c});\n' for c in checks)
    src = f'#include <stdio.h>\n#include "c2mips.h"\n\nint main(void) {{\n{body}    return 0;\n}}\n'
    asm = tmp_path / "props.s"
    asm.write_bytes(compile_source(src, "props.c").encode("ascii"))
    return run_sim(asm, timeout=30)


@pytest.mark.sim
@pytest.mark.parametrize(("lo", "hi"), [(0, 12), (13, 20), (21, 26), (27, 32)])
def test_n16_pascal_rule(lo: int, hi: int, tmp_path: Path) -> None:
    checks = [f"nCk({n}, {k}) + nCk({n}, {k + 1}) - nCk({n + 1}, {k + 1})"
              for n in range(lo, hi + 1) for k in range(0, n + 1)]
    assert run_checks(checks, tmp_path) == ("0\n" * len(checks), 0)


@pytest.mark.sim
@pytest.mark.parametrize(("lo", "hi"), [(0, 20), (21, 28), (29, 33)])
def test_n17_symmetry(lo: int, hi: int, tmp_path: Path) -> None:
    checks = [f"nCk({n}, {k}) - nCk({n}, {n - k})"
              for n in range(lo, hi + 1) for k in range(-1, n + 2)]
    if hi == 33:
        checks += [f"nCk({n}, {k}) - nCk({n}, {n - k})"
                   for n, k in [(65536, 2), (2147483647, 1), (2147483647, 0), (1000, 3)]]
    assert run_checks(checks, tmp_path) == ("0\n" * len(checks), 0)
