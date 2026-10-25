"""Random MiniC programs for differential testing, and a shrinker (Spec 9.4).

    python tests/random/gen.py --seed S              # print prog.c
    python tests/random/gen.py --seed S --expected   # print what it must output

A program is a few user functions, some int variables, and statements that either print
or assign a random expression (depth <= 5). Every expression is evaluated here with
cvalue.py first, and is regenerated if it hits C undefined behaviour (x / 0, x % 0,
INT_MIN / -1, INT_MIN % -1: gcc could not be the oracle) or a c2mips panic (nCk overflow).
"""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path

if __package__ in (None, "") and __name__ == "__main__":  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from c2mips import ast, cvalue  # noqa: E402
from c2mips.tokens import Pos  # noqa: E402

P = Pos("gen.c", 1, 1)
INT_MIN, INT_MAX = cvalue.INT_MIN, cvalue.INT_MAX
LEAVES = [0, 1, -1, 2, 7, INT_MAX, INT_MIN + 1, INT_MIN]
OPS = ["+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=", "&&", "||"]
MAX_DEPTH = 5


class Reject(Exception):
    """The expression is C undefined behaviour, or it makes c2mips panic."""


@dataclass(frozen=True)
class Func:
    name: str
    params: tuple[str, ...]
    body: ast.Expr  # int f(params) { return body; }


@dataclass(frozen=True)
class Stmt:
    target: str | None  # None: printf("%d\n", expr);  else: target = expr;
    expr: ast.Expr


@dataclass(frozen=True)
class Prog:
    funcs: tuple[Func, ...]
    init: tuple[tuple[str, int], ...]
    stmts: tuple[Stmt, ...]


# -- meaning ----------------------------------------------------------------------------

def evaluate(e: ast.Expr, env: dict[str, int], funcs: dict[str, Func]) -> int:
    match e:
        case ast.IntLit():
            return e.value
        case ast.Var():
            return env[e.name]
        case ast.Unary():
            return cvalue.unary(e.op, evaluate(e.operand, env, funcs))
        case ast.Binary(op="&&" | "||"):
            a = evaluate(e.left, env, funcs)
            if (a != 0) == (e.op == "||"):
                return int(e.op == "||")  # the right side is not evaluated, as in C
            return int(evaluate(e.right, env, funcs) != 0)
        case ast.Binary():
            a, b = evaluate(e.left, env, funcs), evaluate(e.right, env, funcs)
            if e.op in ("/", "%") and (b == 0 or (b == -1 and a == INT_MIN)):
                raise Reject(f"{a} {e.op} {b}")
            r = cvalue.binary(e.op, a, b)
            assert r is not None
            return r
        case ast.Call(name="nCk", args=[n, k]):
            r = cvalue.nck(evaluate(n, env, funcs), evaluate(k, env, funcs))
            if r is None:
                raise Reject("nCk overflow")
            return r
        case ast.Call():
            f = funcs[e.name]
            args = [evaluate(a, env, funcs) for a in e.args]
            return evaluate(f.body, dict(zip(f.params, args, strict=True)), funcs)
    raise TypeError(e)


def expected(prog: Prog) -> str:
    """The program's stdout. Raises Reject if any statement is invalid."""
    funcs = {f.name: f for f in prog.funcs}
    env = dict(prog.init)
    out = []
    for st in prog.stmts:
        v = evaluate(st.expr, env, funcs)
        if st.target is None:
            out.append(f"{v}\n")
        else:
            env[st.target] = v
    return "".join(out)


def valid(prog: Prog) -> bool:
    try:
        expected(prog)
    except Reject:
        return False
    return True


# -- C source ---------------------------------------------------------------------------

def c_text(e: ast.Expr) -> str:
    match e:
        case ast.IntLit(value=v):
            return "(-2147483647 - 1)" if v == INT_MIN else f"({v})" if v < 0 else str(v)
        case ast.Var(name=n):
            return n
        case ast.Unary(op=op, operand=x):
            return f"({op}{c_text(x)})"
        case ast.Binary(op=op, left=a, right=b):
            return f"({c_text(a)} {op} {c_text(b)})"
        case ast.Call(name=n, args=args):
            return f"{n}({', '.join(map(c_text, args))})"
    raise TypeError(e)


