"""The random program generator and shrinker themselves (Spec 9.4), without SPIM or gcc."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import gen
import pytest

from c2mips import ast, cvalue
from c2mips.driver import compile_program

P = ast.Pos("t.c", 1, 1)
SEEDS = range(200)


def lit(v: int) -> ast.IntLit:
    return ast.IntLit(v, P)


def binop(op: str, a: ast.Expr, b: ast.Expr) -> ast.Binary:
    return ast.Binary(op, a, b, P)


def test_same_seed_same_program() -> None:
    assert gen.render(gen.generate(7)) == gen.render(gen.generate(7))
    assert gen.render(gen.generate(7)) != gen.render(gen.generate(8))


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_programs_are_valid(seed: int) -> None:
    prog = gen.generate(seed)
    src = gen.render(prog)
    gen.expected(prog)  # no Reject: no C UB, no runtime panic
    assert src.isascii()
    for opt in (0, 1):
        _, warnings = compile_program(src, "r.c", runtime=False, opt=opt)
        assert warnings == []


def test_generator_covers_the_language() -> None:
    text = "".join(gen.render(gen.generate(s)) for s in SEEDS)
    for token in [" + ", " - ", " * ", " / ", " % ", " < ", " <= ", " > ", " >= ", " == ",
                  " != ", " && ", " || ", "(-", "(!", "nCk(", "f0(", "f1(", " = ",
                  "(-2147483647 - 1)", "2147483647"]:
        assert token in text, token


@pytest.mark.parametrize(("e", "rejected"), [
    (binop("/", lit(1), lit(0)), True),
    (binop("%", lit(1), lit(0)), True),
    (binop("/", lit(cvalue.INT_MIN), lit(-1)), True),   # traps on x86 gcc (Q25)
    (binop("%", lit(cvalue.INT_MIN), lit(-1)), True),
    (ast.Call("nCk", [lit(34), lit(16)], P), True),     # c2mips panics (exit 70)
    (binop("/", lit(cvalue.INT_MIN + 1), lit(-1)), False),
    (binop("%", lit(7), lit(-1)), False),
    (binop("&&", lit(0), binop("/", lit(1), lit(0))), False),  # never evaluated
    (binop("+", lit(cvalue.INT_MAX), lit(1)), False),   # wraps, like gcc -fwrapv
])
def test_reject_rules(e: ast.Expr, rejected: bool) -> None:
    if rejected:
        with pytest.raises(gen.Reject):
            gen.evaluate(e, {}, {})
    else:
        gen.evaluate(e, {}, {})


def test_shrink_finds_a_minimal_failing_program() -> None:
    prog = next(p for p in map(gen.generate, SEEDS) if " / " in gen.render(p))

    def fails(p: gen.Prog) -> bool:  # stands in for "SPIM, gcc and cvalue disagree"
        return " / " in gen.render(p)

    small = gen.shrink(prog, fails)
    assert fails(small)
    gen.expected(small)  # still a valid program
    assert len(small.stmts) == 1
    assert gen.size(small) <= 3  # one division of two leaves
    assert gen.size(small) < gen.size(prog)


def test_cli_prints_program_and_expected_output() -> None:
    script = Path(gen.__file__)
    src = subprocess.run([sys.executable, str(script), "--seed", "3"], capture_output=True,
                         text=True, check=True).stdout
    out = subprocess.run([sys.executable, str(script), "--seed", "3", "--expected"],
                         capture_output=True, text=True, check=True).stdout
    assert src == gen.render(gen.generate(3))
    assert out == gen.expected(gen.generate(3))
