"""AST (Spec 5.3). Every node has .pos; statements also have .end (just past their last token)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from c2mips.tokens import Pos

if TYPE_CHECKING:
    from c2mips.diagnostics import Diagnostic
    from c2mips.sema import BuiltinFunc, FuncInfo, Symbol


@dataclass
class IntLit:
    value: int
    pos: Pos


@dataclass
class Var:
    name: str
    pos: Pos
    resolved: Symbol | None = None  # filled by sema


@dataclass
class Assign:
    name: str
    value: Expr
    pos: Pos
    resolved: Symbol | None = None


@dataclass
class Unary:
    op: str  # "-" | "+" | "!"
    operand: Expr
    pos: Pos


@dataclass
class Binary:
    op: str  # + - * / %  < <= > >= == !=  && ||
    left: Expr
    right: Expr
    pos: Pos


@dataclass
class Call:
    name: str
    args: list[Expr]
    pos: Pos
    resolved: BuiltinFunc | FuncInfo | None = None  # filled by sema


@dataclass
class MmioLoad:
    """`*(volatile int*)ADDR` read (ADR-010): always a real lw, never folded or moved."""

    addr: int
    pos: Pos


@dataclass
class MmioStore:
    """`*(volatile int*)ADDR = value` (ADR-010): always a real sw."""

    addr: int
    value: Expr
    pos: Pos


Expr = IntLit | Var | Assign | Unary | Binary | Call | MmioLoad | MmioStore


@dataclass(frozen=True)
class FmtD:
    """A `%d` in a printf format."""


@dataclass
class Block:
    stmts: list[Stmt]
    pos: Pos
    end: Pos


@dataclass
class Decl:
    items: list[tuple[str, Expr | None]]
    pos: Pos
    end: Pos
    item_pos: list[Pos] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)  # filled by sema, one per item


@dataclass
class Return:
    expr: Expr
    pos: Pos
    end: Pos


@dataclass
class ExprStmt:
    expr: Expr
    pos: Pos
    end: Pos


@dataclass
class Empty:
    pos: Pos
    end: Pos


@dataclass
class Printf:
    segments: list[str | FmtD]
    args: list[Expr]
    pos: Pos
    end: Pos


@dataclass
class If:
    cond: Expr
    then: Stmt
    else_: Stmt | None
    pos: Pos
    end: Pos
    head_end: Pos  # just past the ")" of `if (cond)`


@dataclass
class While:
    cond: Expr
    body: Stmt
    pos: Pos
    end: Pos
    head_end: Pos


@dataclass
class For:
    init: Decl | Expr | None
    cond: Expr | None
    step: Expr | None
    body: Stmt
    pos: Pos
    end: Pos
    head_end: Pos


@dataclass
class Scanf:
    """`scanf("%d", &name);` (Spec FR-10) -> syscall 5 (read_int)."""

    name: str
    pos: Pos
    end: Pos
    name_pos: Pos
    resolved: Symbol | None = None  # filled by sema


Stmt = Block | Decl | Return | ExprStmt | Empty | Printf | If | While | For | Scanf


@dataclass
class Function:
    name: str
    params: list[str]
    body: Block | None  # None = prototype
    pos: Pos  # position of the name
    param_pos: list[Pos] = field(default_factory=list)
    info: FuncInfo | None = None  # filled by sema


@dataclass
class Program:
    functions: list[Function]
    pos: Pos
    warnings: list[Diagnostic] = field(default_factory=list)  # filled by sema


def quote(s: str) -> str:
    """C-style string literal for s (used by --emit=ast and asm comments)."""
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{out}"'


_UNARY_NAMES = {"-": "neg", "+": "pos", "!": "!"}


def sexpr(node: Program | Function | Stmt | Expr) -> str:
    """S-expression used by --emit=ast and parser snapshot tests."""
    match node:
        case Program(functions=fns):
            return "(" + " ".join(["program", *map(sexpr, fns)]) + ")"
        case Function(name=name, params=params, body=None):
            return f"(prototype {name} ({' '.join(params)}))"
        case Function(name=name, params=params, body=Block() as body):
            return f"(function {name} ({' '.join(params)}) {sexpr(body)})"
        case Block(stmts=stmts):
            return "(" + " ".join(["block", *map(sexpr, stmts)]) + ")"
        case Decl(items=items):
            parts = [f"({n})" if e is None else f"({n} {sexpr(e)})" for n, e in items]
            return "(" + " ".join(["decl", *parts]) + ")"
        case Return(expr=e):
            return f"(return {sexpr(e)})"
        case ExprStmt(expr=e):
            return f"(expr {sexpr(e)})"
        case Empty():
            return "(empty)"
        case If(cond=c, then=t, else_=e):
            return "(" + " ".join(["if", sexpr(c), sexpr(t)] + ([sexpr(e)] if e else [])) + ")"
        case While(cond=c, body=b):
            return f"(while {sexpr(c)} {sexpr(b)})"
        case For(init=i, cond=c, step=st, body=b):
            parts = ["_" if x is None else sexpr(x) for x in (i, c, st)]
            return "(" + " ".join(["for", *parts, sexpr(b)]) + ")"
        case Scanf(name=name):
            return f"(scanf {name})"
        case Printf(segments=segs, args=args):
            fmt = " ".join("%d" if isinstance(s, FmtD) else quote(s) for s in segs)
            return "(" + " ".join(["printf", f"({fmt})", *map(sexpr, args)]) + ")"
        case IntLit(value=v):
            return str(v)
        case Var(name=name):
            return name
        case Assign(name=name, value=v):
            return f"(= {name} {sexpr(v)})"
        case Unary(op=op, operand=e):
            return f"({_UNARY_NAMES[op]} {sexpr(e)})"
        case Binary(op=op, left=a, right=b):
            return f"({op} {sexpr(a)} {sexpr(b)})"
        case Call(name=name, args=args):
            return "(" + " ".join(["call", name, *map(sexpr, args)]) + ")"
        case MmioLoad(addr=a):
            return f"(mmio 0x{a:08x})"
        case MmioStore(addr=a, value=v):
            return f"(mmio= 0x{a:08x} {sexpr(v)})"
    raise TypeError(node)
