"""Recursive-descent parser, one method per rule of README 4.2. Stops at the first error.

The M4 rules (if/while/for, comparisons, && || !, %) are not parsed: they are reported
as E030 "not supported yet" so the message is not a confusing syntax error.
"""

from __future__ import annotations

from c2mips import ast
from c2mips.diagnostics import CompileError, error
from c2mips.tokens import Pos, Token, TokKind

K = TokKind

# Type names of C that MiniC does not have (Q3): reported as E030, not as syntax errors.
C_TYPES = {"char", "short", "long", "float", "double", "signed", "unsigned", "struct",
           "union", "enum", "const", "volatile", "static", "extern", "register", "auto",
           "typedef", "_Bool"}
UNSUPPORTED_OPS = {K.PERCENT, K.EQ, K.NE, K.LT, K.LE, K.GT, K.GE, K.ANDAND, K.OROR, K.NOT,
                   K.INC, K.DEC, K.PLUS_ASSIGN, K.MINUS_ASSIGN, K.STAR_ASSIGN, K.SLASH_ASSIGN,
                   K.PERCENT_ASSIGN}
UNSUPPORTED_STMTS = {K.IF: "'if' statements", K.WHILE: "'while' loops", K.FOR: "'for' loops"}


def parse(tokens: list[Token]) -> ast.Program:
    return _Parser(tokens).program()


