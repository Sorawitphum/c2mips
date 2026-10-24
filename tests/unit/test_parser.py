"""Parser: grammar 4.2 (non-M4 part), precedence/associativity via AST s-expressions."""

from __future__ import annotations

import pytest

from c2mips.ast import sexpr
from c2mips.diagnostics import CompileError
from c2mips.lexer import lex
from c2mips.parser import parse


def prog(src: str) -> str:
    return sexpr(parse(lex(src, "t.c")))


def expr(src: str) -> str:
    """S-expression of `src` used as the return value of main."""
    s = prog(f"int main(void) {{ return {src}; }}")
    prefix, suffix = "(program (function main () (block (return ", "))))"
    assert s.startswith(prefix) and s.endswith(suffix), s
    return s[len(prefix):-len(suffix)]


def error(src: str) -> tuple[str, str]:
    with pytest.raises(CompileError) as e:
        parse(lex(src, "t.c"))
    d = e.value.diagnostics[0]
    return d.code, d.message


@pytest.mark.parametrize(("src", "tree"), [
    ("1 + 2 * 3", "(+ 1 (* 2 3))"),                 # A1 precedence
    ("(1 + 2) * 3", "(* (+ 1 2) 3)"),               # A2 parentheses
    ("10 - 4 - 3", "(- (- 10 4) 3)"),               # A3 left-assoc
    ("100 / 10 / 5", "(/ (/ 100 10) 5)"),           # A4 left-assoc
    ("-7 / 2", "(/ (neg 7) 2)"),                    # unary binds tighter than /
    ("7 / -2", "(/ 7 (neg 2))"),
    ("- - 5", "(neg (neg 5))"),                     # A10
    ("-+5", "(neg (pos 5))"),
    ("1 - 2 + 3 * 4 / 5", "(+ (- 1 2) (/ (* 3 4) 5))"),
    ("((((7))))", "7"),
    ("a = b = 1 + x", "(= a (= b (+ 1 x)))"),       # assignment is right-assoc
    ("f(1, g(2), h())", "(call f 1 (call g 2) (call h))"),
    ("nCk(n, k) * 2", "(* (call nCk n k) 2)"),
    # M4: C precedence || < && < == != < relational < additive < * / % < unary
    ("a || b && c", "(|| a (&& b c))"),
    ("a && b || c && d", "(|| (&& a b) (&& c d))"),
    ("a == b < c", "(== a (< b c))"),
    ("a != b == c", "(== (!= a b) c)"),
    ("1 + 2 < 3 * 4", "(< (+ 1 2) (* 3 4))"),
    ("a <= b >= c > d", "(> (>= (<= a b) c) d)"),
    ("a % b * c", "(* (% a b) c)"),
    ("-a % b", "(% (neg a) b)"),
    ("!a == b", "(== (! a) b)"),
    ("!!a", "(! (! a))"),
    ("x = a || b", "(= x (|| a b))"),
])
def test_expressions(src: str, tree: str) -> None:
    assert expr(src) == tree


def body(src: str) -> str:
    s = prog(f"int main(void) {{ {src} }}")
    prefix, suffix = "(program (function main () (block ", ")))"
    assert s.startswith(prefix) and s.endswith(suffix), s
    return s[len(prefix):-len(suffix)]


@pytest.mark.parametrize(("src", "tree"), [
    ("if (a) x;", "(if a (expr x))"),
    ("if (a) x; else y;", "(if a (expr x) (expr y))"),
    ("if (a) if (b) x; else y;", "(if a (if b (expr x) (expr y)))"),  # dangling else
    ("if (a) { } else if (b) ; else { y; }",
     "(if a (block) (if b (empty) (block (expr y))))"),
    ("while (i < 3) i = i + 1;", "(while (< i 3) (expr (= i (+ i 1))))"),
    ("for (int i = 0; i < 3; i = i + 1) ;",
     "(for (decl (i 0)) (< i 3) (= i (+ i 1)) (empty))"),
    ("for (i = 0; ; ) { }", "(for (= i 0) _ _ (block))"),
    ("for (;;) ;", "(for _ _ _ (empty))"),
])
def test_control_flow(src: str, tree: str) -> None:
    assert body(src) == tree


