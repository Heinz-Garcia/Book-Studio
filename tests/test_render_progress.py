"""Der Fortschrittsbalken -- und warum er nicht luegt.

Ein Render meldete bisher nur Text im Protokoll. Wer auf ein Buch mit tausend
Seiten wartet, sah Zeilen vorbeilaufen und wusste trotzdem nicht, ob noch zehn
Sekunden oder zehn Minuten vor ihm lagen.

Der Fortschritt wird gelesen, nicht geschaetzt, wo es etwas zu lesen gibt:
Quarto meldet je Kapitel ``[3/57] kapitel.md``. Fuer die Phasen davor und
danach stehen feste Marken -- sie bewegen den Balken, ohne eine Genauigkeit
vorzutaeuschen, die es nicht gibt.
"""

from __future__ import annotations

import pytest

from services.render_progress import (
    CHAPTER_CEILING,
    CHAPTER_FLOOR,
    ProgressStep,
    RenderProgress,
)


# ---------------------------------------------------------------------------
# Echter Fortschritt: Quartos Kapitelzaehler
# ---------------------------------------------------------------------------


def test_the_chapter_counter_is_read_not_guessed():
    fortschritt = RenderProgress()
    stand = fortschritt.feed("[1/4] index.md")
    assert stand is not None
    assert stand.percent == CHAPTER_FLOOR + (CHAPTER_CEILING - CHAPTER_FLOOR) // 4
    assert "1 von 4" in stand.label


def test_the_last_chapter_does_not_reach_the_end():
    """Nach dem letzten Kapitel kommt noch der Satz selbst."""
    fortschritt = RenderProgress()
    stand = fortschritt.feed("[4/4] ende.md")
    assert stand is not None
    assert stand.percent == CHAPTER_CEILING
    assert stand.percent < 100


def test_the_chapter_count_is_remembered():
    fortschritt = RenderProgress()
    assert fortschritt.chapters_total is None
    fortschritt.feed("[2/57] kapitel.md")
    assert fortschritt.chapters_total == 57


def test_a_prefix_before_the_counter_does_not_hide_it():
    """Die Zeilen kommen teils mit ``[safe-render] `` davor."""
    fortschritt = RenderProgress()
    assert fortschritt.feed("[safe-render] [2/8] kapitel.md") is not None


def test_a_long_path_is_shortened_from_the_front():
    """Der Anfang eines Pfads sagt am wenigsten."""
    fortschritt = RenderProgress()
    stand = fortschritt.feed("[1/2] processed\\ein_sehr_langer_dateiname_" + "x" * 60 + ".md")
    assert stand is not None
    assert "processed" not in stand.label
    assert stand.label.endswith(".md")


def test_a_zero_total_is_ignored():
    """Sonst teilte der Balken durch null."""
    fortschritt = RenderProgress()
    assert fortschritt.feed("[0/0] nichts.md") is None


# ---------------------------------------------------------------------------
# Phasen ohne Zaehler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("zeile", "erwartet"),
    [
        ("safe_command=python quarto_render_safe.py ...", "Render wird vorbereitet"),
        ("[safe-render] book=Band format=typst", "Buch wird gelesen"),
        ("[typst]: Compiling index.typ to index.pdf...", "Seiten werden gesetzt"),
    ],
)
def test_the_phases_move_the_bar(zeile: str, erwartet: str):
    fortschritt = RenderProgress()
    stand = fortschritt.feed(zeile)
    assert stand is not None and stand.label == erwartet


def test_an_unknown_line_changes_nothing():
    """Bei tausenden Zeilen ist das der Unterschied zwischen fluessig und ruckelnd."""
    fortschritt = RenderProgress()
    assert fortschritt.feed("irgendeine Ausgabe ohne Bedeutung") is None
    assert fortschritt.percent == 0


def test_an_empty_line_changes_nothing():
    assert RenderProgress().feed("   ") is None


# ---------------------------------------------------------------------------
# Die zwei Zusicherungen
# ---------------------------------------------------------------------------


def test_the_bar_never_goes_backwards():
    """Ein zurueckspringender Balken liest sich wie ein Fehler."""
    fortschritt = RenderProgress()
    fortschritt.feed("[typst]: Compiling index.typ to index.pdf...")
    hoch = fortschritt.percent
    assert fortschritt.feed("[1/57] index.md") is None
    assert fortschritt.percent == hoch


def test_the_same_state_twice_is_reported_once():
    fortschritt = RenderProgress()
    assert fortschritt.feed("[2/4] a.md") is not None
    assert fortschritt.feed("[2/4] a.md") is None


def test_only_finish_gives_a_hundred():
    """Ein Balken auf 100, waehrend noch gearbeitet wird, ist schlimmer als keiner."""
    fortschritt = RenderProgress()
    for zeile in (
        "safe_command=x",
        "[safe-render] book=B format=typst",
        "[9/9] letztes.md",
        "[typst]: Compiling index.typ to index.pdf...DONE",
    ):
        fortschritt.feed(zeile)
    assert fortschritt.percent < 100
    assert fortschritt.finish().percent == 100


def test_finish_takes_a_label():
    assert RenderProgress().finish("Abgebrochen").label == "Abgebrochen"


# ---------------------------------------------------------------------------
# Der Word-Weg meldet Phasen selbst
# ---------------------------------------------------------------------------


def test_a_phase_can_be_announced_without_a_line():
    fortschritt = RenderProgress()
    stand = fortschritt.phase(ProgressStep(40, "Kapitel werden gesetzt"))
    assert stand is not None and stand.percent == 40


def test_a_phase_backwards_is_ignored_too():
    fortschritt = RenderProgress()
    fortschritt.phase(ProgressStep(60, "spaet"))
    assert fortschritt.phase(ProgressStep(20, "frueh")) is None


# ---------------------------------------------------------------------------
# Gegen ein echtes Protokoll
# ---------------------------------------------------------------------------


def test_a_real_log_runs_monotonically_up():
    """Die Zeilenfolge stammt aus einem tatsaechlichen Typst-Render."""
    zeilen = [
        "safe_command=python quarto_render_safe.py Band --to typst",
        "[safe-render] ::: Hinweis: keine strukturellen Defekte",
        "[safe-render] book=Band format=typst",
        "[1/2] index.md",
        "[2/2] processed\\kapitel.md",
        "pandoc",
        "  output-file: index.typ",
        "[typst]: Compiling index.typ to index.pdf...DONE",
    ]
    fortschritt = RenderProgress()
    staende = [s.percent for s in (fortschritt.feed(z) for z in zeilen) if s]
    assert staende == sorted(staende)
    assert len(staende) >= 5
    assert fortschritt.percent < 100
