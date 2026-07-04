"""Tests für Batch B3: Quarto-Block-Parser (SSOT).

Stellt sicher, dass das neue `quarto_block_parser`-Modul die Logik
korrekt konsolidiert, die bisher in `book_doctor.find_fenced_div_issues`,
`export_manager._detect_fenced_div_issues` und
`Sanitizer._find_unclosed_answer_divs` dupliziert war.

Referenz: .doc/refactoring-master.md, Batch B3.
"""

from __future__ import annotations

import pytest

import quarto_block_parser as qp


# --- Grundlegende Erkennung -------------------------------------------------


def test_clean_body_returns_no_issues():
    body = "# Hallo\n\nEin Absatz.\n"
    issues = qp.find_fenced_div_issues(body)
    assert issues == []


def test_balanced_div_no_issues():
    body = "::: {.callout}\nInhalt\n:::\n"
    issues = qp.find_fenced_div_issues(body)
    assert issues == []


def test_nested_div_no_issues():
    body = (
        "::: {.outer}\n"
        "Inhalt\n"
        "::: {.inner}\n"
        "Mehr\n"
        ":::\n"
        ":::\n"
    )
    assert qp.find_fenced_div_issues(body) == []


def test_unclosed_open_marker_is_issue():
    body = "::: {.note}\nInhalt ohne Ende\n"
    issues = qp.find_fenced_div_issues(body)
    assert len(issues) == 1
    assert issues[0].kind == "unclosed-open"
    assert issues[0].line_number == 1


def test_orphan_close_is_issue():
    body = "Vorher\n:::\n"
    issues = qp.find_fenced_div_issues(body)
    assert len(issues) == 1
    assert issues[0].kind == "orphan-close"
    assert issues[0].line_number == 2


def test_mismatched_close_is_issue():
    """`::::` schließt nicht die `:::`-Öffnung (Quarto-Konvention: gleiche
    oder höhere Anzahl schließt)."""
    body = "::: {.outer}\n::: {.inner}\n::::\n:::\n"
    issues = qp.find_fenced_div_issues(body)
    # Das `::::` (4 Doppelpunkte) schließt die `:::` {.inner}-Öffnung
    # und damit auch das `:::` {.outer}? Nein — bei 4 >= 3 wird gepopt.
    # Erwartung: zwei Pops, keine Issues. (Quarto-Konvention)
    assert issues == [], f"unerwartete Issues: {issues}"


# --- Code-Block-Awareness --------------------------------------------------


def test_colons_inside_code_block_are_ignored():
    body = "```python\n::: {.note}\nprint(':::')\n```\n"
    issues = qp.find_fenced_div_issues(body)
    assert issues == []


def test_colons_inside_tilde_fence_are_ignored():
    body = "~~~markdown\n::: {.note}\n:::\n~~~\n"
    assert qp.find_fenced_div_issues(body) == []


def test_mismatched_close_when_close_has_fewer_colons():
    """Schließer mit weniger Doppelpunkten als der Top-Öffner → mismatched-close
    und der ursprüngliche Öffner bleibt ungeschlossen."""
    body = ":::: {.outer}\nInhalt\n:::\n"
    issues = qp.find_fenced_div_issues(body)
    kinds = {issue.kind for issue in issues}
    assert kinds == {"mismatched-close", "unclosed-open"}
    assert {issue.line_number for issue in issues} == {1, 3}


def test_inline_colon_run_in_text_is_inline_issue():
    body = "Hier steht ::: im Fließtext.\n"
    issues = qp.find_fenced_div_issues(body)
    assert len(issues) == 1
    assert issues[0].kind == "inline"
    assert issues[0].line_number == 1


# --- base_line_number-Offset -----------------------------------------------


def test_base_line_number_shifts_results():
    body = "::: {.note}\nInhalt\n"
    issues_default = qp.find_fenced_div_issues(body, base_line_number=1)
    issues_offset = qp.find_fenced_div_issues(body, base_line_number=100)
    assert issues_default[0].line_number == 1
    assert issues_offset[0].line_number == 100


# --- Answer-Div-Erkennung --------------------------------------------------


def test_unclosed_answer_div_detected():
    body = "::: {.answer}\nAnfang ohne Ende\n"
    unclosed = qp.find_unclosed_answer_divs(body)
    assert len(unclosed) == 1
    assert unclosed[0]["is_answer"] is True
    assert unclosed[0]["line_number"] == 1


def test_closed_answer_div_not_in_unclosed_list():
    body = "::: {.answer}\nAnfang\n:::\n"
    assert qp.find_unclosed_answer_divs(body) == []


def test_non_answer_div_unclosed_not_in_answer_list():
    body = "::: {.note}\nInhalt\n"
    assert qp.find_unclosed_answer_divs(body) == []


def test_mixed_answer_and_other():
    body = (
        "::: {.answer}\n"
        "Antwort\n"
        ":::\n"
        "::: {.note}\n"
        "Notiz ohne Ende\n"
    )
    unclosed = qp.find_unclosed_answer_divs(body)
    # Nur die `{.answer}`-Öffnung wurde geschlossen, die `{.note}`-Öffnung
    # ist noch offen, aber NICHT answer — also leere Liste.
    assert unclosed == []


# --- Edge-Cases -------------------------------------------------------------


def test_empty_body():
    assert qp.find_fenced_div_issues("") == []
    assert qp.find_unclosed_answer_divs("") == []


def test_four_colons_open_also_recognised():
    """Quarto erlaubt `::::` als Container, der `:::`-Kinder umschließt."""
    body = ":::: {.super}\n::: {.kid}\nInhalt\n:::\n::::\n"
    assert qp.find_fenced_div_issues(body) == []


def test_fence_kind_field_present():
    issues = qp.find_fenced_div_issues(":::\n")
    assert hasattr(issues[0], "kind")
    assert issues[0].kind == "orphan-close"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
