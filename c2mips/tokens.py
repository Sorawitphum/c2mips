"""Tokens (README 4.1, 5.3)."""

from __future__ import annotations

import enum
from dataclasses import dataclass


@dataclass(frozen=True)
class Pos:
    file: str
    line: int
    col: int


class TokKind(enum.Enum):
    NUMBER = "number"
    IDENT = "identifier"
    STRING = "string literal"
    EOF = "end of file"
    # keywords
    INT = "int"
    VOID = "void"
    RETURN = "return"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    FOR = "for"
    # punctuators
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    SEMI = ";"
    COMMA = ","
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    ASSIGN = "="
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    ANDAND = "&&"
    OROR = "||"
    NOT = "!"
    # lexed only so the parser can say "not supported" instead of "unknown character"
    AMP = "&"
    LBRACKET = "["
    RBRACKET = "]"
    INC = "++"
    DEC = "--"
    PLUS_ASSIGN = "+="
    MINUS_ASSIGN = "-="
    STAR_ASSIGN = "*="
    SLASH_ASSIGN = "/="
    PERCENT_ASSIGN = "%="


KEYWORDS = {k.value: k for k in (TokKind.INT, TokKind.VOID, TokKind.RETURN, TokKind.IF,
                                 TokKind.ELSE, TokKind.WHILE, TokKind.FOR)}

# Longest first, so maximal munch picks "<=" over "<" and "--" over "-".
PUNCTUATORS = sorted(
    (k for k in TokKind
     if k.value and not k.value.isalpha() and k not in (TokKind.NUMBER, TokKind.IDENT,
                                                        TokKind.STRING, TokKind.EOF)),
    key=lambda k: -len(k.value),
)


@dataclass(frozen=True)
class Token:
    kind: TokKind
    text: str
    value: int | str | None
    pos: Pos

    def describe(self) -> str:
        """How diagnostics name this token: 'found ...'."""
        if self.kind is TokKind.EOF:
            return "end of file"
        return f"'{self.text}'"
