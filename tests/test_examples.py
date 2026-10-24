"""M4 exit criteria (Spec 11): examples fact/fib/gcd, and a user-written nCk that equals
the builtin for every n <= 12. Expected output is computed here in Python, independently
of both c2mips and gcc."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from conftest import REPO, run_gcc, run_spim

from c2mips.driver import compile_source

EXAMPLES = REPO / "examples"


def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


NCK_SUM = sum(math.comb(n, k) for n in range(13) for k in range(n + 1))
GCD_PAIRS = [(1071, 462), (462, 1071), (17, 5), (0, 9), (9, 0), (2147483647, 2147483646),
             (1836311903, 1134903170), (65536, 4096)]
EXPECTED = {
    "fact": "".join(f"{n}! = {math.factorial(n)} {math.factorial(n)}\n" for n in range(13)),
    "fib": "".join(f"fib({n}) = {fib(n)} {fib(n)}\n" for n in range(21)),
    "gcd": "".join(f"gcd({a}, {b}) = {math.gcd(a, b)} {math.gcd(a, b)}\n" for a, b in GCD_PAIRS),
    "nck_user": f"checked 91, mismatches 0, sum {NCK_SUM}\n",
}


@pytest.mark.spim
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_on_spim(name: str, tmp_path: Path) -> None:
    src = EXAMPLES / f"{name}.c"
    asm = tmp_path / f"{name}.s"
    asm.write_bytes(compile_source(src.read_text(encoding="utf-8"), src.name).encode("ascii"))
    assert run_spim(asm, timeout=30) == (EXPECTED[name], 0)


@pytest.mark.gcc
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_on_gcc(name: str, tmp_path: Path) -> None:
    assert run_gcc(EXAMPLES / f"{name}.c", tmp_path) == (EXPECTED[name], 0)


def test_every_example_is_checked() -> None:
    m4 = {"fact", "fib", "gcd", "nck_user"}
    assert m4 <= {p.stem for p in EXAMPLES.glob("*.c")}
    assert m4 == set(EXPECTED)
