"""CLI (README 2). Exit codes: 0 ok, 1 compile error, 2 bad usage / unreadable file."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

from c2mips import __version__
from c2mips.ast import sexpr
from c2mips.diagnostics import CompileError
from c2mips.driver import compile_source
from c2mips.lexer import lex
from c2mips.parser import parse


def _args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="c2mips", description="MiniC -> MIPS32 for SPIM/MARS")
    p.add_argument("input", type=Path)
    p.add_argument("-o", dest="output", type=Path, help="output .s (default: input with .s)")
    p.add_argument("--emit", choices=["tokens", "ast", "asm"],
                   help="print one stage to stdout instead of writing a file")
    opt = p.add_mutually_exclusive_group()
    opt.add_argument("-O0", dest="opt", action="store_const", const=0, default=0)
    opt.add_argument("-O1", dest="opt", action="store_const", const=1)
    p.add_argument("--run", action="store_true", help="run on spim and forward its exit code")
    p.add_argument("--no-runtime", action="store_true", help="do not append runtime.s")
    p.add_argument("--version", action="version", version=f"c2mips {__version__}")
    return p.parse_args(argv)


def _fail(message: str) -> int:
    sys.stderr.write(f"c2mips: error: {message}\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _args(sys.argv[1:] if argv is None else argv)
    if args.opt == 1:
        return _fail("-O1 is not implemented yet")
    name = str(args.input)
    try:
        src = args.input.read_bytes().decode("utf-8").replace("\r\n", "\n")
    except OSError as e:
        return _fail(f"cannot read '{name}': {e.strerror}")
    except UnicodeDecodeError:
        return _fail(f"'{name}' is not valid UTF-8")

    try:
        if args.emit == "tokens":
            for t in lex(src, name):
                sys.stdout.write(f"{t.pos.line}:{t.pos.col}\t{t.kind.name}\t{t.text}\n")
            return 0
        if args.emit == "ast":
            sys.stdout.write(sexpr(parse(lex(src, name))) + "\n")
            return 0
        asm = compile_source(src, name, runtime=not args.no_runtime)
    except CompileError as e:
        for d in e.diagnostics:
            sys.stderr.write(d.render(src))
        return 1

    if args.emit == "asm":
        sys.stdout.write(asm)
        return 0
    out = args.output or args.input.with_suffix(".s")
    out.write_bytes(asm.encode("ascii"))
    return _run(out) if args.run else 0


def _run(asm: Path) -> int:
    """`spim -stext 4194304 -file asm`, without SPIM's 5-line banner (S1, S10)."""
    spim = os.environ.get("SPIM") or shutil.which("spim")
    if spim is None:
        return _fail("spim not found (install it or set SPIM)")
    p = subprocess.run([spim, "-stext", "4194304", "-file", str(asm)], capture_output=True,
                       stdin=subprocess.DEVNULL)
    out = p.stdout.decode("utf-8", errors="replace")
    head, sep, rest = out.partition("Loaded:")
    if sep:
        out = rest.partition("\n")[2]
    sys.stdout.write(out)
    sys.stderr.write(p.stderr.decode("utf-8", errors="replace"))
    return p.returncode


def cli() -> None:
    # A Windows console may not be able to encode Thai source lines in diagnostics.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="backslashreplace")
    sys.exit(main())


if __name__ == "__main__":
    cli()
