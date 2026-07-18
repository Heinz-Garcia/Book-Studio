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


# --- Phase 3: Code-Fence-sichere Zeileniter (Cluster 3.5) --------------------


def test_iter_body_lines_outside_code_fences_empty_body():
    """Test für Cluster 3.5: Leerer Body sollte keine Zeilen liefern."""
    # Diese Test wird rot sein, bis iter_body_lines_outside_code_fences implementiert ist
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
        lines = list(iter_body_lines_outside_code_fences(""))
        assert lines == []
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")


def test_iter_body_lines_outside_code_fences_basic():
    """Grundlegend: Zeilen außerhalb von Fences sollten mit in_code_fence=False geliefert werden."""
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = "Zeile 1\nZeile 2\n"
    lines = list(iter_body_lines_outside_code_fences(body))
    assert len(lines) == 2
    line_num_1, text_1, in_fence_1 = lines[0]
    line_num_2, text_2, in_fence_2 = lines[1]
    assert line_num_1 == 1
    assert text_1 == "Zeile 1"
    assert in_fence_1 is False
    assert line_num_2 == 2
    assert text_2 == "Zeile 2"
    assert in_fence_2 is False


def test_iter_body_lines_outside_code_fences_skips_inside_backtick_fence():
    """Test für Cluster 3.5: Zeilen INNERHALB von ```-Fences sollten mit in_code_fence=True markiert sein."""
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = "Vorher\n```python\nprint('---')\n```\nNachher\n"
    lines = list(iter_body_lines_outside_code_fences(body))

    # Zeile 1: "Vorher" -> outside
    assert lines[0][0] == 1
    assert lines[0][2] is False  # not in_fence

    # Zeile 2: "```python" -> inside fence
    assert lines[1][0] == 2
    assert lines[1][2] is True  # in_fence (Fence-Zeile ist auch Teil der Fence)

    # Zeile 3: "print('---')" -> inside fence
    assert lines[2][0] == 3
    assert lines[2][2] is True  # in_fence

    # Zeile 4: "```" -> Fence-Ende, noch als in_fence markiert
    assert lines[3][0] == 4
    assert lines[3][2] is True  # in_fence (Fence-Zeile)

    # Zeile 5: "Nachher" -> outside fence
    assert lines[4][0] == 5
    assert lines[4][2] is False  # not in_fence


def test_iter_body_lines_outside_code_fences_handles_tilde_fences():
    """Test für Cluster 3.5: auch ~~~-Fences sollten erkannt werden."""
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = "Vorher\n~~~\nInhalt\n~~~\nNachher\n"
    lines = list(iter_body_lines_outside_code_fences(body))

    # Vorher
    assert lines[0][2] is False
    # Tilde-Fence-Start
    assert lines[1][2] is True
    # Inhalt
    assert lines[2][2] is True
    # Tilde-Fence-End
    assert lines[3][2] is True
    # Nachher
    assert lines[4][2] is False


def test_iter_body_lines_outside_code_fences_tripledash_inside_fence_ignored():
    """Test für Cluster 3.5: `---` INNERHALB eines Code-Blocks sollte vom
    `iter_body_lines_outside_code_fences` als 'in_fence' markiert werden."""
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = "```yaml\nkey1: value1\n---\nkey2: value2\n```\n"
    lines = list(iter_body_lines_outside_code_fences(body))

    # Finde die `---`-Zeile (sollte Zeile 3 sein)
    dash_line = [l for l in lines if l[1].strip() == "---"][0]
    line_num, text, in_fence = dash_line
    assert in_fence is True, "--- innerhalb eines Code-Blocks sollte als in_fence=True markiert sein"


# --- Phase 3, R1: Fence-Typ-Bewusstsein (Rescan 2026-07-18) ------------------


