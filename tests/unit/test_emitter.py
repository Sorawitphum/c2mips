"""Emitter: ASCII-only output, .asciiz/.byte rule, string interning, E040 (README 6.5, 6.6)."""

from __future__ import annotations

import re

import pytest

from c2mips.diagnostics import CompileError
from c2mips.driver import compile_source


def asm(body: str) -> str:
    return compile_source(f"int main(void) {{\n{body}\n}}\n", "t.c", runtime=False)


def data(body: str) -> list[str]:
    return re.findall(r"^__str\d+: .*$", asm(body), flags=re.M)


def test_asciiz_for_printable_ascii_with_n_t_quote() -> None:
    assert data('printf("a b\\t\\"q\\"\\n");') == ['__str0: .asciiz "a b\\t\\"q\\"\\n"']


def test_byte_for_backslash() -> None:
    # SPIM prints `\\` in .asciiz as two backslashes and MARS as one (S9, S16).
    assert data('printf("x\\\\y");') == ["__str0: .byte 120, 92, 121, 0"]


def test_byte_for_utf8_uses_signed_values() -> None:
    # Same bytes, but values >= 0x80 written negative so MARS does not warn (S17, ADR-007).
    assert data('printf("ส");') == ["__str0: .byte -32, -72, -86, 0"]


def test_strings_are_interned_in_first_use_order() -> None:
    assert data('printf("b\\n"); printf("a\\n"); printf("b\\n%d\\n", 1);') == [
        '__str0: .asciiz "b\\n"', '__str1: .asciiz "a\\n"', '__str2: .asciiz "\\n"',
    ]


def test_non_ascii_in_statement_comment_is_escaped() -> None:
    out = asm('printf("สว%d\\n", 1); // ส')
    assert out.isascii()
    assert '# printf("\\u0e2a\\u0e27%d\\n", 1);' in out.splitlines()


def test_no_data_strings_still_has_data_and_text() -> None:
    lines = asm("return 7;").splitlines()
    assert lines[1] == "        .data"
    assert lines[2] == ""
    assert lines[3] == "        .text"


def test_main_without_return_returns_zero() -> None:
    lines = asm('printf("x");').splitlines()
    i = lines.index("L_epi_main:")
    assert lines[i - 1] == f"{'        move  $v0, $zero':<35} # main returns 0 by default"


def test_div_labels_are_numbered_per_file() -> None:
    out = asm('printf("%d %d\\n", 8 / 2, 9 / 3);')
    assert re.findall(r"^(L\d+_\w+):", out, flags=re.M) == ["L1_div", "L1_end", "L2_div",
                                                           "L2_end"]


def test_too_many_instructions_is_e040() -> None:
    body = "    1 + 1;\n" * 5000  # ~8 instructions each
    with pytest.raises(CompileError) as e:
        asm(body)
    (d,) = e.value.diagnostics
    assert d.code == "E040"
    assert re.fullmatch(r"program too large: \d+ instructions \(limit 32000\)", d.message)
