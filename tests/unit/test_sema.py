"""Sema: scopes, shadowing, one slot per declaration, FuncInfo (Spec 5.3, 6.2, 9.2)."""

from __future__ import annotations

import pytest

from c2mips import ast
from c2mips.diagnostics import CompileError
from c2mips.lexer import lex
from c2mips.parser import parse
from c2mips.sema import Symbol, SymKind, analyze


def main_of(src: str) -> ast.Function:
    prog = analyze(parse(lex(f"int main(void) {{ {src} }}", "t.c")))
    (fn,) = prog.functions
    return fn


def all_nodes(node: object) -> list[object]:
    """Every AST node under node, in source order."""
    out = [node]
    match node:
        case ast.Function(body=ast.Block() as b):
            out += all_nodes(b)
        case ast.Block(stmts=stmts):
            for s in stmts:
                out += all_nodes(s)
        case ast.Decl(items=items):
            for _, e in items:
                if e is not None:
                    out += all_nodes(e)
        case ast.Return(expr=e) | ast.ExprStmt(expr=e):
            out += all_nodes(e)
        case ast.Printf(args=args):
            for a in args:
                out += all_nodes(a)
        case ast.Assign(value=v):
            out += all_nodes(v)
        case ast.Unary(operand=e):
            out += all_nodes(e)
        case ast.Binary(left=a, right=b):
            out += all_nodes(a) + all_nodes(b)
    return out


def uses(fn: ast.Function) -> list[tuple[str, int | None]]:
    """(name, slot) of every Var/Assign in source order."""
    return [(n.name, n.resolved.slot if n.resolved else None)
            for n in all_nodes(fn) if isinstance(n, ast.Var | ast.Assign)]


def decls(fn: ast.Function) -> list[tuple[str, int | None]]:
    return [(s.name, s.slot) for n in all_nodes(fn) if isinstance(n, ast.Decl)
            for s in n.symbols]


def test_every_declaration_gets_its_own_slot_in_order() -> None:
    fn = main_of("int a; { int b; int a; } { int b; } int c, d;")
    assert decls(fn) == [("a", 0), ("b", 1), ("a", 2), ("b", 3), ("c", 4), ("d", 5)]
    assert fn.info is not None
    assert (fn.info.name, fn.info.n_params, fn.info.n_slots, fn.info.label) == (
        "main", 0, 6, "f_main")
    assert [s.name for s in fn.info.symbols] == ["a", "b", "a", "b", "c", "d"]


def test_shadowing_resolves_to_innermost() -> None:
    fn = main_of("int x = 1; { int x = 2; x = x + 1; { x = 5; } } x = x;")
    assert uses(fn) == [("x", 1), ("x", 1), ("x", 1), ("x", 0), ("x", 0)]


def test_initializer_sees_its_own_declarator_like_c() -> None:
    # C 6.2.1p7: the scope of x starts right after its declarator, so `x` below is the new x.
    fn = main_of("int x = 1; { int x = x; int y = x; }")
    assert uses(fn) == [("x", 1), ("x", 1)]


def test_symbol_offsets_follow_frame_layout() -> None:
    assert [Symbol("v", SymKind.LOCAL, i).offset for i in range(3)] == [-4, -8, -12]


def test_no_locals_means_no_slots() -> None:
    fn = main_of("return 1;")
    assert fn.info is not None and fn.info.n_slots == 0


@pytest.mark.parametrize(("src", "codes"), [
    ("return x;", ["E020"]),
    ("int a = b; a = c; return d;", ["E020", "E020", "E020"]),
    ("int x; int x;", ["E021"]),
    ("int x; { int x; } int y; int y;", ["E021"]),
    ("int a, a; return a + q;", ["E021", "E020"]),  # every error is reported
    ("{ int x = 1; } return x;", ["E020"]),
])
def test_errors(src: str, codes: list[str]) -> None:
    with pytest.raises(CompileError) as e:
        main_of(src)
    assert [d.code for d in e.value.diagnostics] == codes


def analyze_src(src: str) -> ast.Program:
    return analyze(parse(lex(src, "t.c")))


def calls(prog: ast.Program) -> list[ast.Call]:
    return [n for f in prog.functions for n in all_nodes(f) if isinstance(n, ast.Call)]


def test_nck_resolves_to_the_runtime_builtin() -> None:
    (call,) = calls(analyze_src("int main(void) { return nCk(5, 2); }"))
    assert call.resolved is not None
    assert (call.resolved.name, call.resolved.arity, call.resolved.label) == (
        "nCk", 2, "__rt_nCk")


def test_matching_nck_prototype_is_accepted_with_any_param_names() -> None:
    analyze_src("int nCk(int a, int b); int nCk(int n, int k); int main(void) { return 0; }")