def test_statements() -> None:
    src = """
    int main() {
        int a, b = 2;
        ;
        { a = 1; }
        printf("x=%d%%\\n", a + b);
        printf("");
        return 0;
    }
    """
    assert prog(src) == (
        '(program (function main () (block (decl (a) (b 2)) (empty) (block (expr (= a 1))) '
        '(printf ("x=" %d "%\\n") (+ a b)) (printf ()) (return 0))))'
    )


def test_functions_and_prototypes() -> None:
    src = "int nCk(int n, int k); int f(void) { return 1; } int main(void) { return 0; }"
    assert prog(src) == (
        "(program (prototype nCk (n k)) (function f () (block (return 1))) "
        "(function main () (block (return 0))))"
    )


def test_empty_program() -> None:
    assert prog("") == "(program)"


@pytest.mark.parametrize(("src", "code", "message"), [
    ("int main(void) { return 1 }", "E010", "expected ';' but found '}'"),
    ("int main(void) { return ; }", "E010", "expected expression but found ';'"),
    ("int main(void) { 1 = 2; }", "E010", "expected ';' but found '='"),
    ("int (void) {}", "E010", "expected identifier but found '('"),
    ("int main(void) { return 1;", "E011", "unexpected end of file (expected '}')"),
    ("int main(void", "E011", "unexpected end of file (expected ')')"),
    ("int main(void) { printf(x); }", "E025", "format of 'printf' must be a string literal"),
    ("int main(void) { printf; }", "E010", "expected '(' but found ';'"),
    ("int main(void) { f(printf(\"a\")); }", "E025",
     "'printf' can only be used as a statement"),
    ('int main(void) { printf("%x"); }', "E026", "unsupported conversion '%x' (only %d and %%)"),
    ('int main(void) { printf("%d"); }', "E027", "'printf' format expects 1 arguments, got 0"),
    ("long main(void) { return 0; }", "E030", "type 'long' is not supported (only int)"),
    ("int main(void) { unsigned x; }", "E030", "type 'unsigned' is not supported (only int)"),
    ("void main(void) { }", "E030", "functions must return 'int'"),
    ("int main(void) { int *p; }", "E030", "pointers are not supported"),
    ("int main(void) { int a[3]; }", "E030", "arrays are not supported"),
    ("int main(void) { x++; }", "E030", "operator '++' is not supported"),
    ("int main(void) { --x; }", "E030", "operator '--' is not supported"),
    ("int main(void) { x += 1; }", "E030", "operator '+=' is not supported"),
    ("int main(void) { while (1) break; }", "E030", "'break' is not supported"),
    ("int main(void) { do ; while (1); }", "E030", "'do' is not supported"),
    ("int main(void) { switch (1) { } }", "E030", "'switch' is not supported"),
    ("int main(void) { if (1) int x; }", "E010", "expected statement but found 'int'"),
    ("int main(void) { while (1) int x; }", "E010", "expected statement but found 'int'"),
    ("int main(void) { for (;;) int x; }", "E010", "expected statement but found 'int'"),
    ("int main(void) { if 1 ; }", "E010", "expected '(' but found '1'"),
    ("int main(void) { for (int i = 0, i < 3; ) ; }", "E010", "expected ';' but found '<'"),
    ("int main(void) { else ; }", "E010", "expected expression but found 'else'"),
    ("int main(void) { return &x; }", "E030", "pointers are not supported"),
])
def test_parse_errors(src: str, code: str, message: str) -> None:
    assert error(src) == (code, message)


def test_scanf_statement() -> None:
    # README FR-10: exactly scanf("%d", &x);
    assert body('int x; scanf("%d", &x);') == "(decl (x)) (scanf x)"


@pytest.mark.parametrize("src", [
    'scanf("%d %d", &x, &y);', 'scanf("%i", &x);', 'scanf("%d", x);', "scanf(x);",
    'scanf("%d", &x)', 'scanf("%d", &(x));',
])
def test_scanf_other_forms_are_e030(src: str) -> None:
    assert error(f"int main(void) {{ int x, y; {src} }}") == (
        "E030", "only 'scanf(\"%d\", &x);' is supported")
