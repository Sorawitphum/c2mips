"""Random expressions (README 9.4 generator, ahead of M6): SPIM output at -O0 and -O1 must
both equal cvalue.py. Leaves are literals or variables holding constants, so -O1 both folds
(literals) and uses the leaf-operand / constant-divisor templates (variables)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from conftest import run_spim
from exprgen import PANIC, c_text, evaluate, random_expr

from c2mips import cvalue
from c2mips.driver import compile_source

N_EXPRS = 40


def program(seed: int) -> tuple[str, str]:
    """(C source, expected stdout); every seed gives the same program (recorded seed)."""
    rng = random.Random(seed)
    env = {f"v{i}": rng.choice([0, 1, -1, 3, cvalue.INT_MAX, cvalue.INT_MIN,
                                rng.randint(-99, 99)]) for i in range(4)}
    lines, out = [], []
    while len(out) < N_EXPRS:
        e = random_expr(rng, 4, list(env))
        v = evaluate(e, env)
        if v == PANIC:  # one panic would end the program; panics have their own goldens
            continue
        lines.append(f'    printf("%d\\n", {c_text(e)});\n')
        out.append(f"{v}\n")
    decls = "".join(f"    int {n} = {c_text_int(v)};\n" for n, v in env.items())
    src = ('#include <stdio.h>\n#include "c2mips.h"\n\nint main(void) {\n'
           + decls + "".join(lines) + "    return 0;\n}\n")
    return src, "".join(out)


def c_text_int(v: int) -> str:
    return "-2147483647 - 1" if v == cvalue.INT_MIN else str(v)


@pytest.mark.spim
@pytest.mark.parametrize("seed", range(1, 7))
@pytest.mark.parametrize("opt", [0, 1])
def test_random_expressions(seed: int, opt: int, tmp_path: Path) -> None:
    src, want = program(seed)
    asm = tmp_path / f"r{seed}.s"
    asm.write_bytes(compile_source(src, f"random_{seed}.c", opt=opt).encode("ascii"))
    got = run_spim(asm, timeout=30)
    assert got == (want, 0), f"seed {seed} -O{opt}\n{src}"
