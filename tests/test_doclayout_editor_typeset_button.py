"""Der Knopf »Buch setzen« -- und was er tut, wenn es schiefgeht.

Der Lauf dauert je nach Umfang Sekunden bis Minuten. Im GUI-Faden hiesse das:
Das Fenster friert ein, Windows malt "Keine Rueckmeldung" darueber, und der
Benutzer schiesst die Anwendung ab -- mitten in einem Pandoc-Lauf. Deshalb ein
eigener Faden, und deshalb diese Tests.

Gesetzt wird hier nie wirklich: Geprueft wird die Verdrahtung.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.typeset import TypesetResult  # noqa: E402
from ui_qt.dialogs import doclayout_editor_dialog as D  # noqa: E402
from ui_qt.dialogs.doclayout_typeset_runner import TypesetRunner  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def keine_echte_vorschau(monkeypatch):
    """Der Editor setzt beim Oeffnen einen Mustertext -- hier unerwuenscht."""
    monkeypatch.setattr(D.DocLayoutEditorDialog, "_start_preview", lambda *a, **k: None)


@pytest.fixture()
def dialog(app, monkeypatch):
    fenster = D.DocLayoutEditorDialog()
    yield fenster
    fenster._teardown()
    fenster.deleteLater()


# ---------------------------------------------------------------------------
# Der Lauf laeuft nebenher
# ---------------------------------------------------------------------------


def test_the_runner_refuses_a_second_run(tmp_path: Path, monkeypatch):
    """Zwei Saetze desselben Buchs schrieben in dieselben Dateien."""
    runner = TypesetRunner()
    monkeypatch.setattr(
        type(runner), "is_running", property(lambda self: True)
    )
    assert runner.start(load_layout("IFJN_layout"), tmp_path) is False


def test_a_released_runner_starts_nothing(tmp_path: Path):
    """Nach dem Schliessen darf nichts mehr anlaufen."""
    runner = TypesetRunner()
    runner.release()
    assert runner.start(load_layout("IFJN_layout"), tmp_path) is False


def test_releasing_twice_is_allowed():
    """Der Dialog wird auf mehreren Wegen verlassen; keiner soll das wissen muessen."""
    runner = TypesetRunner()
    runner.release()
    runner.release()
    assert runner.released is True


# ---------------------------------------------------------------------------
# Der Knopf
# ---------------------------------------------------------------------------


class MeldungsAttrappe:
    """Steht fuer ``QMessageBox`` -- mit echten Aufzaehlungen, falschem Fenster.

    Die Aufzaehlungen (``StandardButton``, ``ButtonRole``) kommen vom Original:
    Der Dialog benutzt sie, und sie nachzubauen hiesse, den Test gegen eine
    Erfindung laufen zu lassen statt gegen Qt.
    """

    StandardButton = QMessageBox.StandardButton
    ButtonRole = QMessageBox.ButtonRole
    letzter: dict[str, str] = {}

    def __init__(self, *a, **k):
        MeldungsAttrappe.letzter = {}

    def setWindowTitle(self, titel):
        MeldungsAttrappe.letzter["titel"] = titel

    def setText(self, text):
        MeldungsAttrappe.letzter["text"] = text

    def addButton(self, *a, **k):
        return None

    def exec(self):
        return 0

    def clickedButton(self):
        return None


def test_the_button_exists_and_says_what_it_does(dialog):
    assert dialog.typeset_button.text() == "Buch setzen..."
    hinweis = dialog.typeset_button.toolTip()
    assert "ganze Buch" in hinweis
    assert "export/doclayout" in hinweis


def test_the_button_locks_itself_while_running(dialog):
    """Sonst startete ein zweiter Klick einen zweiten Lauf."""
    dialog._on_typeset_busy()
    assert dialog.typeset_button.isEnabled() is False
    assert "gesetzt" in dialog.typeset_button.text()


def test_the_button_comes_back_after_a_failure(dialog, monkeypatch):
    """Ein gescheiterter Lauf darf den Knopf nicht dauerhaft sperren."""
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    dialog._on_typeset_busy()
    dialog._on_typeset_failed("Pandoc fehlt.")
    assert dialog.typeset_button.isEnabled() is True
    assert dialog.typeset_button.text() == "Buch setzen..."


def test_the_button_comes_back_after_a_run(dialog, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(D, "QMessageBox", MeldungsAttrappe)
    dialog._on_typeset_busy()
    dialog._on_typeset_ready(
        TypesetResult(docx=tmp_path / "a.docx", pdf=None, chapters=("a.md", "b.md"))
    )
    assert dialog.typeset_button.isEnabled() is True
    assert "2 Kapiteldatei(en)" in MeldungsAttrappe.letzter["text"]


def test_pandoc_warnings_reach_the_user(dialog, monkeypatch, tmp_path: Path):
    """Sie betreffen sein Manuskript -- sie zu verschlucken waere Bevormundung."""
    monkeypatch.setattr(D, "QMessageBox", MeldungsAttrappe)
    dialog._on_typeset_ready(
        TypesetResult(
            docx=tmp_path / "a.docx",
            pdf=None,
            chapters=("a.md",),
            warnings=("[WARNING] Div unclosed at kap1.md line 7",),
        )
    )
    assert "Div unclosed" in MeldungsAttrappe.letzter["text"]


def test_the_pdf_gets_its_own_button(dialog, monkeypatch, tmp_path: Path):
    """Wer eben zehn Minuten gewartet hat, soll nicht auch noch suchen muessen."""
    knoepfe: list[str] = []

    class MitKnopf(MeldungsAttrappe):
        def addButton(self, *a, **k):
            if a and isinstance(a[0], str):
                knoepfe.append(a[0])
            return None

    monkeypatch.setattr(D, "QMessageBox", MitKnopf)
    pdf = tmp_path / "fertig.pdf"
    pdf.write_bytes(b"%PDF")
    dialog._on_typeset_ready(
        TypesetResult(docx=tmp_path / "a.docx", pdf=pdf, chapters=("a.md",))
    )
    assert knoepfe == ["PDF öffnen"]


def test_a_cancelled_book_choice_starts_nothing(dialog, monkeypatch):
    monkeypatch.setattr(D.DocLayoutEditorDialog, "_ask_book", lambda self, titel: None)
    monkeypatch.setattr(
        TypesetRunner, "start",
        lambda *a, **k: pytest.fail("ohne Buch darf nichts starten"),
    )
    dialog._typeset_book()


def test_declining_the_question_starts_nothing(dialog, monkeypatch, tmp_path: Path):
    """Der Rueckfrage-Dialog ist die letzte Bremse vor einem langen Lauf."""
    (tmp_path / "_quarto.yml").write_text(
        "book:\n  chapters:\n    - a.md\n", encoding="utf-8"
    )
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(D.DocLayoutEditorDialog, "_ask_book", lambda self, titel: tmp_path)
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Cancel,
    )
    monkeypatch.setattr(
        TypesetRunner, "start",
        lambda *a, **k: pytest.fail("abgelehnt heisst abgelehnt"),
    )
    dialog._typeset_book()


def test_a_book_without_a_chapter_list_is_refused_early(
    dialog, monkeypatch, tmp_path: Path
):
    """Der Fehler faellt vor der Rueckfrage auf, nicht erst nach Minuten."""
    (tmp_path / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    gemeldet: list[str] = []
    monkeypatch.setattr(D.DocLayoutEditorDialog, "_ask_book", lambda self, titel: tmp_path)
    monkeypatch.setattr(
        QMessageBox, "critical", lambda parent, titel, text, *a: gemeldet.append(text)
    )
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: pytest.fail("erst pruefen, dann fragen"),
    )
    dialog._typeset_book()
    assert gemeldet and "Kapitelliste" in gemeldet[0]
