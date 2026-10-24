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


def run_spim(asm: Path, timeout: float = 10) -> tuple[str, int]:
    """Run asm on SPIM; return (stdout without the banner, exit code)."""
    if SPIM is None:
        pytest.skip("spim not found")
    # The WSL shim (tools/spim.cmd) kills spim itself shortly after our own timeout fires.
    env = {**os.environ, "C2MIPS_SPIM_TIMEOUT": str(timeout + 2)}
    p = subprocess.run([SPIM, "-stext", "4194304", "-file", str(asm)],
                       capture_output=True, text=True, timeout=timeout, env=env)
    lines = p.stdout.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Loaded:")) + 1
    except StopIteration:
        raise RuntimeError(f"no SPIM banner\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}") from None
    return "\n".join(lines[start:]), p.returncode


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--random-count", type=int, default=50,
                     help="number of random programs per run (README §9.4)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if SPIM is not None:
        return
    skip = pytest.mark.skip(reason="spim not found")
    for item in items:
        if "spim" in item.keywords:
            item.add_marker(skip)
