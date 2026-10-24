"""Static checks on runtime.s (README appendix A, §6.6, §6.8, Q20, NFR-6)."""

from __future__ import annotations

import re

from conftest import REPO

from c2mips import RUNTIME_S


def code_lines() -> list[str]:
    return [ln.split("#", 1)[0] for ln in RUNTIME_S.read_text(encoding="ascii").splitlines()]


def test_runtime_is_ascii() -> None:
    # SPIM 8.0 hangs on any byte > 0x7F, even in a comment (S8).
    assert all(b <= 0x7F for b in RUNTIME_S.read_bytes())


def test_runtime_matches_readme_appendix_a() -> None:
    # runtime.s is the tested listing from the spec; it must not be rewritten.
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split("## ภาคผนวก A", 1)[1]
    listing = section.split("```asm\n", 1)[1].split("```", 1)[0]
    assert RUNTIME_S.read_text(encoding="ascii") == listing


def test_runtime_never_touches_stack_or_saved_regs() -> None:
    bad = re.compile(r"\$(sp|fp|gp|s[0-7]|ra)\b")
    offenders = [ln for ln in code_lines() if bad.search(ln) and ln.split() != ["jr", "$ra"]]
    assert offenders == []


def test_runtime_labels_are_namespaced() -> None:
    # README §6.5: compiler-internal names never start with f_ ; runtime uses __rt_.
    labels = [m.group(1) for ln in code_lines() if (m := re.match(r"^(\w+):", ln))]
    assert labels
    assert all(lb.startswith("__rt_") for lb in labels)
    assert {"__rt_nCk", "__rt_div0", "__rt_panic"} <= set(labels)
