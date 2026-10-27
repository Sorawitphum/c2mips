"""Compile-error golden: errors/*.c -> stderr == *.err, exit 1 (Spec 10, 9.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2mips.__main__ import main

ERR_DIR = Path(__file__).parent / "errors"
ERRORS = sorted(ERR_DIR.glob("*.c"))
ARGS = "// c2mips-args:"  # first line of a test that needs extra CLI options (--target fpga)


@pytest.mark.parametrize("src", ERRORS, ids=lambda p: p.stem)
def test_error(src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
               capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(ERR_DIR)  # diagnostics print the path as given on the command line
    out = tmp_path / "out.s"
    want = src.with_suffix(".err").read_text(encoding="utf-8")
    has_error = ": error[" in want  # warnings alone (W001) still compile
    first = src.read_text(encoding="utf-8").partition("\n")[0]
    extra = first.removeprefix(ARGS).split() if first.startswith(ARGS) else []
    assert main([src.name, "-o", str(out), *extra]) == (1 if has_error else 0)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == want
    assert out.exists() != has_error


def test_every_lexer_parser_code_has_an_error_test() -> None:
    # M1 exit criterion: error tests for the lexer and the parser are complete.
    codes = {p.stem.split("_")[0].upper() for p in ERRORS}
    assert {"E001", "E002", "E003", "E010", "E011", "E025", "E026", "E027", "E030",
            "E031"} <= codes


def test_sema_codes_have_error_tests() -> None:
    # Spec 9.6: every diagnostic code has a test (E040 is generated in test_emitter.py).
    codes = {p.stem.split("_")[0].upper() for p in ERRORS}
    assert {"E020", "E021", "E022", "E023", "E024", "E028", "E029", "W001"} <= codes


def test_target_fpga_and_preprocessor_codes_have_error_tests() -> None:
    # ADR-009 / ADR-010
    codes = {p.stem.split("_")[0].upper() for p in ERRORS}
    assert {"E032", "E033", "E034"} <= codes
