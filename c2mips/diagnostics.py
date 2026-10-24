"""gcc-style diagnostics: `file:line:col: error[Exxx]: message`, source line, caret (README 10)."""

from __future__ import annotations

from dataclasses import dataclass

from c2mips.tokens import Pos


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    pos: Pos

    def render(self, source: str) -> str:
        lines = source.split("\n")
        text = lines[self.pos.line - 1] if self.pos.line <= len(lines) else ""
        # Keep tabs so the caret lines up under the same column in a terminal.
        pad = "".join("\t" if c == "\t" else " " for c in text[:self.pos.col - 1])
        kind = "warning" if self.code.startswith("W") else "error"
        return (f"{self.pos.file}:{self.pos.line}:{self.pos.col}: {kind}[{self.code}]: "
                f"{self.message}\n{text}\n{pad}^\n")


class CompileError(Exception):
    """One or more diagnostics; lexer/parser raise on the first, sema on all of them."""

    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        super().__init__("; ".join(d.message for d in diagnostics))
        self.diagnostics = diagnostics


def error(code: str, message: str, pos: Pos) -> CompileError:
    return CompileError([Diagnostic(code, message, pos)])
