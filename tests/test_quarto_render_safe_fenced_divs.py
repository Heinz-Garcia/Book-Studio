"""Regression: quarto_render_safe nutzt quarto_block_parser als SSOT."""

from __future__ import annotations

import quarto_block_parser as qp
from quarto_render_safe import _detect_fenced_div_issues


def _issues_from_ssot(body: str) -> list[tuple[int, str]]:
    return [(i.line_number, i.kind) for i in qp.find_fenced_div_issues(body)]


def test_detect_fenced_div_issues_matches_ssot_clean():
    body = "::: {.callout}\nInhalt\n:::\n"
    assert _detect_fenced_div_issues(body.splitlines()) == _issues_from_ssot(body)


def test_detect_fenced_div_issues_matches_ssot_unclosed():
    body = "::: {.note}\nOffen\n"
    assert _detect_fenced_div_issues(body.splitlines()) == _issues_from_ssot(body)


def test_detect_fenced_div_issues_matches_ssot_orphan_close():
    body = "Text\n:::\n"
    assert _detect_fenced_div_issues(body.splitlines()) == _issues_from_ssot(body)


def test_detect_fenced_div_issues_matches_ssot_inline():
    body = "Siehe ::: im Text.\n"
    assert _detect_fenced_div_issues(body.splitlines()) == _issues_from_ssot(body)


def test_detect_fenced_div_issues_matches_ssot_code_block():
    body = "~~~markdown\n::: {.note}\n:::\n~~~\n"
    assert _detect_fenced_div_issues(body.splitlines()) == _issues_from_ssot(body)
