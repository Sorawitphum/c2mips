"""Shared test harness (README §9.5)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _find_spim() -> str | None:
    """$SPIM, then spim on PATH, then (Windows) the WSL shim in tools/."""
    if env := os.environ.get("SPIM"):
        return env
    if found := shutil.which("spim"):
        return found
    if os.name == "nt" and shutil.which("wsl"):
        return str(REPO / "tools" / "spim.cmd")
    return None


SPIM = _find_spim()
GCC = os.environ.get("GCC") or shutil.which("gcc")


def run_spim(asm: Path, timeout: float = 10) -> tuple[str, int]:
    """Run asm on SPIM; return (stdout without the banner, exit code)."""
    if SPIM is None:
        pytest.skip("spim not found")
    # The WSL shim (tools/spim.cmd) kills spim itself shortly after our own timeout fires.
    env = {**os.environ, "C2MIPS_SPIM_TIMEOUT": str(timeout + 2)}
    p = subprocess.run([SPIM, "-stext", "4194304", "-file", str(asm)],
                       capture_output=True, text=True, timeout=timeout, env=env,
                       stdin=subprocess.DEVNULL,  # bad file -> spim's REPL must not wait
                       encoding="utf-8", errors="replace")  # .byte strings print UTF-8
    lines = p.stdout.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Loaded:")) + 1
    except StopIteration:
        raise RuntimeError(f"no SPIM banner\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}") from None
    return "\n".join(lines[start:]), p.returncode


def run_gcc(src: Path, workdir: Path, timeout: float = 10) -> tuple[str, int]:
    """Oracle (README 3.2 NFR-1): gcc -fwrapv + ref/nck_ref.c; (stdout, exit code & 0xFF)."""
    if GCC is None:
        pytest.skip("gcc not found")
    exe = workdir / f"{src.stem}.exe"
    build = subprocess.run([GCC, "-std=c99", "-fwrapv", "-O0", f"-I{REPO / 'include'}",
                            str(src), str(REPO / "ref" / "nck_ref.c"), "-o", str(exe)],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    p = subprocess.run([str(exe)], capture_output=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    out = p.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")  # Windows CRT
    return out, p.returncode & 0xFF  # Windows reports the full 32-bit status


def read_expected(path: Path) -> tuple[str, int]:
    """programs/*.expected: first line `exit: <code>`, the rest is the exact stdout."""
    head, _, out = path.read_text(encoding="utf-8").partition("\n")
    assert head.startswith("exit: "), path
    return out, int(head.removeprefix("exit: "))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--random-count", type=int, default=50,
                     help="number of random programs per run (README §9.4)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for tool, found in (("spim", SPIM), ("gcc", GCC)):
        if found is None:
            skip = pytest.mark.skip(reason=f"{tool} not found")
            for item in items:
                if tool in item.keywords:
                    item.add_marker(skip)