def _end(tok: Token) -> Pos:
    return Pos(tok.pos.file, tok.pos.line, tok.pos.col + len(tok.text))


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.toks = tokens
        self.i = 0

    # -- helpers ----------------------------------------------------------------

    @property
    def tok(self) -> Token:
        return self.toks[self.i]

    def peek(self, n: int = 1) -> Token:
        return self.toks[min(self.i + n, len(self.toks) - 1)]

    def at(self, kind: TokKind) -> bool:
        # A method, so mypy does not keep a narrowed self.tok.kind across advance().
        return self.tok.kind is kind

    def advance(self) -> Token:
        tok = self.tok
        if tok.kind is not K.EOF:
            self.i += 1
        return tok

    def unexpected(self, what: str) -> CompileError:
        tok = self.tok
        if tok.kind is K.EOF:
            return error("E011", f"unexpected end of file (expected {what})", tok.pos)
        if tok.kind in UNSUPPORTED_OPS:
            return error("E030", f"operator '{tok.text}' is not supported yet", tok.pos)
        if tok.kind is K.AMP:
            return error("E030", "pointers are not supported", tok.pos)
        if tok.kind is K.LBRACKET:
            return error("E030", "arrays are not supported", tok.pos)
        return error("E010", f"expected {what} but found {tok.describe()}", tok.pos)

    def expect(self, kind: TokKind) -> Token:
        if self.tok.kind is not kind:
            raise self.unexpected("identifier" if kind is K.IDENT else f"'{kind.value}'")
        return self.advance()

    def type_int(self) -> None:
        """The only type: `int`."""
        tok = self.tok
        if tok.kind is K.IDENT and tok.text in C_TYPES:
            raise error("E030", f"type '{tok.text}' is not supported (only int)", tok.pos)
        self.expect(K.INT)

    # -- declarations -----------------------------------------------------------

    def program(self) -> ast.Program:
        pos = self.tok.pos
        functions = []
        while self.tok.kind is not K.EOF:
            functions.append(self.function())
        return ast.Program(functions, pos)

    def function(self) -> ast.Function:
        if self.tok.kind is K.VOID:
            raise error("E030", "functions must return 'int'", self.tok.pos)
        self.type_int()
        name = self.expect(K.IDENT)
        self.expect(K.LPAREN)
        params, param_pos = self.params()
        self.expect(K.RPAREN)
        if self.tok.kind is K.SEMI:
            self.advance()
            body = None
        elif self.tok.kind is K.LBRACE:
            body = self.block()
        else:
            raise self.unexpected("'{' or ';'")
        return ast.Function(str(name.value), params, body, name.pos, param_pos)

    def params(self) -> tuple[list[str], list[Pos]]:
        if self.tok.kind is K.RPAREN:
            return [], []
        if self.tok.kind is K.VOID:  # the caller expects the ")"
            self.advance()
            return [], []
        names, positions = [], []
        while True:
            self.type_int()
            name = self.expect(K.IDENT)
            names.append(str(name.value))
            positions.append(name.pos)
            if self.tok.kind is not K.COMMA:
                return names, positions
            self.advance()

    # -- statements -------------------------------------------------------------

    def block(self) -> ast.Block:
        start = self.expect(K.LBRACE)
        stmts = []
        while self.tok.kind is not K.RBRACE:
            if self.tok.kind is K.EOF:
                raise self.unexpected("'}'")
            stmts.append(self.stmt())
        return ast.Block(stmts, start.pos, _end(self.advance()))

    def stmt(self) -> ast.Stmt:
        tok = self.tok
        if tok.kind is K.INT or (tok.kind is K.IDENT and tok.text in C_TYPES):
            return self.decl()
        if tok.kind in UNSUPPORTED_STMTS:
            raise error("E030", f"{UNSUPPORTED_STMTS[tok.kind]} are not supported yet", tok.pos)
        if tok.kind is K.RETURN:
            self.advance()
            e = self.expr()
            return ast.Return(e, tok.pos, _end(self.expect(K.SEMI)))
        if tok.kind is K.IDENT and tok.text == "printf":
            return self.printf_stmt()
        if tok.kind is K.LBRACE:
            return self.block()
        if tok.kind is K.SEMI:
            self.advance()
            return ast.Empty(tok.pos, _end(tok))
        e = self.expr()
        return ast.ExprStmt(e, tok.pos, _end(self.expect(K.SEMI)))

    def decl(self) -> ast.Decl:
        start = self.tok.pos
        self.type_int()
        items: list[tuple[str, ast.Expr | None]] = []
        item_pos = []
        while True:
            if self.tok.kind is K.STAR:
                raise error("E030", "pointers are not supported", self.tok.pos)
            name = self.expect(K.IDENT)
            init = None
            if self.tok.kind is K.ASSIGN:
                self.advance()
                init = self.expr()
            items.append((str(name.value), init))
            item_pos.append(name.pos)
            if self.tok.kind is not K.COMMA:
                break
            self.advance()
        return ast.Decl(items, start, _end(self.expect(K.SEMI)), item_pos)

    def printf_stmt(self) -> ast.Printf:
        name = self.advance()
        self.expect(K.LPAREN)
        if self.tok.kind is not K.STRING:
            raise error("E025", "format of 'printf' must be a string literal", self.tok.pos)
        segments, n_conv = _parse_format(self.advance())
        args: list[ast.Expr] = []
        while self.at(K.COMMA):
            self.advance()
            args.append(self.expr())
        self.expect(K.RPAREN)
        end = _end(self.expect(K.SEMI))
        if n_conv != len(args):
            raise error("E027", f"'printf' format expects {n_conv} arguments, got {len(args)}",
                        name.pos)
        return ast.Printf(segments, args, name.pos, end)

    # -- expressions ------------------------------------------------------------

    def expr(self) -> ast.Expr:
        return self.assign()

    def assign(self) -> ast.Expr:
        if self.tok.kind is K.IDENT and self.peek().kind is K.ASSIGN:
            name = self.advance()
            self.advance()
            return ast.Assign(str(name.value), self.assign(), name.pos)
        return self.additive()  # logic_or .. relational are M4

    def additive(self) -> ast.Expr:
        left = self.term()
        while self.tok.kind in (K.PLUS, K.MINUS):
            op = self.advance()
            left = ast.Binary(op.text, left, self.term(), op.pos)
        return left

    def term(self) -> ast.Expr:
        left = self.unary()
        while self.tok.kind in (K.STAR, K.SLASH):  # "%" is M4
            op = self.advance()
            left = ast.Binary(op.text, left, self.unary(), op.pos)
        return left

    def unary(self) -> ast.Expr:
        if self.tok.kind in (K.MINUS, K.PLUS):
            op = self.advance()
            return ast.Unary(op.text, self.unary(), op.pos)
        return self.primary()

    def primary(self) -> ast.Expr:
        tok = self.tok
        if tok.kind is K.NUMBER:
            self.advance()
            assert isinstance(tok.value, int)
            return ast.IntLit(tok.value, tok.pos)
        if tok.kind is K.IDENT:
            if tok.text == "printf":
                raise error("E025", "'printf' can only be used as a statement", tok.pos)
            self.advance()
            if self.tok.kind is K.LPAREN:
                return ast.Call(tok.text, self.call_args(), tok.pos)
            return ast.Var(tok.text, tok.pos)
        if tok.kind is K.LPAREN:
            self.advance()
            e = self.expr()
            self.expect(K.RPAREN)
            return e
        if tok.kind is K.STRING:
            raise error("E030", "string literals are only supported as the printf format",
                        tok.pos)
        raise self.unexpected("expression")

    def call_args(self) -> list[ast.Expr]:
        self.expect(K.LPAREN)
        args = []
        if self.tok.kind is not K.RPAREN:
            args.append(self.expr())
            while self.tok.kind is K.COMMA:
                self.advance()
                args.append(self.expr())
        self.expect(K.RPAREN)
        return args


def _parse_format(tok: Token) -> tuple[list[str | ast.FmtD], int]:
    """Split a printf format into literal text and %d (README 4.5), from the raw token text
    so E026 can point at the exact column of the bad conversion."""
    raw = tok.text[1:-1]
    segments: list[str | ast.FmtD] = []
    text: list[str] = []
    n_conv = 0
    j = 0
    while j < len(raw):
        c = raw[j]
        if c == "\\":
            text.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}[raw[j + 1]])
            j += 2
            continue
        if c != "%":
            text.append(c)
            j += 1
            continue
        nxt = raw[j + 1] if j + 1 < len(raw) else ""
        if nxt == "%":
            text.append("%")
        elif nxt == "d":
            if text:
                segments.append("".join(text))
                text = []
            segments.append(ast.FmtD())
            n_conv += 1
        else:
            conv = "%" + (nxt if nxt not in ("", "\\") else "")
            pos = Pos(tok.pos.file, tok.pos.line, tok.pos.col + 1 + j)
            raise error("E026", f"unsupported conversion '{conv}' (only %d and %%)", pos)
        j += 2
    if text:
        segments.append("".join(text))
    return segments, n_conv
