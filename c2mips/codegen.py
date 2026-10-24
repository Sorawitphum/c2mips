"""AST -> AsmLine, following the templates of README 6.2-6.7 (accumulator $t0 + stack)."""

from __future__ import annotations

from dataclasses import dataclass

from c2mips import ast
from c2mips.tokens import Pos


@dataclass(frozen=True)
class StrRef:
    """A string operand; the emitter interns it and turns it into a __str<n> label."""

    text: str


@dataclass(frozen=True)
class Insn:
    op: str
    args: tuple[str | StrRef, ...] = ()
    comment: str = ""


@dataclass(frozen=True)
class Label:
    name: str
    comment: str = ""


@dataclass(frozen=True)
class Directive:
    text: str


@dataclass(frozen=True)
class Comment:
    """A column-0 comment echoing a C statement."""

    text: str


@dataclass(frozen=True)
class Blank:
    pass


AsmLine = Insn | Label | Directive | Comment | Blank

_PREC = {"+": 1, "-": 1, "*": 2, "/": 2}


def codegen(prog: ast.Program, source: str) -> list[AsmLine]:
    return _Codegen(source).program(prog)


def _depth(e: ast.Expr) -> int:
    match e:
        case ast.Unary():
            return 1 + _depth(e.operand)
        case ast.Binary():
            return 1 + max(_depth(e.left), _depth(e.right))
    return 0


def _render(e: ast.Expr) -> str:
    """C text of e with the fewest parentheses."""
    match e:
        case ast.IntLit():
            return str(e.value)
        case ast.Var():
            return e.name
        case ast.Unary():
            inner = _render(e.operand)
            if isinstance(e.operand, ast.Binary):
                inner = f"({inner})"
            return f"{e.op} {inner}" if inner.startswith(("-", "+")) else f"{e.op}{inner}"
        case ast.Binary():
            left, right = _render(e.left), _render(e.right)
            if isinstance(e.left, ast.Binary) and _PREC[e.left.op] < _PREC[e.op]:
                left = f"({left})"
            if isinstance(e.right, ast.Binary) and _PREC[e.right.op] <= _PREC[e.op]:
                right = f"({right})"
            return f"{left} {e.op} {right}"
        case ast.Assign():
            return f"{e.name} = {_render(e.value)}"
        case ast.Call():
            return f"{e.name}({', '.join(map(_render, e.args))})"
    raise TypeError(e)


def _describe(e: ast.Expr) -> str:
    """Short comment for the instruction that produces e (README appendix B style)."""
    if _depth(e) <= 2:
        return _render(e)
    if isinstance(e, ast.Binary):
        return f"... {e.op} ..."
    return "..."


