"""The whole pipeline (README 5.1): lex -> parse -> sema -> codegen -> emit."""

from __future__ import annotations

from pathlib import PurePath

from c2mips.codegen import codegen
from c2mips.diagnostics import Diagnostic
from c2mips.emitter import emit
from c2mips.lexer import lex
from c2mips.parser import parse
from c2mips.sema import analyze


def compile_program(src: str, filename: str, *,
                    runtime: bool = True) -> tuple[str, list[Diagnostic]]:
    """C source -> (.s text, warnings). Raises CompileError. `filename` is used in
    diagnostics."""
    src = src.replace("\r\n", "\n")
    prog = analyze(parse(lex(src, filename)))
    main = next(f for f in prog.functions if f.name == "main" and f.body is not None)
    asm = emit(codegen(prog, src), PurePath(filename).name, where=main.pos, runtime=runtime)
    return asm, prog.warnings


def compile_source(src: str, filename: str, *, runtime: bool = True) -> str:
    """C source -> .s text, ignoring warnings. Raises CompileError."""
    return compile_program(src, filename, runtime=runtime)[0]