def calls_in(e: ast.Expr) -> set[str]:
    match e:
        case ast.Unary():
            return calls_in(e.operand)
        case ast.Binary():
            return calls_in(e.left) | calls_in(e.right)
        case ast.Call():
            inner = set().union(*map(calls_in, e.args)) if e.args else set()
            return inner | ({e.name} if e.name != "nCk" else set())
    return set()


def used_funcs(prog: Prog) -> list[Func]:
    """Functions reachable from main (bodies may call earlier functions)."""
    by_name = {f.name: f for f in prog.funcs}
    todo = set().union(*(calls_in(s.expr) for s in prog.stmts)) if prog.stmts else set()
    seen: set[str] = set()
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo |= calls_in(by_name[name].body)
    return [f for f in prog.funcs if f.name in seen]


def render(prog: Prog) -> str:
    out = ['#include <stdio.h>\n#include "c2mips.h"\n\n']
    for f in used_funcs(prog):
        params = ", ".join(f"int {p}" for p in f.params) or "void"
        out.append(f"int {f.name}({params}) {{\n    return {c_text(f.body)};\n}}\n\n")
    out.append("int main(void) {\n")
    for name, v in prog.init:
        out.append(f"    int {name} = {'-2147483647 - 1' if v == INT_MIN else v};\n")
    for st in prog.stmts:
        if st.target is None:
            out.append(f'    printf("%d\\n", {c_text(st.expr)});\n')
        else:
            out.append(f"    {st.target} = {c_text(st.expr)};\n")
    out.append("    return 0;\n}\n")
    return "".join(out)


# -- generation -------------------------------------------------------------------------

def _leaf(rng: random.Random, names: list[str]) -> ast.Expr:
    if names and rng.random() < 0.4:
        return ast.Var(rng.choice(names), P)
    v = rng.choice(LEAVES) if rng.random() < 0.6 else rng.randint(-1000, 1000)
    return ast.IntLit(v, P)


def _expr(rng: random.Random, depth: int, names: list[str], funcs: list[Func]) -> ast.Expr:
    if depth == 0 or rng.random() < 0.25:
        return _leaf(rng, names)
    r = rng.random()
    if r < 0.1:
        return ast.Unary(rng.choice("-!"), _expr(rng, depth - 1, names, funcs), P)
    if r < 0.17:  # Spec 9.4: nCk(a, b), a in [0, 40], b in [-2, 42]
        return ast.Call("nCk", [ast.IntLit(rng.randint(0, 40), P),
                                ast.IntLit(rng.randint(-2, 42), P)], P)
    if r < 0.27 and funcs:
        f = rng.choice(funcs)
        return ast.Call(f.name, [_expr(rng, depth - 1, names, funcs) for _ in f.params], P)
    return ast.Binary(rng.choice(OPS), _expr(rng, depth - 1, names, funcs),
                      _expr(rng, depth - 1, names, funcs), P)


def generate(seed: int) -> Prog:
    rng = random.Random(seed)
    funcs: list[Func] = []
    for i in range(rng.randint(0, 2)):
        params = ("a", "b")[:rng.randint(1, 2)]
        # a body may call the functions defined before it (no recursion: always terminates)
        funcs.append(Func(f"f{i}", params, _expr(rng, 3, list(params), funcs)))
    init = tuple((f"v{i}", rng.choice(LEAVES) if rng.random() < 0.5 else rng.randint(-99, 99))
                 for i in range(rng.randint(1, 4)))
    names = [n for n, _ in init]
    by_name = {f.name: f for f in funcs}
    env = dict(init)
    stmts = []
    for _ in range(rng.randint(3, 10)):
        target = rng.choice(names) if rng.random() < 0.3 else None
        for _attempt in range(50):
            e = _expr(rng, MAX_DEPTH, names, funcs)
            try:
                v = evaluate(e, env, by_name)
                break
            except Reject:
                continue
        else:
            e, v = ast.IntLit(0, P), 0
        if target is not None:
            env[target] = v
        stmts.append(Stmt(target, e))
    return Prog(tuple(funcs), init, tuple(stmts))