class _Codegen:
    def __init__(self, source: str) -> None:
        self.lines: list[AsmLine] = []
        self.src_lines = source.replace("\r\n", "\n").split("\n")
        self.n_labels = 0
        self.fn = ""

    def emit(self, op: str, *args: str | StrRef, comment: str = "") -> None:
        self.lines.append(Insn(op, args, comment))

    def label(self, name: str, comment: str = "") -> None:
        self.lines.append(Label(name, comment))

    def new_label(self) -> int:
        self.n_labels += 1
        return self.n_labels

    def push(self, comment: str = "") -> None:
        self.emit("addiu", "$sp", "$sp", "-4")
        self.emit("sw", "$t0", "0($sp)", comment=comment)

    def pop_t1(self) -> None:
        self.emit("lw", "$t1", "0($sp)")
        self.emit("addiu", "$sp", "$sp", "4")

    def source_text(self, start: Pos, end: Pos) -> str:
        if start.line == end.line:
            text = self.src_lines[start.line - 1][start.col - 1:end.col - 1]
        else:
            parts = [self.src_lines[start.line - 1][start.col - 1:]]
            parts += self.src_lines[start.line:end.line - 1]
            parts.append(self.src_lines[end.line - 1][:end.col - 1])
            text = " ".join(p.strip() for p in parts)
        return text.strip()

    # -- program / functions ------------------------------------------------------

    def program(self, prog: ast.Program) -> list[AsmLine]:
        self.lines += [Directive(".text"), Directive(".globl main")]
        self.label("main", "entry stub (SPIM __start and MARS both enter here)")
        self.emit("jal", "f_main")
        self.emit("move", "$a0", "$v0")
        self.emit("li", "$v0", "17", comment="exit2(return value of main)")
        self.emit("syscall")
        for f in prog.functions:
            if f.body is not None:
                self.lines.append(Blank())
                self.function(f, f.body)
        return self.lines

    def function(self, f: ast.Function, body: ast.Block) -> None:
        self.fn = f.name
        self.label(f"f_{f.name}")
        self.emit("addiu", "$sp", "$sp", "-8", comment="prologue")
        self.emit("sw", "$ra", "4($sp)")
        self.emit("sw", "$fp", "0($sp)")
        self.emit("move", "$fp", "$sp")
        assert f.info is not None, "sema fills FuncInfo"
        if f.info.n_slots:
            slots = "  ".join(f"{s.name}@{s.offset}" for s in f.info.symbols)
            self.emit("addiu", "$sp", "$sp", str(-4 * f.info.n_slots), comment=f"locals: {slots}")
        for s in body.stmts:
            self.stmt(s)
        if not (body.stmts and isinstance(body.stmts[-1], ast.Return)):
            self.emit("move", "$v0", "$zero", comment="main returns 0 by default")
        self.label(f"L_epi_{f.name}")
        self.emit("move", "$sp", "$fp", comment="epilogue")
        self.emit("lw", "$fp", "0($sp)")
        self.emit("lw", "$ra", "4($sp)")
        self.emit("addiu", "$sp", "$sp", "8")
        self.emit("jr", "$ra")

    # -- statements -----------------------------------------------------------------

    def stmt(self, s: ast.Stmt) -> None:
        match s:
            case ast.Block():
                for x in s.stmts:
                    self.stmt(x)
                return
            case ast.Empty():
                return
        self.lines.append(Comment(self.source_text(s.pos, s.end)))
        match s:
            case ast.Return():
                self.expr(s.expr)
                self.emit("move", "$v0", "$t0")
                self.emit("b", f"L_epi_{self.fn}")
            case ast.ExprStmt():
                self.expr(s.expr)
            case ast.Printf():
                self.printf(s)
            case ast.Decl():
                for (_, init), sym in zip(s.items, s.symbols, strict=True):
                    if init is not None:  # no initializer: the slot keeps whatever was there
                        self.expr(init)
                        self.emit("sw", "$t0", f"{sym.offset}($fp)")

    def printf(self, s: ast.Printf) -> None:
        # README 4.5: evaluate every argument (pushed) before printing anything.
        for i, arg in enumerate(s.args):
            self.expr(arg)
            self.push(f"arg{i} = {_render(arg)}" if _depth(arg) <= 2 else f"arg{i}")
        n = len(s.args)
        k = 0
        for seg in s.segments:
            if isinstance(seg, ast.FmtD):
                self.emit("lw", "$a0", f"{4 * (n - 1 - k)}($sp)")
                self.emit("li", "$v0", "1")
                k += 1
            else:
                self.emit("la", "$a0", StrRef(seg))
                self.emit("li", "$v0", "4")
            self.emit("syscall")
        if n:
            self.emit("addiu", "$sp", "$sp", str(4 * n))

    # -- expressions (result in $t0) --------------------------------------------------

    def expr(self, e: ast.Expr) -> None:
        match e:
            case ast.IntLit():
                self.emit("li", "$t0", str(e.value))
            case ast.Var():
                assert e.resolved is not None, "sema resolves every Var"
                self.emit("lw", "$t0", f"{e.resolved.offset}($fp)")
            case ast.Assign():
                assert e.resolved is not None, "sema resolves every Assign"
                self.expr(e.value)
                self.emit("sw", "$t0", f"{e.resolved.offset}($fp)")  # value stays in $t0
            case ast.Unary():
                self.expr(e.operand)
                if e.op == "-":
                    self.emit("subu", "$t0", "$zero", "$t0", comment=_describe(e))
            case ast.Binary():
                self.expr(e.left)
                self.push()
                self.expr(e.right)
                self.pop_t1()
                self.binary(e)
            case ast.Call():
                self.call(e)

    def call(self, e: ast.Call) -> None:
        """README 6.3: push every argument, load $a0..$a(n-1) from the stack, pop, jal.

        Nothing stays in a register across the jal, so the callee may clobber $t*/$a*.
        """
        assert e.resolved is not None, "sema resolves every call (user functions: M4)"
        n = len(e.args)
        for i, arg in enumerate(e.args):
            self.expr(arg)
            self.push(f"{e.name} arg {_render(arg)}" if _depth(arg) <= 2 else f"{e.name} arg{i}")
        for i in reversed(range(n)):
            self.emit("lw", f"$a{i}", f"{4 * (n - 1 - i)}($sp)")
        if n:
            self.emit("addiu", "$sp", "$sp", str(4 * n))
        self.emit("jal", e.resolved.label)
        self.emit("move", "$t0", "$v0")

    def binary(self, e: ast.Binary) -> None:
        note = _describe(e)
        if e.op == "+":
            self.emit("addu", "$t0", "$t1", "$t0", comment=note)
        elif e.op == "-":
            self.emit("subu", "$t0", "$t1", "$t0", comment=note)
        elif e.op == "*":
            self.emit("mult", "$t1", "$t0")
            self.emit("mflo", "$t0", comment=note)
        else:  # "/" -- README 6.4 guard
            n = self.new_label()
            self.emit("beq", "$t0", "$zero", "__rt_div0", comment="divisor == 0 -> panic")
            self.emit("li", "$t2", "-1")
            self.emit("bne", "$t0", "$t2", f"L{n}_div")
            self.emit("subu", "$t0", "$zero", "$t1", comment="x / -1 == -x (wraps for INT_MIN)")
            self.emit("b", f"L{n}_end")
            self.label(f"L{n}_div")
            self.emit("div", "$t1", "$t0")
            self.emit("mflo", "$t0", comment=note)
            self.label(f"L{n}_end")
