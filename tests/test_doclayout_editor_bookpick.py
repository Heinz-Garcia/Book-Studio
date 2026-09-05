"""Tests fuer die Buchauswahl im Layout-Editor.

Ein Ordnerdialog, der im Code-Verzeichnis startet, ist die schlechteste aller
Antworten: Er beginnt dort, wo keine Buecher liegen, und ueberlaesst es dem
Benutzer, ein ``_quarto.yml`` zu erkennen. Book Studio weiss selbst, wo seine
Buecher stehen -- also fragt es mit dem, was es weiss.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from tools.doclayout.library import load_layout  # noqa: E402
from ui_qt.dialogs import doclayout_editor_dialog as modul  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import DocLayoutEditorDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])
@pytest.fixture(autouse=True)
def _ohne_vorschau(monkeypatch):
    """Legt den Vorschaulauf still -- diese Datei prueft ihn nicht.

    Jede Konstruktion des Dialogs startete sonst einen echten Lauf mit Pandoc
    und LibreOffice: ein paar Sekunden je Test, ein Temp-Verzeichnis mit
    LibreOffice-Profil je Lauf, und keiner davon wird hier ueberprueft. Bei
    neunzig Dialogen im Durchgang blieben tausende Ordner liegen und der
    gesamte Testlauf hing sich spaeter an einer ganz anderen Stelle auf.

    Den Vorschaulauf selbst pruefen ``test_doclayout_preview_runner.py`` und
    ``test_doclayout_editor_closing.py`` -- dort mit einem ersetzten
    ``render_preview``, ohne fremde Programme.
    """
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    replace(load_layout("IFJN_Referenz"), name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


@pytest.fixture()
def dialog(qapp, library: Path):
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    yield dlg
    # Offene Aenderungen wuerden beim Schliessen eine Rueckfrage ausloesen --
    # und nach dem Zuruecknehmen von ``monkeypatch`` waere das ein echter
    # modaler Dialog, an dem der Testlauf ohne Meldung haengen bliebe.
    dlg._session.mark_clean()
    dlg.close()


def _book(root: Path, name: str) -> Path:
    pfad = root / name
    pfad.mkdir(parents=True, exist_ok=True)
    (pfad / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    return pfad


@pytest.fixture()
def buecher(tmp_path: Path, monkeypatch) -> list[Path]:
    """Ersetzt die Buch-Suche durch drei Attrappen an einem festen Ort."""
    gefunden = [_book(tmp_path / "buecher", n) for n in ("Alpha", "Beta", "Gamma")]
    import ui_qt.book_workspace as bw

    monkeypatch.setattr(bw, "discover_books", lambda base=None: list(gefunden))
    return gefunden


def _capture_items(monkeypatch) -> dict:
    """Faengt die Auswahlliste ab und waehlt den ersten Eintrag."""
    aufzeichnung: dict = {}

    def fake(parent, titel, label, eintraege, aktuell=0, editierbar=True, **k):
        aufzeichnung["titel"] = titel
        aufzeichnung["eintraege"] = list(eintraege)
        aufzeichnung["aktuell"] = aktuell
        return eintraege[aufzeichnung.get("wahl", 0)], True

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(fake))
    return aufzeichnung


# ---------------------------------------------------------------------------


def test_the_known_books_are_offered(dialog, buecher, monkeypatch):
    aufzeichnung = _capture_items(monkeypatch)
    dialog._ask_book("Buch prüfen")
    angeboten = aufzeichnung["eintraege"]
    for buch in buecher:
        assert any(buch.name in eintrag for eintrag in angeboten)


def test_the_list_shows_where_each_book_lives(dialog, buecher, monkeypatch):
    """Gleichnamige Buecher an verschiedenen Orten waeren sonst ununterscheidbar."""
    aufzeichnung = _capture_items(monkeypatch)
    dialog._ask_book("Buch prüfen")
    assert str(buecher[0].parent) in aufzeichnung["eintraege"][0]


def test_choosing_a_book_returns_its_path(dialog, buecher, monkeypatch):
    _capture_items(monkeypatch)
    assert dialog._ask_book("Buch prüfen") == buecher[0]


def test_a_folder_tree_stays_available(dialog, buecher, monkeypatch):
    """Ein Buch ausserhalb der bekannten Orte muss weiterhin erreichbar sein."""
    aufzeichnung = _capture_items(monkeypatch)
    aufzeichnung["wahl"] = -1  # der letzte Eintrag
    gerufen: dict = {}

    def fake_browse(self, titel):
        gerufen["titel"] = titel
        return None

    monkeypatch.setattr(DocLayoutEditorDialog, "_browse_for_book", fake_browse)
    dialog._ask_book("Buch prüfen")
    assert gerufen["titel"] == "Buch prüfen"


def test_the_last_entry_is_the_folder_tree(dialog, buecher, monkeypatch):
    aufzeichnung = _capture_items(monkeypatch)
    dialog._ask_book("Buch prüfen")
    assert "Ordner" in aufzeichnung["eintraege"][-1]


def test_cancelling_returns_nothing(dialog, buecher, monkeypatch):
    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False))
    )
    assert dialog._ask_book("Buch prüfen") is None


def test_the_current_book_is_preselected(dialog, buecher, monkeypatch):
    """Wer schon ein Buch geprüft hat, will meist dasselbe wieder."""
    aufzeichnung = _capture_items(monkeypatch)
    dialog._book_path = buecher[2]
    dialog._ask_book("Buch prüfen")
    assert aufzeichnung["aktuell"] == 2


def test_a_book_outside_the_known_places_is_added(dialog, tmp_path, buecher, monkeypatch):
    fremd = _book(tmp_path / "woanders", "Fremd")
    aufzeichnung = _capture_items(monkeypatch)
    dialog._book_path = fremd
    dialog._ask_book("Buch prüfen")
    assert "Fremd" in aufzeichnung["eintraege"][0]
    assert aufzeichnung["aktuell"] == 0


# ---------------------------------------------------------------------------
# Ordnerbaum
# ---------------------------------------------------------------------------


def test_the_folder_tree_starts_where_books_live(dialog, buecher):
    """Regression: er startete im Code-Ordner, wo kein einziges Buch liegt."""
    assert dialog._books_root() == buecher[0].parent


def test_a_folder_without_quarto_yml_is_refused(dialog, tmp_path, monkeypatch):
    leer = tmp_path / "kein_buch"
    leer.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(leer))
    )
    gemeldet: dict = {}
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, titel, text, *a, **k: gemeldet.update(text=text)),
    )
    assert dialog._browse_for_book("Buch prüfen") is None
    assert "_quarto.yml" in gemeldet["text"]


def test_a_real_book_folder_is_accepted(dialog, tmp_path, monkeypatch):
    buch = _book(tmp_path, "Echt")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(buch))
    )
    assert dialog._browse_for_book("Buch prüfen") == buch


def test_cancelling_the_folder_tree_returns_nothing(dialog, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "")
    )
    assert dialog._browse_for_book("Buch prüfen") is None


def test_a_broken_book_search_does_not_break_the_dialog(dialog, monkeypatch):
    """Ohne erreichbare Buchliste bleibt der Ordnerbaum uebrig."""
    import ui_qt.book_workspace as bw

    def kaputt(base=None):
        raise OSError("Laufwerk nicht erreichbar")

    monkeypatch.setattr(bw, "discover_books", kaputt)
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "")
    )
    assert dialog._ask_book("Buch prüfen") is None
    assert modul is not None
