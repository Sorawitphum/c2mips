"""Constant folding (Spec 6.9, 9.2): 10k random expression trees, oracle cvalue.py.

The contract: folding never changes what the program does, so `x/0` and an overflowing
nCk stay in the code and still panic at runtime, exactly like -O0."""

from __future__ import annotations

import pytest
from exprgen import OPS, PANIC, P, evaluate
from hypothesis import given, settings
from hypothesis import strategies as st

from c2mips import ast, cvalue
from c2mips.ast import sexpr
from c2mips.fold import fold, fold_expr
from c2mips.lexer import lex
from c2mips.parser import parse
from c2mips.sema import analyze
from c2mips.tokens import Pos

VARS = ["x", "y"]
leaves = st.one_of(
    st.builds(lambda v: ast.IntLit(v, P),
              st.one_of(st.sampled_from([0, 1, -1, 2, cvalue.INT_MAX, cvalue.INT_MIN]),
                        st.integers(cvalue.INT_MIN, cvalue.INT_MAX))),
    st.builds(lambda n: ast.Var(n, P), st.sampled_from(VARS)),
)


def _extend(children: st.SearchStrategy[ast.Expr]) -> st.SearchStrategy[ast.Expr]:
    small = st.builds(lambda v: ast.IntLit(v, P), st.integers(-2, 40))
    return st.one_of(
        st.builds(lambda op, e: ast.Unary(op, e, P), st.sampled_from("-+!"), children),
        st.builds(lambda op, a, b: ast.Binary(op, a, b, P), st.sampled_from(OPS),
                  children, children),
        st.builds(lambda a, b: ast.Call("nCk", [a, b], P), st.one_of(small, children),
                  st.one_of(small, children)),
    )


exprs = st.recursive(leaves, _extend, max_leaves=12)
envs = st.fixed_dictionaries({n: st.integers(cvalue.INT_MIN, cvalue.INT_MAX) for n in VARS})


@settings(max_examples=10_000, deadline=None)
@given(exprs, envs)
def test_fold_preserves_meaning(e: ast.Expr, env: dict[str, int]) -> None:
    folded = fold_expr(e)
    assert evaluate(folded, env) == evaluate(e, env)
    if isinstance(folded, ast.IntLit):  # folded away completely: it cannot have panicked
        assert evaluate(e, env) != PANIC


def no_vars(e: ast.Expr) -> bool:
    match e:
        case ast.Var():
            return False
        case ast.Unary():
            return no_vars(e.operand)
        case ast.Binary():
            return no_vars(e.left) and no_vars(e.right)
        case ast.Call():
            return all(map(no_vars, e.args))
    return True


@settings(max_examples=2_000, deadline=None)
@given(exprs.filter(no_vars))
def test_constant_expressions_fold_completely_unless_they_panic(e: ast.Expr) -> None:
    folded = fold_expr(e)
    assert isinstance(folded, ast.IntLit) == (evaluate(e, {}) != PANIC)


def folded(src: str) -> str:
    """S-expression of main's body after sema + fold."""
    prog = fold(analyze(parse(lex(f"int main(void) {{ int x = 1; {src} }}", "t.c"))))
    s = sexpr(prog)
    prefix = "(program (function main () (block (decl (x 1)) "
    assert s.startswith(prefix), s
    return s[len(prefix):-len(")))")]


@pytest.mark.parametrize(("src", "tree"), [
    ("return (10 + 3) * 2 - 7 / 2;", "(return 23)"),
    ("return 2147483647 + 1;", "(return -2147483648)"),
    ("return (-2147483647 - 1) / -1;", "(return -2147483648)"),
    ("return -7 / 2 + -7 % 3;", "(return -4)"),
    ("return 1 / 0;", "(return (/ 1 0))"),                        # still panics at runtime
    ("return 5 % (3 - 3);", "(return (% 5 0))"),                  # operands still folded
    ("return nCk(10, 3) + nCk(5, 7);", "(return 120)"),
    ("return nCk(34, 16);", "(return (call nCk 34 16))"),        # overflow stays a call
    ("return 0 && 1 / 0;", "(return 0)"),                        # right side never runs
    ("return 1 || nCk(34, 16);", "(return 1)"),
    ("return 1 && x;", "(return (&& 1 x))"),                     # x still decides
    ("return x && 0;", "(return (&& x 0))"),                     # x is still evaluated
    ("return x + 2 * 3;", "(return (+ x 6))"),
    ("return x * 0;", "(return (* x 0))"),                       # no algebra, only constants
    ("return !(3 < 2) == (4 >= 4);", "(return 1)"),
    ("x = 2 + 2;", "(expr (= x 4))"),
    ("int y = 6 / 3, z;", "(decl (y 2) (z))"),
    ('printf("%d\\n", 6 * 7);', '(printf (%d "\\n") 42)'),
    ("if (1 < 2) x = 1; else x = 2;", "(if 1 (expr (= x 1)) (expr (= x 2)))"),
    ("while (0 * 5) x = x;", "(while 0 (expr (= x x)))"),
    ("for (x = 1 + 1; x < 2 + 3; x = x + (1 * 1)) ;",
     "(for (= x 2) (< x 5) (= x (+ x 1)) (empty))"),
])
def test_fold_cases(src: str, tree: str) -> None:
    assert folded(src) == tree


def test_folded_literal_keeps_the_position_of_the_expression() -> None:
    e = ast.Binary("+", ast.IntLit(1, Pos("t.c", 3, 9)), ast.IntLit(2, Pos("t.c", 3, 13)),
                   Pos("t.c", 3, 11))
    assert fold_expr(e) == ast.IntLit(3, Pos("t.c", 3, 11))


def test_fold_does_not_mutate_its_input() -> None:
    prog = analyze(parse(lex("int main(void) { return 1 + 2; }", "t.c")))
    before = sexpr(prog)
    fold(prog)
    assert sexpr(prog) == before
