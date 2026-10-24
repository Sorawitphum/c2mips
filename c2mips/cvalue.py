"""Reference evaluator for MiniC int arithmetic (README 4.3, 4.4, ADR-006, ADR-008).

Used by fold.py (-O1) and by the tests. `None` means "this is a runtime error": division
by zero or nCk overflow, which must stay in the program so it panics at runtime.
"""

from __future__ import annotations

import math

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1


def wrap32(v: int) -> int:
    """Two's complement wrap to int32, like addu/subu/mflo (and gcc -fwrapv)."""
    return (v + 2**31) % 2**32 - 2**31


def div(a: int, b: int) -> int | None:
    """a / b rounded toward zero; x / -1 == -x (wraps for INT_MIN)."""
    if b == 0:
        return None
    if b == -1:
        return wrap32(-a)
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def mod(a: int, b: int) -> int | None:
    """Remainder with the sign of a (C99); x % -1 == 0."""
    if b == 0:
        return None
    if b == -1:
        return 0
    q = div(a, b)
    assert q is not None
    return a - b * q


def nck(n: int, k: int) -> int | None:
    """README 4.4: 0 if n < 0, k < 0 or k > n; None if C(n, k) > INT_MAX."""
    if n < 0 or k < 0 or k > n:
        return 0
    k = min(k, n - k)
    if k > 17:  # C(n, k) >= C(2k, k) >= C(36, 18) > INT_MAX (README 6.8 point 6)
        return None
    v = math.comb(n, k)
    return v if v <= INT_MAX else None


def unary(op: str, a: int) -> int:
    if op == "-":
        return wrap32(-a)
    if op == "!":
        return int(a == 0)
    return a  # "+"


def binary(op: str, a: int, b: int) -> int | None:
    """Both operands already evaluated (for && and ||, fold.py decides what to evaluate)."""
    match op:
        case "+":
            return wrap32(a + b)
        case "-":
            return wrap32(a - b)
        case "*":
            return wrap32(a * b)
        case "/":
            return div(a, b)
        case "%":
            return mod(a, b)
        case "<":
            return int(a < b)
        case "<=":
            return int(a <= b)
        case ">":
            return int(a > b)
        case ">=":
            return int(a >= b)
        case "==":
            return int(a == b)
        case "!=":
            return int(a != b)
        case "&&":
            return int(a != 0 and b != 0)
        case "||":
            return int(a != 0 or b != 0)
    raise ValueError(op)
