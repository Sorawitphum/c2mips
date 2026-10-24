"""Semantic checks (README 5.2). Collects every error before stopping.

M1 scope: `main` must exist with the right signature (E029). Constructs the parser accepts
but later milestones implement (variables M2, calls M3, user functions M4) are reported
as E030 instead of reaching codegen.
"""

from __future__ import annotations

from c2mips import ast
from c2mips.diagnostics import CompileError, Diagnostic
from c2mips.tokens import Pos


def analyze(prog: ast.Program) -> ast.Program:
    diags: list[Diagnostic] = []

    def unsupported(what: str, pos: Pos) -> None:
        diags.append(Diagnostic("E030", f"{what} are not supported yet", pos))

    def expr(e: ast.Expr) -> None:
        match e:
            case ast.IntLit():
                pass
            case ast.Var():
                unsupported("variables", e.pos)
            case ast.Assign():
                unsupported("assignments", e.pos)
                expr(e.value)
            case ast.Call():
                unsupported("function calls", e.pos)
                for a in e.args:
                    expr(a)
            case ast.Unary():
                expr(e.operand)
            case ast.Binary():
                expr(e.left)
                expr(e.right)

    def stmt(s: ast.Stmt) -> None:
        match s:
            case ast.Block():
                for x in s.stmts:
                    stmt(x)
            case ast.Decl():
                unsupported("variable declarations", s.pos)
                for _, init in s.items:
                    if init is not None:
                        expr(init)
            case ast.Return() | ast.ExprStmt():
                expr(s.expr)
            case ast.Printf():
                for a in s.args:
                    expr(a)
            case ast.Empty():
                pass

    mains = [f for f in prog.functions if f.name == "main" and f.body is not None]
    if not mains:
        diags.append(Diagnostic("E029", "no 'main' function", Pos(prog.pos.file, 1, 1)))
    for f in prog.functions:
        if f.name == "main" and f.params:
            diags.append(Diagnostic(
                "E029", "'main' must be declared as 'int main(void)' or 'int main()'", f.pos))
        if f.body is None:
            continue  # prototypes are harmless (c2mips.h declares nCk)
        if f.name != "main":
            unsupported("user-defined functions", f.pos)
        else:
            stmt(f.body)
    if diags:
        raise CompileError(diags)
    return prog
