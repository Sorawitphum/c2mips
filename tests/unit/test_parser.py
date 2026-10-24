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
])
def test_expressions(src: str, tree: str) -> None:
    assert expr(src) == tree


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
    ("int main(void) { while (1) ; }", "E030", "'while' loops are not supported yet"),
    ("int main(void) { for (;;) ; }", "E030", "'for' loops are not supported yet"),
    ("int main(void) { return 5 % 2; }", "E030", "operator '%' is not supported yet"),
    ("int main(void) { return !1; }", "E030", "operator '!' is not supported yet"),
    ("int main(void) { return 1 == 1; }", "E030", "operator '==' is not supported yet"),
    ("int main(void) { return 1 && 1; }", "E030", "operator '&&' is not supported yet"),
    ("int main(void) { x++; }", "E030", "operator '++' is not supported yet"),
    ("int main(void) { x += 1; }", "E030", "operator '+=' is not supported yet"),
    ("int main(void) { return &x; }", "E030", "pointers are not supported"),
])
def test_parse_errors(src: str, code: str, message: str) -> None:
    assert error(src) == (code, message)