def test_iter_body_lines_fence_type_aware_nested_backticks_with_tildes():
    """R1: Öffnender ```-Fence sollte NICHT durch ~~~ geschlossen werden.

    Reproduziert den Bug aus specifications.md: Ein äußerer ```-Block
    mit einem eingebetteten ~-ähnlichen Inhalt sollte alle Zeilen
    korrekt als 'in_fence=True' markieren.
    """
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = (
        "```markdown\n"
        "Beispiel:\n"
        "~~~\n"
        "Das ist im inneren Beispiel\n"
        "---\n"
        "Ende des inneren Beispiels\n"
        "~~~\n"
        "Noch im aeusseren Codeblock:\n"
        "---\n"
        "```\n"
    )
    lines = list(iter_body_lines_outside_code_fences(body))

    # Erwartung: Zeile 1-10 sollen alle in_fence=True sein (alles ist im äußeren ``` ``` -Block)
    # Die ~~~ sollten NICHT den äußeren ``` ``` -Block schließen
    for line_num, text, in_fence in lines:
        assert in_fence is True, (
            f"Zeile {line_num} ({text!r}) sollte in_fence=True sein, "
            f"aber war {in_fence}. Nested ~~~ sollte ``` ``` nicht schließen."
        )


def test_iter_body_lines_fence_type_aware_nested_tildes_with_backticks():
    """R1: Öffnender ~~~-Fence sollte NICHT durch ``` geschlossen werden.

    Symmetrisch zu obigem Test: ~~~ als äußerer Block mit ```  als innerer "Fence".
    """
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = (
        "~~~markdown\n"
        "Beispiel:\n"
        "```\n"
        "Das ist im inneren Beispiel\n"
        "---\n"
        "Ende des inneren Beispiels\n"
        "```\n"
        "Noch im aeusseren Tilde-Block:\n"
        "~~~\n"
    )
    lines = list(iter_body_lines_outside_code_fences(body))

    # Erwartung: Zeile 1-9 sollen alle in_fence=True sein (alles ist im äußeren ~~~ ~~~ -Block)
    for line_num, text, in_fence in lines:
        assert in_fence is True, (
            f"Zeile {line_num} ({text!r}) sollte in_fence=True sein, "
            f"aber war {in_fence}. Nested ``` sollte ~~~ nicht schließen."
        )


def test_iter_body_lines_fence_length_matters():
    """R1: Fence-Länge sollte beachtet werden (CommonMark-Semantik).

    Ein öffnender ``````` (7 Backticks) sollte nur durch
    ``````` oder länger geschlossen werden, nicht durch ``` (3 Backticks).
    """
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = (
        "`````````\n"
        "Innerer Code:\n"
        "```\n"
        "Foo\n"
        "```\n"
        "Noch im äußeren Block\n"
        "`````````\n"
    )
    lines = list(iter_body_lines_outside_code_fences(body))

    # Alle Zeilen sollten in_fence=True sein (die ``` mit 3 Backticks können
    # die 9 Backticks nicht schließen)
    for line_num, text, in_fence in lines:
        assert in_fence is True, (
            f"Zeile {line_num} sollte in_fence=True sein (nested triple-backticks "
            f"können 9-backtick-fence nicht schließen)"
        )


def test_iter_body_lines_backtick_fence_exactly_matches_length():
    """R1: Fence-Schließung muss GLEICHE oder LÄNGERE Backticks sein."""
    try:
        from quarto_block_parser import iter_body_lines_outside_code_fences
    except ImportError:
        pytest.skip("iter_body_lines_outside_code_fences noch nicht implementiert")

    body = (
        "```\n"
        "Innerhalb\n"
        "```\n"
        "Außerhalb\n"
    )
    lines = list(iter_body_lines_outside_code_fences(body))

    # Zeile 1-3 im Fence, Zeile 4 außerhalb
    assert lines[0][2] is True  # ``` opening
    assert lines[1][2] is True  # content
    assert lines[2][2] is True  # ``` closing
    assert lines[3][2] is False  # outside


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
