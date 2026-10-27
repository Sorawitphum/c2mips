"""Constant folding for -O1 (Spec 6.9): AST -> new AST, the input is not modified.

Only an operator whose operands are all constants is folded, with the semantics of
cvalue.py. A runtime error (x / 0, x % 0, nCk overflow) is never folded, so -O1 panics
exactly where -O0 does. No algebra (`x * 0` stays): x is still evaluated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from c2mips import ast, cvalue

# Builtins whose value is known at compile time for constant arguments.
_PURE_BUILTINS: dict[str, Callable[[int, int], int | None]] = {"nCk": cvalue.nck}


def fold(prog: ast.Program) -> ast.Program:
    return replace(prog, functions=[_function(f) for f in prog.functions])


def _function(f: ast.Function) -> ast.Function:
    return f if f.body is None else replace(f, body=_block(f.body))


def _block(b: ast.Block) -> ast.Block:
    return replace(b, stmts=[_stmt(s) for s in b.stmts])


def _opt(e: ast.Expr | None) -> ast.Expr | None:
    return None if e is None else fold_expr(e)


def _decl(d: ast.Decl) -> ast.Decl:
    return replace(d, items=[(name, _opt(init)) for name, init in d.items])


def _stmt(s: ast.Stmt) -> ast.Stmt:
    match s:
        case ast.Block():
            return _block(s)
        case ast.Decl():
            return _decl(s)
        case ast.Return() | ast.ExprStmt():
            return replace(s, expr=fold_expr(s.expr))
        case ast.Printf():
            return replace(s, args=[fold_expr(a) for a in s.args])
        case ast.If():
            return replace(s, cond=fold_expr(s.cond), then=_stmt(s.then),
                           else_=None if s.else_ is None else _stmt(s.else_))
        case ast.While():
            return replace(s, cond=fold_expr(s.cond), body=_stmt(s.body))
        case ast.For():
            init = _decl(s.init) if isinstance(s.init, ast.Decl) else _opt(s.init)
            return replace(s, init=init, cond=_opt(s.cond), step=_opt(s.step), body=_stmt(s.body))
        case ast.Empty() | ast.Scanf():
            return s
    raise TypeError(s)


def fold_expr(e: ast.Expr) -> ast.Expr:
    match e:
        case ast.IntLit() | ast.Var() | ast.MmioLoad():
            return e  # MMIO is volatile (ADR-010): never folded, merged or moved
        case ast.MmioStore():
            return replace(e, value=fold_expr(e.value))
        case ast.Assign():
            return replace(e, value=fold_expr(e.value))
        case ast.Unary():
            x = fold_expr(e.operand)
            if isinstance(x, ast.IntLit):
                return ast.IntLit(cvalue.unary(e.op, x.value), e.pos)
            return replace(e, operand=x)
        case ast.Binary(op="&&" | "||"):
            a = fold_expr(e.left)
            if isinstance(a, ast.IntLit) and (a.value != 0) == (e.op == "||"):
                return ast.IntLit(int(e.op == "||"), e.pos)  # the right side never runs
            b = fold_expr(e.right)
            if isinstance(a, ast.IntLit) and isinstance(b, ast.IntLit):
                return ast.IntLit(int(b.value != 0), e.pos)
            return replace(e, left=a, right=b)
        case ast.Binary():
            a, b = fold_expr(e.left), fold_expr(e.right)
            if isinstance(a, ast.IntLit) and isinstance(b, ast.IntLit):
                r = cvalue.binary(e.op, a.value, b.value)
                if r is not None:
                    return ast.IntLit(r, e.pos)
            return replace(e, left=a, right=b)
        case ast.Call():
            args = [fold_expr(a) for a in e.args]
            f = _PURE_BUILTINS.get(e.name)
            if f is not None and len(args) == 2:
                n, k = args
                if isinstance(n, ast.IntLit) and isinstance(k, ast.IntLit):
                    r = f(n.value, k.value)
                    if r is not None:
                        return ast.IntLit(r, e.pos)
            return replace(e, args=args)
    raise TypeError(e)
