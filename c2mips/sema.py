"""Semantic analysis (README 5.2, 5.3). Collects every error before stopping.

Binds every Var/Assign to a Symbol and gives every declaration its own frame slot
(README 6.2: slots are never reused across blocks), and every call of a builtin (nCk)
to its runtime routine. User-defined functions (M4) are still reported as E030.
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


@dataclass(frozen=True)
class BuiltinFunc:
    """A function implemented in runtime.s and declared in include/c2mips.h."""

    name: str
    arity: int
    label: str
    signature: str


BUILTINS = {"nCk": BuiltinFunc("nCk", 2, "__rt_nCk", "int nCk(int n, int k)")}


def analyze(prog: ast.Program) -> ast.Program:
    _Sema().program(prog)
    return prog


class _Sema:
    def __init__(self) -> None:
        self.diags: list[Diagnostic] = []
        self.scopes: list[dict[str, Symbol]] = []
        self.slots: list[Symbol] = []
        self.user_funcs: set[str] = set()

    def error(self, code: str, message: str, pos: Pos) -> None:
        self.diags.append(Diagnostic(code, message, pos))

    def unsupported(self, what: str, pos: Pos) -> None:
        self.error("E030", f"{what} are not supported yet", pos)

    def program(self, prog: ast.Program) -> None:
        mains = [f for f in prog.functions if f.name == "main" and f.body is not None]
        if not mains:
            self.error("E029", "no 'main' function", Pos(prog.pos.file, 1, 1))
        self.user_funcs = {f.name for f in prog.functions if f.name not in BUILTINS}
        for f in prog.functions:
            if f.name in BUILTINS:
                self.builtin_decl(f, BUILTINS[f.name])
                continue
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

    def builtin_decl(self, f: ast.Function, b: BuiltinFunc) -> None:
        """README 4.4 / Q16: a matching prototype (from c2mips.h) is fine; a body is not."""
        if f.body is not None:
            self.error("E024", f"'{b.name}' is a builtin and cannot be defined", f.pos)
        elif len(f.params) != b.arity:
            self.error("E024", f"conflicting prototype for builtin '{b.name}' "
                               f"(expected '{b.signature}')", f.pos)

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

    def find(self, name: str) -> Symbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def lookup(self, name: str, pos: Pos) -> Symbol | None:
        sym = self.find(name)
        if sym is None:
            self.error("E020", f"undeclared identifier '{name}'", pos)
        return sym

    def call(self, e: ast.Call) -> None:
        if self.find(e.name) is not None:  # a local variable hides the function, as in C
            self.error("E022", f"called object '{e.name}' is not a function", e.pos)
        elif (b := BUILTINS.get(e.name)) is not None:
            if len(e.args) != b.arity:
                self.error("E023", f"'{b.name}' expects {b.arity} arguments, got {len(e.args)}",
                           e.pos)
            else:
                e.resolved = b
        elif e.name in self.user_funcs:
            self.unsupported("calls to user-defined functions", e.pos)  # M4
        else:
            self.error("E022", f"call to undeclared function '{e.name}'", e.pos)
        for a in e.args:
            self.expr(a)

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
                self.call(e)
            case ast.Unary():
                self.expr(e.operand)
            case ast.Binary():
                self.expr(e.left)
                self.expr(e.right)
