"""Lexer: tokens, line:col, literal range, comments, #include (README 4.1, 9.2)."""

from __future__ import annotations

import pytest

from c2mips.diagnostics import CompileError
from c2mips.lexer import lex
from c2mips.tokens import TokKind as K


def kinds(src: str) -> list[K]:
    return [t.kind for t in lex(src, "t.c")]


def first_error(src: str) -> tuple[str, int, int, str]:
    with pytest.raises(CompileError) as e:
        lex(src, "t.c")
    d = e.value.diagnostics[0]
    return d.code, d.pos.line, d.pos.col, d.message


def test_tokens_kind_text_value() -> None:
    toks = lex("int main(void) { return -12 + x_1; }", "t.c")
    assert [(t.kind, t.text, t.value) for t in toks] == [
        (K.INT, "int", None), (K.IDENT, "main", "main"), (K.LPAREN, "(", None),
        (K.VOID, "void", None), (K.RPAREN, ")", None), (K.LBRACE, "{", None),
        (K.RETURN, "return", None), (K.MINUS, "-", None), (K.NUMBER, "12", 12),
        (K.PLUS, "+", None), (K.IDENT, "x_1", "x_1"), (K.SEMI, ";", None),
        (K.RBRACE, "}", None), (K.EOF, "", None),
    ]


def test_positions_are_1_based_line_col() -> None:
    toks = lex("int\n  x = /* c\n */ 7; // tail\n\treturn", "f.c")
    assert [(t.text, t.pos.line, t.pos.col) for t in toks] == [
        ("int", 1, 1), ("x", 2, 3), ("=", 2, 5), ("7", 3, 5), (";", 3, 6),
        ("return", 4, 2), ("", 4, 8),
    ]
    assert toks[0].pos.file == "f.c"


def test_crlf_is_one_newline() -> None:
    toks = lex("int\r\n  x", "t.c")
    assert (toks[1].pos.line, toks[1].pos.col) == (2, 3)


def test_includes_are_skipped() -> None:
    src = '#include <stdio.h>\n  #  include   "c2mips.h"\nint'
    toks = lex(src, "t.c")
    assert [(t.kind, t.pos.line) for t in toks] == [(K.INT, 3), (K.EOF, 3)]


def test_every_operator_and_keyword() -> None:
    src = ("int void return if else while for ( ) { } ; , + - * / % = == != < <= > >= "
           "&& || ! & [ ] ++ -- += -= *= /= %=")
    assert kinds(src)[:-1] == [
        K.INT, K.VOID, K.RETURN, K.IF, K.ELSE, K.WHILE, K.FOR, K.LPAREN, K.RPAREN,
        K.LBRACE, K.RBRACE, K.SEMI, K.COMMA, K.PLUS, K.MINUS, K.STAR, K.SLASH, K.PERCENT,
        K.ASSIGN, K.EQ, K.NE, K.LT, K.LE, K.GT, K.GE, K.ANDAND, K.OROR, K.NOT, K.AMP,
        K.LBRACKET, K.RBRACKET, K.INC, K.DEC, K.PLUS_ASSIGN, K.MINUS_ASSIGN,
        K.STAR_ASSIGN, K.SLASH_ASSIGN, K.PERCENT_ASSIGN,
    ]


def test_minus_minus_is_one_token_like_c() -> None:
    # `- - 5` is fine (A10) but `--5` is a decrement in C, so it must not become two minuses.
    assert kinds("- - 5")[:-1] == [K.MINUS, K.MINUS, K.NUMBER]
    assert kinds("--5")[:-1] == [K.DEC, K.NUMBER]


def test_string_escapes_and_utf8() -> None:
    (tok, _eof) = lex('"a\\n\\t\\\\\\"ส"', "t.c")
    assert tok.kind is K.STRING
    assert tok.value == 'a\n\t\\"ส'
    assert tok.text == '"a\\n\\t\\\\\\"ส"'


def test_non_ascii_in_comments_is_fine() -> None:
    assert kinds("// ส\n/* ส */ int") == [K.INT, K.EOF]


@pytest.mark.parametrize(("src", "value"), [("0", 0), ("7", 7), ("2147483647", 2147483647)])
def test_int_literal_range_ok(src: str, value: int) -> None:
    assert lex(src, "t.c")[0].value == value


def test_int_literal_out_of_range() -> None:
    assert first_error("x 2147483648") == (
        "E003", 1, 3, "integer literal 2147483648 out of range (max 2147483647)")
    assert first_error("- 2147483648") == (
        "E003", 1, 3, "integer literal 2147483648 out of range; write -2147483647 - 1")


@pytest.mark.parametrize(("src", "code", "col"), [
    ("$", "E001", 1), ("a ` b", "E001", 3), ("๑", "E001", 1), ("09", "E001", 1),
    ("1abc", "E001", 1), ('"\\x"', "E001", 2), ("/* x", "E002", 1), ('"abc', "E002", 1),
    ('"ab\ncd"', "E002", 1), ("#define X", "E031", 1), ("#include <math.h>", "E031", 1),
    ("#pragma once", "E031", 1), ("int x; #include <stdio.h>", "E031", 8),
])
def test_lexer_errors(src: str, code: str, col: int) -> None:
    got_code, line, got_col, _msg = first_error(src)
    assert (got_code, line, got_col) == (code, 1, col)