@pytest.mark.parametrize(("src", "codes"), [
    ("int main(void) { return nCk(1); }", ["E023"]),
    ("int main(void) { return nCk(1, 2, 3) + nCk(); }", ["E023", "E023"]),
    ("int main(void) { return foo(1) + bar(); }", ["E022", "E022"]),
    ("int main(void) { int nCk = 1; return nCk(1, 2); }", ["E022"]),  # shadowed, like C
    ("int nCk(int n, int k) { return 0; } int main(void) { return 0; }", ["E024"]),
    ("int nCk(int n); int main(void) { return 0; }", ["E024"]),
    ("int nCk(int a, int b, int c); int main(void) { return 0; }", ["E024"]),
    ("int f(int x); int main(void) { return f(1); }", ["E022"]),  # never defined
    ("int main(void) { return nCk(x, 1); }", ["E020"]),  # args are still checked
])
def test_call_errors(src: str, codes: list[str]) -> None:
    with pytest.raises(CompileError) as e:
        analyze_src(src)
    assert [d.code for d in e.value.diagnostics] == codes


def test_shadowed_nck_message() -> None:
    with pytest.raises(CompileError) as e:
        analyze_src("int main(void) { int nCk = 1; return nCk(1, 2); }")
    assert e.value.diagnostics[0].message == "called object 'nCk' is not a function"


def fn(prog: ast.Program, name: str) -> ast.Function:
    return next(f for f in prog.functions if f.name == name and f.body is not None)


def test_params_take_the_first_slots() -> None:
    prog = analyze_src("int f(int a, int b) { int c = a; { int d; } return b; } "
                       "int main(void) { return f(1, 2); }")
    info = fn(prog, "f").info
    assert info is not None
    assert (info.n_params, info.n_slots, info.label) == (2, 4, "f_f")
    assert [(s.name, s.kind, s.slot) for s in info.symbols] == [
        ("a", SymKind.PARAM, 0), ("b", SymKind.PARAM, 1),
        ("c", SymKind.LOCAL, 2), ("d", SymKind.LOCAL, 3)]


def test_user_call_resolves_to_function_label() -> None:
    prog = analyze_src("int g(void); int main(void) { return g(); } int g(void) { return 1; }")
    (call,) = calls(prog)
    assert call.resolved is not None and call.resolved.label == "f_g"


def test_for_init_scope_ends_with_the_loop() -> None:
    # C99 6.8.5p5: `for (int i ...)` is its own scope, so a later `int i` is not a redeclaration.
    analyze_src("int main(void) { for (int i = 0; i < 2; i = i + 1) { int i = 5; } "
                "int i = 3; return i; }")
    with pytest.raises(CompileError) as e:
        analyze_src("int main(void) { for (int i = 0; i < 2; i = i + 1) ; return i; }")
    assert [d.code for d in e.value.diagnostics] == ["E020"]


@pytest.mark.parametrize(("src", "falls_through"), [
    ("int f(void) { return 1; }", False),
    ("int f(int x) { if (x) return 1; }", True),
    ("int f(int x) { if (x) return 1; else return 2; }", False),
    ("int f(int x) { if (x) { return 1; } else { { return 2; } } }", False),
    ("int f(int x) { while (x) return 1; }", True),
    ("int f(void) { while (1) { } }", False),       # never completes: no break in MiniC
    ("int f(void) { for (;;) ; }", False),
    ("int f(void) { for (; 1;) ; }", False),
    ("int f(int x) { for (; x;) ; }", True),
    ("int f(void) { return 1; printf(\"dead\"); }", False),
])
def test_falls_through(src: str, falls_through: bool) -> None:
    prog = analyze_src(src + " int main(void) { return f(1); }"
                       if "(int x)" in src else src + " int main(void) { return f(); }")
    info = fn(prog, "f").info
    assert info is not None and info.falls_through == falls_through
    assert [w.code for w in prog.warnings] == (["W001"] if falls_through else [])


def test_main_falling_through_is_not_a_warning() -> None:
    prog = analyze_src('int main(void) { printf("x"); }')
    assert prog.warnings == []
    assert fn(prog, "main").info is not None


@pytest.mark.parametrize(("src", "codes"), [
    ("int f(int a, int b, int c, int d, int e); int main(void) { return 0; }", ["E028"]),
    ("int f(void) { return 1; } int f(void) { return 2; } int main(void) { return f(); }",
     ["E021"]),
    ("int f(int a); int f(int a, int b) { return a; } int main(void) { return 0; }", ["E021"]),
    ("int f(int a, int a) { return a; } int main(void) { return 0; }", ["E021"]),
    ("int main(void) { return f(1); } int f(int x) { return x; }", ["E022"]),
    ("int f(int a) { return a; } int main(void) { return f(1, 2) + f(); }", ["E023", "E023"]),
    ("int main(void) { return 0; } int main(void) { return 1; }", ["E021"]),
])
def test_function_errors(src: str, codes: list[str]) -> None:
    with pytest.raises(CompileError) as e:
        analyze_src(src)
    assert [d.code for d in e.value.diagnostics] == codes
