"""The whole pipeline (Spec 5.1): lex -> parse -> sema -> fold (-O1) -> codegen -> emit."""

from __future__ import annotations

from pathlib import PurePath

from c2mips.codegen import codegen
from c2mips.diagnostics import Diagnostic
from c2mips.emitter import emit
from c2mips.fold import fold
from c2mips.lexer import lex
from c2mips.parser import parse
from c2mips.sema import analyze

TARGETS = ("spim", "fpga")  # spim: SPIM/MARS (Spec 6) · fpga: openmips / FPGA Studio (ADR-009)


def compile_program(src: str, filename: str, *, runtime: bool = True, opt: int = 0,
                    target: str = "spim") -> tuple[str, list[Diagnostic]]:
    """C source -> (.s text, warnings). Raises CompileError. `filename` is used in
    diagnostics; opt is 0 (-O0) or 1 (-O1: fold + the Spec 6.9 templates)."""
    assert target in TARGETS, target
    src = src.replace("\r\n", "\n")
    prog = analyze(parse(lex(src, filename)), target)
    if opt:
        prog = fold(prog)
    main = next(f for f in prog.functions if f.name == "main" and f.body is not None)
    asm = emit(codegen(prog, src, opt, target), PurePath(filename).name, where=main.pos,
               runtime=runtime, opt=f"-O{opt}", target=target)
    return asm, prog.warnings


def compile_source(src: str, filename: str, *, runtime: bool = True, opt: int = 0,
                   target: str = "spim") -> str:
    """C source -> .s text, ignoring warnings. Raises CompileError."""
    return compile_program(src, filename, runtime=runtime, opt=opt, target=target)[0]
