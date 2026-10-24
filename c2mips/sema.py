"""Semantic analysis (README 5.2, 5.3). Collects every error before stopping.

Binds every Var/Assign to a Symbol and gives every declaration its own frame slot
(README 6.2: slots are never reused across blocks). Calls (M3) and user-defined
functions (M4) are still reported as E030 until those milestones land.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from c2mips import ast
from c2mips.diagnostics import CompileError, Diagnostic
from c2mips.tokens import Pos


class SymKind(enum.Enum):
    LOCAL = "local"
    PARAM = "param"
    FUNC = "func"
    BUILTIN = "builtin"


@dataclass(eq=False)
class Symbol:
    name: str
    kind: SymKind
    slot: int | None

    @property
    def offset(self) -> int:
        """Offset from $fp: slot i -> -4*(i+1)."""
        assert self.slot is not None
        return -4 * (self.slot + 1)


@dataclass
class FuncInfo:
    name: str
    n_params: int
    n_slots: int
    label: str
    symbols: list[Symbol] = field(default_factory=list)  # slot order


def analyze(prog: ast.Program) -> ast.Program:
    _Sema().program(prog)
    return prog


class _Sema:
    def __init__(self) -> None:
        self.diags: list[Diagnostic] = []
        self.scopes: list[dict[str, Symbol]] = []
        self.slots: list[Symbol] = []

    def error(self, code: str, message: str, pos: Pos) -> None:
        self.diags.append(Diagnostic(code, message, pos))

    def unsupported(self, what: str, pos: Pos) -> None:
        self.error("E030", f"{what} are not supported yet", pos)

    def program(self, prog: ast.Program) -> None:
        mains = [f for f in prog.functions if f.name == "main" and f.body is not None]
        if not mains:
            self.error("E029", "no 'main' function", Pos(prog.pos.file, 1, 1))
        for f in prog.functions:
            if f.name == "main" and f.params:
                self.error("E029", "'main' must be declared as 'int main(void)' or "
                                   "'int main()'", f.pos)
            if f.body is None:
                continue  # prototypes are harmless (c2mips.h declares nCk)
            if f.name != "main":
                self.unsupported("user-defined functions", f.pos)
            else:
                self.function(f, f.body)
        if self.diags:
            raise CompileError(self.diags)

    # -- scopes ---------------------------------------------------------------------

    def declare(self, name: str, kind: SymKind, pos: Pos) -> Symbol:
        sym = Symbol(name, kind, len(self.slots))
        self.slots.append(sym)
        scope = self.scopes[-1]
        if name in scope:
            self.error("E021", f"redeclaration of '{name}'", pos)
        else:
            scope[name] = sym
        return sym

    def lookup(self, name: str, pos: Pos) -> Symbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self.error("E020", f"undeclared identifier '{name}'", pos)
        return None

    def function(self, f: ast.Function, body: ast.Block) -> None:
        self.slots = []
        # C 6.2.1p4: parameters and the outermost block of the body share one scope.
        self.scopes = [{}]
        for name, pos in zip(f.params, f.param_pos, strict=True):
            self.declare(name, SymKind.PARAM, pos)
        for s in body.stmts:
            self.stmt(s)
        self.scopes = []
        f.info = FuncInfo(f.name, len(f.params), len(self.slots), f"f_{f.name}", self.slots)

    # -- statements / expressions ---------------------------------------------------

    def stmt(self, s: ast.Stmt) -> None:
        match s:
            case ast.Block():
                self.scopes.append({})
                for x in s.stmts:
                    self.stmt(x)
                self.scopes.pop()
            case ast.Decl():
                s.symbols = []
                for (name, init), pos in zip(s.items, s.item_pos, strict=True):
                    # C 6.2.1p7: the scope starts right after the declarator, so the
                    # initializer already sees the new variable.
                    s.symbols.append(self.declare(name, SymKind.LOCAL, pos))
                    if init is not None:
                        self.expr(init)
            case ast.Return() | ast.ExprStmt():
                self.expr(s.expr)
            case ast.Printf():
                for a in s.args:
                    self.expr(a)
            case ast.Empty():
                pass

    def expr(self, e: ast.Expr) -> None:
        match e:
            case ast.IntLit():
                pass
            case ast.Var():
                e.resolved = self.lookup(e.name, e.pos)
            case ast.Assign():
                e.resolved = self.lookup(e.name, e.pos)
                self.expr(e.value)
            case ast.Call():
                self.unsupported("function calls", e.pos)
                for a in e.args:
                    self.expr(a)
            case ast.Unary():
                self.expr(e.operand)
            case ast.Binary():
                self.expr(e.left)
                self.expr(e.right)
