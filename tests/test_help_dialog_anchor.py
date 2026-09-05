"""Tests fuer den Sprung ins richtige Handbuchkapitel.

Ein Handbuch mit dreiundzwanzig Kapiteln liest niemand von vorn, wenn er
gerade an einer Stelle nicht weiterkommt. Der Weg von der Frage zur Antwort
soll ein Klick sein.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui_qt.dialogs.help_dialog import HelpDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def handbuch() -> Path:
    path = Path(__file__).resolve().parent.parent / "doc" / "handbuch.html"
    if not path.is_file():
        pytest.skip("doc/handbuch.html ist nicht erzeugt")
    return path


def _oeffne(handbuch: Path, anchor: str | None) -> HelpDialog:
    dlg = HelpDialog(None, handbuch, anchor=anchor)
    dlg.resize(900, 700)
    dlg.show()
    QApplication.processEvents()
    QApplication.processEvents()  # showEvent -> singleShot(0) -> Sprung
    return dlg


def test_without_an_anchor_the_manual_starts_at_the_top(qapp, handbuch: Path):
    dlg = _oeffne(handbuch, None)
    try:
        assert dlg.browser.verticalScrollBar().value() == 0
    finally:
        dlg.close()


def test_an_anchor_scrolls_to_its_chapter(qapp, handbuch: Path):
    dlg = _oeffne(handbuch, "sec-doclayout")
    try:
        assert dlg.browser.verticalScrollBar().value() > 0
    finally:
        dlg.close()


def test_the_chapter_heading_ends_up_at_the_top(qapp, handbuch: Path):
    """Nicht irgendwo hin scrollen, sondern genau dorthin."""
    dlg = _oeffne(handbuch, "sec-doclayout")
    try:
        text = dlg.browser.toPlainText()
        kapitel = text.find("23) Layout-Editor")
        assert kapitel > 0, "das Kapitel steht nicht im Handbuch"
        oben = dlg.browser.cursorForPosition(
            dlg.browser.viewport().rect().topLeft()
        ).position()
        assert abs(oben - kapitel) < 500, (
            f"Sprungziel um {abs(oben - kapitel)} Zeichen daneben"
        )
    finally:
        dlg.close()


def test_two_anchors_land_in_different_places(qapp, handbuch: Path):
    """Sonst waere der Sprung nur zufaellig richtig."""
    eins = _oeffne(handbuch, "sec-doclayout")
    zwei = _oeffne(handbuch, "sec-schnellstart")
    try:
        assert eins.browser.verticalScrollBar().value() != (
            zwei.browser.verticalScrollBar().value()
        )
    finally:
        eins.close()
        zwei.close()


def test_an_unknown_anchor_does_not_raise(qapp, handbuch: Path):
    """Ein umbenanntes Kapitel darf die Hilfe nicht unbenutzbar machen."""
    dlg = _oeffne(handbuch, "gibt-es-nicht")
    try:
        assert dlg.browser.toPlainText().strip() != ""
    finally:
        dlg.close()


def test_the_layout_editor_points_at_its_own_chapter():
    """Der Anker ist fest vergeben, nicht aus der Ueberschrift abgeleitet."""
    from ui_qt.dialogs.doclayout_editor_dialog import _HANDBOOK_ANCHOR

    quelle = (
        Path(__file__).resolve().parent.parent / "doc" / "handbuch.md"
    ).read_text(encoding="utf-8")
    assert f"{{#{_HANDBOOK_ANCHOR}}}" in quelle, (
        f"Der Anker {_HANDBOOK_ANCHOR} steht nicht mehr im Handbuch"
    )
