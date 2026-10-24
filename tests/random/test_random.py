"""Random differential testing (Spec 9.4): for every seed, c2mips -O0 and -O1 on SPIM,
gcc -fwrapv + nck_ref.c, and cvalue.py must all print the same thing.

    pytest -m random --random-count 500 [--random-seed S]

On a mismatch the program is shrunk automatically, saved to tests/random/failures/, and
the seed is reported so the run can be repeated with `gen.py --seed S`.
"""

from __future__ import annotations

from pathlib import Path

import gen
import pytest
from conftest import run_gcc, run_spim

from c2mips.driver import compile_source

FAILURES = Path(__file__).parent / "failures"


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "seed" in metafunc.fixturenames:
        first = metafunc.config.getoption("--random-seed")
        count = metafunc.config.getoption("--random-count")
        metafunc.parametrize("seed", range(first, first + count))


def outputs(prog: gen.Prog, workdir: Path) -> dict[str, tuple[str, int]]:
    src = gen.render(prog)
    c_file = workdir / "prog.c"
    c_file.write_text(src, encoding="utf-8")
    got = {"expected": (gen.expected(prog), 0)}
    for opt in (0, 1):
        asm = workdir / f"prog_O{opt}.s"
        asm.write_bytes(compile_source(src, "prog.c", opt=opt).encode("ascii"))
        got[f"spim -O{opt}"] = run_spim(asm, timeout=30)
    got["gcc"] = run_gcc(c_file, workdir)
    return got


def agree(got: dict[str, tuple[str, int]]) -> bool:
    return len(set(got.values())) == 1


@pytest.mark.random
@pytest.mark.spim
@pytest.mark.gcc
def test_three_way_agreement(seed: int, tmp_path: Path) -> None:
    prog = gen.generate(seed)
    got = outputs(prog, tmp_path)
    if agree(got):
        return
    small = gen.shrink(prog, lambda p: not agree(outputs(p, tmp_path)))
    FAILURES.mkdir(exist_ok=True)
    saved = FAILURES / f"seed_{seed}.c"
    saved.write_text(gen.render(small), encoding="utf-8")
    report = "\n".join(f"  {k:9} exit={c} {o!r}" for k, (o, c) in outputs(small, tmp_path).items())
    pytest.fail(f"seed {seed}: outputs differ; shrunk program saved to {saved}\n"
                f"{gen.render(small)}\n{report}")
