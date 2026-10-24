"""CLI (Spec 2). Exit codes: 0 ok, 1 compile error, 2 bad usage / unreadable file."""

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
from c2mips.driver import compile_program
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
    p.add_argument("--run", action="store_true",
                   help="run the .s and forward its stdin, stdout and exit code")
    p.add_argument("--sim", choices=["auto", "spim", "mars"], default="auto",
                   help="simulator for --run: spim ($SPIM or PATH) or MARS ($MARS_JAR + java); "
                        "auto = spim if found, else MARS")
    p.add_argument("--no-runtime", action="store_true", help="do not append runtime.s")
    p.add_argument("--version", action="version", version=f"c2mips {__version__}")
    return p.parse_args(argv)


def _fail(message: str) -> int:
    sys.stderr.write(f"c2mips: error: {message}\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _args(sys.argv[1:] if argv is None else argv)
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
        asm, warnings = compile_program(src, name, runtime=not args.no_runtime,
                                        opt=args.opt)
    except CompileError as e:
        for d in e.diagnostics:
            sys.stderr.write(d.render(src))
        return 1
    for w in warnings:
        sys.stderr.write(w.render(src))

    if args.emit == "asm":
        sys.stdout.write(asm)
        return 0
    out = args.output or args.input.with_suffix(".s")
    out.write_bytes(asm.encode("ascii"))
    return _run(out, args.sim) if args.run else 0


def _simulator(choice: str) -> tuple[str, str] | str:
    """("spim", path) or ("mars", jar), or an error message."""
    spim = os.environ.get("SPIM") or shutil.which("spim")
    jar = os.environ.get("MARS_JAR")
    java = shutil.which("java")
    if choice in ("auto", "spim") and spim:
        return "spim", spim
    if choice in ("auto", "mars") and jar and java:
        return "mars", jar
    if choice == "spim":
        return "spim not found (install it, or set SPIM to its path)"
    if choice == "mars":
        return "MARS needs java on PATH and MARS_JAR set to Mars4_5.jar"
    return ("no simulator found: install spim (or set SPIM), or set MARS_JAR to Mars4_5.jar "
            "and install java")


def _run(asm: Path, choice: str) -> int:
    """Run asm, forwarding stdin (for scanf) and the exit code.

    spim: `spim -stext 4194304 -file asm` without its 5-line banner (S1, S10).
    MARS: `java -jar Mars4_5.jar nc ae2 asm` without the extra last line (S20), with a
    latin-1 stdout so .byte strings come out byte for byte (S17).
    """
    sim = _simulator(choice)
    if isinstance(sim, str):
        return _fail(sim)
    kind, path = sim
    if kind == "spim":
        cmd = [path, "-stext", "4194304", "-file", str(asm)]
    else:
        cmd = ["java", "-Dstdout.encoding=ISO-8859-1", "-jar", path, "nc", "ae2", str(asm)]
    p = subprocess.run(cmd, capture_output=True)  # stdin is inherited: pipe input for scanf
    raw = p.stdout
    if kind == "spim":
        _, sep, rest = raw.partition(b"Loaded:")
        raw = rest.partition(b"\n")[2] if sep else raw
    elif raw.endswith(b"\r\n"):
        raw = raw[:-2]
    elif raw.endswith(b"\n"):
        raw = raw[:-1]
    sys.stdout.write(raw.decode("utf-8", errors="replace"))
    sys.stderr.write(p.stderr.decode("utf-8", errors="replace"))
    # exit2(-1) is 255 on Linux but 4294967295 from java on Windows: report 8 bits everywhere
    return p.returncode & 0xFF


def cli() -> None:
    # A Windows console may not be able to encode Thai source lines in diagnostics.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="backslashreplace")
    sys.exit(main())


if __name__ == "__main__":
    cli()
