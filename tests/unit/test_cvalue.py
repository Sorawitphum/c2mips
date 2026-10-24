"""cvalue (README 5.4): the reference evaluator, checked against independent definitions
(ctypes int32 arithmetic, exact fractions, math.comb)."""

from __future__ import annotations

import ctypes
import math
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from c2mips import cvalue

i32 = st.integers(cvalue.INT_MIN, cvalue.INT_MAX)
EDGES = [0, 1, -1, 2, -2, 7, -7, cvalue.INT_MAX, cvalue.INT_MIN, cvalue.INT_MIN + 1]


def c32(v: int) -> int:
    return ctypes.c_int32(v).value


@given(st.integers(-(2**80), 2**80))
def test_wrap32_is_int32_truncation(v: int) -> None:
    assert cvalue.wrap32(v) == c32(v)


@given(i32, i32)
def test_add_sub_mul_wrap(a: int, b: int) -> None:
    assert cvalue.binary("+", a, b) == c32(a + b)
    assert cvalue.binary("-", a, b) == c32(a - b)
    assert cvalue.binary("*", a, b) == c32(a * b)


@given(i32, i32.filter(lambda b: b != 0))
def test_div_mod_truncate_toward_zero(a: int, b: int) -> None:
    q = math.trunc(Fraction(a, b))
    assert cvalue.binary("/", a, b) == c32(q)  # INT_MIN / -1 wraps to INT_MIN (ADR-006)
    assert cvalue.binary("%", a, b) == (0 if b == -1 else a - b * q)  # ADR-008
    # (a/b)*b + a%b == a under wrap-around, for every b != 0 (ADR-008)
    assert c32(cvalue.binary("/", a, b) * b + cvalue.binary("%", a, b)) == a


@pytest.mark.parametrize("op", ["/", "%"])
@pytest.mark.parametrize("a", EDGES)
def test_division_by_zero_is_a_runtime_error(op: str, a: int) -> None:
    assert cvalue.binary(op, a, 0) is None


@given(i32, i32)
def test_comparisons_and_logic_give_0_or_1(a: int, b: int) -> None:
    expect = {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b,
              "&&": a != 0 and b != 0, "||": a != 0 or b != 0}
    for op, want in expect.items():
        assert cvalue.binary(op, a, b) == int(want)


@given(i32)
def test_unary(a: int) -> None:
    assert cvalue.unary("-", a) == c32(-a)
    assert cvalue.unary("+", a) == a
    assert cvalue.unary("!", a) == int(a == 0)


@pytest.mark.parametrize("n", list(range(-1, 41)) + [65536, 65537, 100000, cvalue.INT_MAX])
@pytest.mark.parametrize("k", [-1, 0, 1, 2, 16, 17, 33, 40, 65534, cvalue.INT_MAX - 1])
def test_nck_matches_math_comb(n: int, k: int) -> None:
    if n < 0 or k < 0 or k > n:
        assert cvalue.nck(n, k) == 0
        return
    k2 = min(k, n - k)
    want = math.comb(n, k2) if k2 <= 17 else None  # C(n, 18) > INT_MAX for every n >= 36
    if want is not None and want > cvalue.INT_MAX:
        want = None
    assert cvalue.nck(n, k) == want
