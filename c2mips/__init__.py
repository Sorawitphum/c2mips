"""c2mips: MiniC (C subset) -> MIPS32 assembly for SPIM/MARS."""

from pathlib import Path

__version__ = "0.1.0"

RUNTIME_S: Path = Path(__file__).parent / "runtime" / "runtime.s"
"""runtime.s (README appendix A) appended to every emitted .s file."""
