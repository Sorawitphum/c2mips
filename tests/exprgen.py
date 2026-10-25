"""Shared by the fold and random-expression tests: evaluate an expression tree with the
c2mips semantics of Spec 4.3 (via c2mips.cvalue), and generate random ones (Spec 9.4)."""

from __future__ import annotations

import random

from c2mips import ast, cvalue
from c2mips.tokens import Pos

P = Pos("t.c", 1, 1)
PANIC = "panic"  # evaluating the expression stops the program (division by zero, nCk overflow)
OPS = ["+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=", "&&", "||"]


def evaluate(e: ast.Expr, env: dict[str, int]) -> int | str:
    """Value of e, or PANIC. Left before right; && and || only evaluate what C does."""
    match e:
        case ast.IntLit():
            return e.value
        case ast.Var():
            return env[e.name]
        case ast.Unary():
            v = evaluate(e.operand, env)
            return v if v == PANIC else cvalue.unary(e.op, int(v))
        case ast.Binary(op="&&" | "||"):
            a = evaluate(e.left, env)
            if a == PANIC:
                return PANIC
            if (a != 0) == (e.op == "||"):
                return int(e.op == "||")
            b = evaluate(e.right, env)
            return b if b == PANIC else int(b != 0)
        case ast.Binary():
            a, b = evaluate(e.left, env), evaluate(e.right, env)
            if a == PANIC or b == PANIC:
                return PANIC
            r = cvalue.binary(e.op, int(a), int(b))
            return PANIC if r is None else r
        case ast.Call(name="nCk", args=[n, k]):
            a, b = evaluate(n, env), evaluate(k, env)
            if a == PANIC or b == PANIC:
                return PANIC
            r = cvalue.nck(int(a), int(b))
            return PANIC if r is None else r
    raise TypeError(e)


def c_text(e: ast.Expr) -> str:
    """Fully parenthesised C source for e (INT_MIN cannot be a literal, Spec Q4)."""
    match e:
        case ast.IntLit(value=v):
            return "(-2147483647 - 1)" if v == cvalue.INT_MIN else f"({v})" if v < 0 else str(v)
        case ast.Var(name=n):
            return n
        case ast.Unary(op=op, operand=x):
            return f"({op}{c_text(x)})"
        case ast.Binary(op=op, left=a, right=b):
            return f"({c_text(a)} {op} {c_text(b)})"
        case ast.Call(name=n, args=args):
            return f"{n}({', '.join(map(c_text, args))})"
    raise TypeError(e)


INTERESTING = [0, 1, -1, 2, 7, cvalue.INT_MAX, cvalue.INT_MIN + 1, cvalue.INT_MIN]


def random_expr(rng: random.Random, depth: int, var_names: list[str]) -> ast.Expr:
    if depth == 0 or rng.random() < 0.25:
        if var_names and rng.random() < 0.4:
            return ast.Var(rng.choice(var_names), P)
        v = rng.choice(INTERESTING) if rng.random() < 0.6 else rng.randint(-1000, 1000)
        return ast.IntLit(v, P)
    r = rng.random()
    if r < 0.1:
        return ast.Unary(rng.choice("-!"), random_expr(rng, depth - 1, var_names), P)
    if r < 0.18:  # Spec 9.4: nCk(a, b) with a in [0, 40], b in [-2, 42]
        return ast.Call("nCk", [ast.IntLit(rng.randint(0, 40), P),
                                ast.IntLit(rng.randint(-2, 42), P)], P)
    return ast.Binary(rng.choice(OPS), random_expr(rng, depth - 1, var_names),
                      random_expr(rng, depth - 1, var_names), P)
