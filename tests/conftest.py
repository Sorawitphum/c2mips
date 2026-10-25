"""Shared test harness (Spec §9.5)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _wsl_has_spim() -> bool:
    """wsl.exe exists on every Windows 11, so ask whether its distro really has spim."""
    distro = os.environ.get("C2MIPS_WSL_DISTRO")
    cmd = ["wsl", *(["-d", distro] if distro else []), "-e", "sh", "-c", "command -v spim"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _find_spim() -> str | None:
    """$SPIM, then spim on PATH, then (Windows) the WSL shim in tools/ if WSL has spim."""
    if env := os.environ.get("SPIM"):
        return env
    if found := shutil.which("spim"):
        return found
    if os.name == "nt" and shutil.which("wsl") and _wsl_has_spim():
        return str(REPO / "tools" / "spim.cmd")
    return None


SPIM = _find_spim()
GCC = os.environ.get("GCC") or shutil.which("gcc")
# MARS 4.5 jar (Spec S14-S20); not downloaded by the test suite, so opt-in via $MARS_JAR.
MARS_JAR = os.environ.get("MARS_JAR") if shutil.which("java") else None


def _pick_simulator() -> str | None:
    """spim when there is one, else MARS (e.g. Windows without WSL); C2MIPS_SIMULATOR=spim|mars
    forces one. Every `sim` test runs on it, so the whole suite also works with MARS only."""
    want = os.environ.get("C2MIPS_SIMULATOR")
    available = {"spim": SPIM, "mars": MARS_JAR}
    if want:
        return want if available.get(want) else None
    return "spim" if SPIM else "mars" if MARS_JAR else None


SIMULATOR = _pick_simulator()


def sim_cli(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Make `c2mips --run` use the same simulator as the tests; returns the --sim argument."""
    assert SIMULATOR is not None
    if SIMULATOR == "spim":
        assert SPIM is not None
        monkeypatch.setenv("SPIM", SPIM)
    else:
        assert MARS_JAR is not None
        monkeypatch.setenv("MARS_JAR", MARS_JAR)
    return ["--sim", SIMULATOR]


def stdin_for(src: Path) -> str:
    """programs/x.c may come with x.stdin: one integer per line for scanf (Spec S21)."""
    p = src.with_suffix(".stdin")
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run_sim(asm: Path, timeout: float = 10, stdin: str = "") -> tuple[str, int]:
    """Run asm on the selected simulator (SIMULATOR); return (stdout, exit code)."""
    if SIMULATOR is None:
        pytest.skip("no simulator: install spim, or set MARS_JAR (and have java)")
    if SIMULATOR == "mars":
        return run_mars(asm, timeout=max(timeout, 60), stdin=stdin)  # JVM start-up
    return run_spim(asm, timeout, stdin)


def run_spim(asm: Path, timeout: float = 10, stdin: str = "") -> tuple[str, int]:
    """Run asm on SPIM; return (stdout without the banner, exit code)."""
    if SPIM is None:
        pytest.skip("spim not found")
    # The WSL shim (tools/spim.cmd) kills spim itself shortly after our own timeout fires.
    env = {**os.environ, "C2MIPS_SPIM_TIMEOUT": str(timeout + 2)}
    p = subprocess.run([SPIM, "-stext", "4194304", "-file", str(asm)],
                       capture_output=True, text=True, timeout=timeout, env=env,
                       input=stdin,  # then EOF: a bad file cannot leave spim's REPL waiting
                       encoding="utf-8", errors="replace")  # .byte strings print UTF-8
    lines = p.stdout.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Loaded:")) + 1
    except StopIteration:
        raise RuntimeError(f"no SPIM banner\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}") from None
    return "\n".join(lines[start:]), p.returncode


def run_gcc(src: Path, workdir: Path, timeout: float = 10, stdin: str = "") -> tuple[str, int]:
    """Oracle (Spec 3.2 NFR-1): gcc -fwrapv + ref/nck_ref.c; (stdout, exit code & 0xFF)."""
    if GCC is None:
        pytest.skip("gcc not found")
    exe = workdir / f"{src.stem}.exe"
    build = subprocess.run([GCC, "-std=c99", "-fwrapv", "-O0", f"-I{REPO / 'include'}",
                            str(src), str(REPO / "ref" / "nck_ref.c"), "-o", str(exe)],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    p = subprocess.run([str(exe)], capture_output=True, timeout=timeout,
                       input=stdin.encode())
    out = p.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")  # Windows CRT
    return out, p.returncode & 0xFF  # Windows reports the full 32-bit status


def run_mars(asm: Path, timeout: float = 60, stdin: str = "") -> tuple[str, int]:
    """Run asm on MARS 4.5 (Spec S14-S20): `nc` = no banner, `ae2` = exit 2 on an
    assemble error (MARS exits 0 otherwise), latin-1 stdout so .byte output stays exact."""
    if MARS_JAR is None:
        pytest.skip("set MARS_JAR to a Mars4_5.jar (and have java) to run MARS tests")
    p = subprocess.run(["java", "-Dstdout.encoding=ISO-8859-1", "-jar", MARS_JAR, "nc", "ae2",
                        str(asm)], capture_output=True, timeout=timeout, input=stdin.encode())
    out = p.stdout
    out = out[:-2] if out.endswith(b"\r\n") else out[:-1] if out.endswith(b"\n") else out
    # MARS adds one line (S20); java on Windows reports exit2(-1) as 4294967295, Linux as 255
    return out.decode("utf-8", errors="replace"), p.returncode & 0xFF


def read_expected(path: Path) -> tuple[str, int]:
    """programs/*.expected: first line `exit: <code>`, the rest is the exact stdout."""
    head, _, out = path.read_text(encoding="utf-8").partition("\n")
    assert head.startswith("exit: "), path
    return out, int(head.removeprefix("exit: "))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--random-count", type=int, default=20,
                     help="random programs per run (Spec 9.4; CI 500, nightly 10000)")
    parser.addoption("--random-seed", type=int, default=0,
                     help="first seed; seeds are random-seed .. random-seed + count - 1")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for tool, found in (("sim", SIMULATOR), ("gcc", GCC), ("mars", MARS_JAR)):
        if found is None:
            skip = pytest.mark.skip(reason=f"{tool} not found")
            for item in items:
                if tool in item.keywords:
                    item.add_marker(skip)
