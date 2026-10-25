"""Lexer: text -> tokens (Spec 4.1). Stops at the first error."""

from __future__ import annotations

import re

from c2mips.diagnostics import error
from c2mips.tokens import KEYWORDS, PUNCTUATORS, Pos, Token, TokKind

INT_MAX = 2**31 - 1
ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}

_INCLUDE_OK = re.compile(r'#\s*include\s*(<stdio\.h>|"c2mips\.h")\s*(//.*)?$')
_INCLUDE = re.compile(r"#\s*include\s*(.*?)\s*$")
_DIRECTIVE = re.compile(r"#\s*(\w*)")
_WORD = re.compile(r"[A-Za-z0-9_]*")


def lex(src: str, file: str) -> list[Token]:
    return _Lexer(src.replace("\r\n", "\n"), file).run()


def _char_name(c: str) -> str:
    return f"'{c}'" if " " < c < "\x7f" else f"U+{ord(c):04X}"


class _Lexer:
    def __init__(self, src: str, file: str) -> None:
        self.src = src
        self.file = file
        self.i = 0
        self.line = 1
        self.line_start = 0
        self.toks: list[Token] = []

    def pos(self, i: int | None = None) -> Pos:
        i = self.i if i is None else i
        return Pos(self.file, self.line, i - self.line_start + 1)

    def newline(self, i: int) -> None:
        """Record that src[i] is a newline."""
        self.line += 1
        self.line_start = i + 1

    def run(self) -> list[Token]:
        src = self.src
        while self.i < len(src):
            c = src[self.i]
            if c == "\n":
                self.newline(self.i)
                self.i += 1
            elif c in " \t\v\f\r":
                self.i += 1
            elif src.startswith("//", self.i):
                end = src.find("\n", self.i)
                self.i = len(src) if end < 0 else end
            elif src.startswith("/*", self.i):
                self.block_comment()
            elif c == "#":
                self.directive()
            elif c.isascii() and c.isdigit():
                self.number()
            elif c.isascii() and (c.isalpha() or c == "_"):
                word = _WORD.match(src, self.i)
                assert word is not None
                text = word.group()
                kind = KEYWORDS.get(text, TokKind.IDENT)
                self.add(kind, text, text if kind is TokKind.IDENT else None)
            elif c == '"':
                self.string()
            else:
                for kind in PUNCTUATORS:
                    if src.startswith(kind.value, self.i):
                        self.add(kind, kind.value, None)
                        break
                else:
                    raise error("E001", f"unknown character {_char_name(c)}", self.pos())
        self.toks.append(Token(TokKind.EOF, "", None, self.pos()))
        return self.toks

    def add(self, kind: TokKind, text: str, value: int | str | None) -> None:
        self.toks.append(Token(kind, text, value, self.pos()))
        self.i += len(text)

    def block_comment(self) -> None:
        start = self.pos()
        end = self.src.find("*/", self.i + 2)
        if end < 0:
            raise error("E002", "unterminated comment", start)
        for j in range(self.i, end):
            if self.src[j] == "\n":
                self.newline(j)
        self.i = end + 2

    def directive(self) -> None:
        pos = self.pos()
        if self.src[self.line_start:self.i].strip():
            raise error("E031", "'#' must start a line", pos)
        end = self.src.find("\n", self.i)
        end = len(self.src) if end < 0 else end
        text = self.src[self.i:end]
        if _INCLUDE_OK.match(text):
            self.i = end
            return
        if inc := _INCLUDE.match(text):
            raise error("E031", f'unsupported #include {inc.group(1)} '
                                f'(only <stdio.h> and "c2mips.h")', pos)
        word = _DIRECTIVE.match(text)
        assert word is not None
        raise error("E031", f"unsupported preprocessor directive '#{word.group(1)}'", pos)

    def number(self) -> None:
        word = _WORD.match(self.src, self.i)
        assert word is not None
        text = word.group()
        pos = self.pos()
        if not text.isdigit():
            raise error("E001", f"invalid integer literal '{text}' (decimal only)", pos)
        if len(text) > 1 and text[0] == "0":
            raise error("E001", f"octal literal '{text}' is not supported (decimal only)", pos)
        value = int(text)
        if value > INT_MAX:
            after_minus = bool(self.toks) and self.toks[-1].kind is TokKind.MINUS
            hint = ("; write -2147483647 - 1" if after_minus and value == INT_MAX + 1
                    else f" (max {INT_MAX})")
            raise error("E003", f"integer literal {text} out of range{hint}", pos)
        self.add(TokKind.NUMBER, text, value)

    def string(self) -> None:
        src, start = self.src, self.i
        j = start + 1
        value = []
        while True:
            if j >= len(src) or src[j] == "\n":
                raise error("E002", "unterminated string literal", self.pos(start))
            c = src[j]
            if c == '"':
                break
            if c == "\\":
                nxt = src[j + 1] if j + 1 < len(src) else "\n"
                if nxt == "\n":
                    raise error("E002", "unterminated string literal", self.pos(start))
                if nxt not in ESCAPES:
                    raise error("E001", f"unknown escape sequence '\\{nxt}' "
                                        "(supported: \\n \\t \\\\ \\\")", self.pos(j))
                value.append(ESCAPES[nxt])
                j += 2
            else:
                value.append(c)
                j += 1
        self.add(TokKind.STRING, src[start:j + 1], "".join(value))