# -- shrinking --------------------------------------------------------------------------

def _children(e: ast.Expr) -> list[ast.Expr]:
    match e:
        case ast.Unary():
            return [e.operand]
        case ast.Binary():
            return [e.left, e.right]
        case ast.Call():
            return list(e.args)
    return []


def _with_child(e: ast.Expr, i: int, c: ast.Expr) -> ast.Expr:
    match e:
        case ast.Unary():
            return replace(e, operand=c)
        case ast.Binary():
            return replace(e, left=c) if i == 0 else replace(e, right=c)
        case ast.Call():
            return replace(e, args=[c if j == i else a for j, a in enumerate(e.args)])
    raise TypeError(e)


def _substitute(e: ast.Expr, env: dict[str, ast.Expr]) -> ast.Expr:
    if isinstance(e, ast.Var):
        return env.get(e.name, e)
    kids = _children(e)
    for i, k in enumerate(kids):
        e = _with_child(e, i, _substitute(k, env))
    return e


def _simpler(e: ast.Expr, funcs: dict[str, Func]) -> Iterator[ast.Expr]:
    """Smaller replacements for e: a leaf, a child, an inlined call, or a simpler child."""
    if not (isinstance(e, ast.IntLit) and e.value in (0, 1)):
        yield ast.IntLit(0, P)
        yield ast.IntLit(1, P)
    kids = _children(e)
    yield from kids
    if isinstance(e, ast.Call) and e.name in funcs:
        f = funcs[e.name]
        yield _substitute(f.body, dict(zip(f.params, e.args, strict=True)))
    for i, k in enumerate(kids):
        for k2 in _simpler(k, funcs):
            yield _with_child(e, i, k2)


def _nodes(e: ast.Expr) -> int:
    return 1 + sum(map(_nodes, _children(e)))


def size(prog: Prog) -> int:
    """Expression nodes in main and in the functions it uses."""
    return (sum(_nodes(s.expr) for s in prog.stmts)
            + sum(_nodes(f.body) for f in used_funcs(prog)))


def _cost(prog: Prog) -> tuple[int, int, int]:
    def lits(e: ast.Expr) -> int:
        own = abs(e.value) if isinstance(e, ast.IntLit) else 0
        return own + sum(map(lits, _children(e)))
    return size(prog), len(prog.stmts), sum(lits(s.expr) for s in prog.stmts)


def _candidates(prog: Prog) -> Iterator[Prog]:
    stmts, funcs = prog.stmts, {f.name: f for f in prog.funcs}
    for i in range(len(stmts)):
        yield replace(prog, stmts=stmts[:i] + stmts[i + 1:])
    for i, st in enumerate(stmts):
        if st.target is not None:  # an assignment that matters may still print instead
            yield replace(prog, stmts=stmts[:i] + (Stmt(None, st.expr),) + stmts[i + 1:])
        for e2 in _simpler(st.expr, funcs):
            yield replace(prog, stmts=stmts[:i] + (Stmt(st.target, e2),) + stmts[i + 1:])
    for j, f in enumerate(prog.funcs):
        for b2 in _simpler(f.body, funcs):
            new = replace(f, body=b2)
            yield replace(prog, funcs=prog.funcs[:j] + (new,) + prog.funcs[j + 1:])


def shrink(prog: Prog, fails: Callable[[Prog], bool], max_tries: int = 5000) -> Prog:
    """Greedy: keep taking the first valid, cheaper candidate that still fails."""
    tries = 0
    improved = True
    while improved and tries < max_tries:
        improved = False
        for cand in _candidates(prog):
            if _cost(cand) >= _cost(prog) or not valid(cand):
                continue
            tries += 1
            if fails(cand):
                prog, improved = cand, True
                break
            if tries >= max_tries:
                break
    return prog


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--expected", action="store_true", help="print the expected stdout")
    args = p.parse_args(argv)
    prog = generate(args.seed)
    sys.stdout.write(expected(prog) if args.expected else render(prog))
    return 0


if __name__ == "__main__":
    sys.exit(main())
