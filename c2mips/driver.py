"""The whole pipeline (README 5.1): lex -> parse -> sema -> fold (-O1) -> codegen -> emit."""

from __future__ import annotations

from pathlib import PurePath

from c2mips.codegen import codegen
from c2mips.diagnostics import Diagnostic
from c2mips.emitter import emit
from c2mips.fold import fold
from c2mips.lexer import lex
from c2mips.parser import parse
from c2mips.sema import analyze


def compile_program(src: str, filename: str, *, runtime: bool = True,
                    opt: int = 0) -> tuple[str, list[Diagnostic]]:
    """C source -> (.s text, warnings). Raises CompileError. `filename` is used in
    diagnostics; opt is 0 (-O0) or 1 (-O1: fold + the README 6.9 templates)."""
    src = src.replace("\r\n", "\n")
    prog = analyze(parse(lex(src, filename)))
    if opt:
        prog = fold(prog)
    main = next(f for f in prog.functions if f.name == "main" and f.body is not None)
    asm = emit(codegen(prog, src, opt), PurePath(filename).name, where=main.pos,
               runtime=runtime, opt=f"-O{opt}")
    return asm, prog.warnings


def compile_source(src: str, filename: str, *, runtime: bool = True, opt: int = 0) -> str:
    """C source -> .s text, ignoring warnings. Raises CompileError."""
    return compile_program(src, filename, runtime=runtime, opt=opt)[0]
