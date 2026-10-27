"""Semantic analysis (Spec 5.2, 5.3). Collects every error before stopping.

Binds every Var/Assign to a Symbol and gives every declaration its own frame slot
(Spec 6.2: slots are never reused across blocks; parameters take the first slots), and
every call to the runtime routine (nCk) or user function it names.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from c2mips import ast
from c2mips.diagnostics import CompileError, Diagnostic
from c2mips.tokens import Pos

MAX_PARAMS = 4  # $a0-$a3; stack parameters are not implemented (Spec 6.2)


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


@dataclass(eq=False)
class FuncInfo:
    name: str
    n_params: int
    n_slots: int
    label: str
    symbols: list[Symbol] = field(default_factory=list)  # slot order
    falls_through: bool = False  # the end of the body is reachable: returns 0 (W001)


@dataclass(frozen=True)
class BuiltinFunc:
    """A function implemented in runtime.s and declared in include/c2mips.h."""

    name: str
    arity: int
    label: str
    signature: str


BUILTINS = {"nCk": BuiltinFunc("nCk", 2, "__rt_nCk", "int nCk(int n, int k)")}


def analyze(prog: ast.Program, target: str = "spim") -> ast.Program:
    """Raises CompileError if there is any error; warnings end up in prog.warnings."""
    _Sema(target).program(prog)
    return prog


def always_returns(s: ast.Stmt) -> bool:
    """True if control can never run off the end of s. MiniC has no `break`, so a loop
    whose condition is a nonzero constant (or absent, in `for`) never completes."""
    match s:
        case ast.Return():
            return True
        case ast.Block():
            return any(always_returns(x) for x in s.stmts)
        case ast.If():
            return s.else_ is not None and always_returns(s.then) and always_returns(s.else_)
        case ast.While():
            return isinstance(s.cond, ast.IntLit) and s.cond.value != 0
        case ast.For():
            return s.cond is None or (isinstance(s.cond, ast.IntLit) and s.cond.value != 0)
    return False


class _Sema:
    def __init__(self, target: str = "spim") -> None:
        self.target = target
        self.diags: list[Diagnostic] = []
        self.scopes: list[dict[str, Symbol]] = []
        self.slots: list[Symbol] = []
        self.defined: dict[str, FuncInfo] = {}  # user functions with a body
        self.visible: set[str] = set()  # user functions declared so far (C needs it first)

    def error(self, code: str, message: str, pos: Pos) -> None:
        self.diags.append(Diagnostic(code, message, pos))

    def program(self, prog: ast.Program) -> None:
        if not any(f.name == "main" and f.body is not None for f in prog.functions):
            self.error("E029", "no 'main' function", Pos(prog.pos.file, 1, 1))
        first_bodies = self.declarations(prog)
        for f in prog.functions:
            if f.name in BUILTINS:
                continue
            self.visible.add(f.name)  # from here on, including its own body (recursion)
            if f.body is not None and id(f) in first_bodies:
                self.function(f, f.body)
        if any(not d.code.startswith("W") for d in self.diags):
            raise CompileError(self.diags)
        prog.warnings = self.diags

    def declarations(self, prog: ast.Program) -> set[int]:
        """Check every function header; make a FuncInfo for every definition up front so
        calls can resolve to it before its body is analyzed."""
        params: dict[str, int] = {}
        first_bodies: set[int] = set()  # id() of the first definition of each name
        for f in prog.functions:
            if f.name in BUILTINS:
                self.builtin_decl(f, BUILTINS[f.name])
                continue
            if f.name == "main" and f.params:
                self.error("E029", "'main' must be declared as 'int main(void)' or "
                                   "'int main()'", f.pos)
            if len(f.params) > MAX_PARAMS:
                self.error("E028", f"too many parameters (at most {MAX_PARAMS})",
                           f.param_pos[MAX_PARAMS])
            if f.name not in params:
                params[f.name] = len(f.params)
            elif params[f.name] != len(f.params):
                self.error("E021", f"conflicting declaration of '{f.name}' "
                                   f"({len(f.params)} parameters, previously "
                                   f"{params[f.name]})", f.pos)
            if f.body is None:
                continue
            if f.name in self.defined:
                self.error("E021", f"redefinition of '{f.name}'", f.pos)
                continue
            self.defined[f.name] = FuncInfo(f.name, len(f.params), 0, f"f_{f.name}")
            first_bodies.add(id(f))
        return first_bodies

    def builtin_decl(self, f: ast.Function, b: BuiltinFunc) -> None:
        """Spec 4.4 / Q16: a matching prototype (from c2mips.h) is fine; a body is not."""
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
        arity: int | None = None
        target: BuiltinFunc | FuncInfo | None = None
        if self.find(e.name) is not None:  # a local variable hides the function, as in C
            self.error("E022", f"called object '{e.name}' is not a function", e.pos)
        elif (b := BUILTINS.get(e.name)) is not None:
            arity, target = b.arity, b
        elif e.name not in self.visible:
            self.error("E022", f"call to undeclared function '{e.name}'", e.pos)
        elif (info := self.defined.get(e.name)) is None:
            self.error("E022", f"'{e.name}' is declared but never defined", e.pos)
        else:
            arity, target = info.n_params, info
        if arity is not None:
            if len(e.args) != arity:
                self.error("E023", f"'{e.name}' expects {arity} arguments, got {len(e.args)}",
                           e.pos)
            else:
                e.resolved = target
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
        info = self.defined[f.name]
        info.n_slots, info.symbols = len(self.slots), self.slots
        info.falls_through = not always_returns(body)
        f.info = info
        if info.falls_through and f.name != "main":  # main returns 0 (C99 5.1.2.2.3)
            close = Pos(body.end.file, body.end.line, body.end.col - 1)
            self.error("W001", f"control may reach the end of '{f.name}' without a return; "
                               "it returns 0", close)

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
                if self.target == "fpga":  # ADR-009: no OS, no stdout
                    self.error("E032", "'printf' is not available on --target fpga; "
                                       "write to SEG7/LED instead", s.pos)
                for a in s.args:
                    self.expr(a)
            case ast.Scanf():
                if self.target == "fpga":
                    self.error("E032", "'scanf' is not available on --target fpga; "
                                       "read SWITCH instead", s.pos)
                s.resolved = self.lookup(s.name, s.name_pos)
            case ast.If():
                self.expr(s.cond)
                self.stmt(s.then)
                if s.else_ is not None:
                    self.stmt(s.else_)
            case ast.While():
                self.expr(s.cond)
                self.stmt(s.body)
            case ast.For():
                self.scopes.append({})  # C99 6.8.5p5: `for (int i ...)` has its own scope
                if isinstance(s.init, ast.Decl):
                    self.stmt(s.init)
                elif s.init is not None:
                    self.expr(s.init)
                for e in (s.cond, s.step):
                    if e is not None:
                        self.expr(e)
                self.stmt(s.body)
                self.scopes.pop()
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
            case ast.MmioLoad():
                pass
            case ast.MmioStore():
                self.expr(e.value)
            case ast.Unary():
                self.expr(e.operand)
            case ast.Binary():
                self.expr(e.left)
                self.expr(e.right)
