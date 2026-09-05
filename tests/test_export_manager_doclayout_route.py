"""Die Weiche im Render: ``docx`` + Formatvorlage geht ueber Pandoc.

Warum ueberhaupt eine Weiche -- Quarto koennte die ``.docx`` auch setzen:
Pandoc schreibt in sie nur ein Verzeichnis**feld**, also die Anweisung, dass
dort ein Inhaltsverzeichnis hingehoert. Word fuehrt sie beim Oeffnen aus,
``soffice --convert-to pdf`` niemals. Die PDF trug dann die Ueberschrift
"Inhaltsverzeichnis" und darunter nichts. Der doclayout-Weg baut es auf, setzt
den Umbruch dahinter und liefert ``.docx`` **und** PDF.

Ohne gewaehlte Formatvorlage darf sich nichts aendern: Dann rendert Quarto wie
vorher.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from export_manager import ExportManager
from tools.doclayout.typeset import TypesetResult


class _FakeStudio:
    def __init__(self, book_path: Path):
        self._book_path = book_path
        self.log_records: list[tuple[str, str]] = []
        self.status: list[tuple[str, str]] = []
        self.clipboard: list[str] = []

    def get_current_book(self):
        return self._book_path

    def log(self, message, level="info"):
        self.log_records.append((message, level))

    def read_config(self):
        return {}

    def set_status(self, text, fg="#000000"):
        self.status.append((text, fg))

    def copy_text_to_clipboard(self, text):
        self.clipboard.append(text)


@pytest.fixture()
def manager(tmp_path: Path) -> ExportManager:
    buch = tmp_path / "Band"
    buch.mkdir()
    (buch / "_quarto.yml").write_text("book:\n  chapters:\n    - a.md\n", encoding="utf-8")
    (buch / "a.md").write_text("# A\n", encoding="utf-8")
    return ExportManager(_FakeStudio(buch))


def _text(records) -> str:
    return "\n".join(m for m, _ in records)


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


def test_a_finished_run_names_both_files(manager, tmp_path: Path):
    ergebnis = TypesetResult(
        docx=tmp_path / "Band.docx",
        pdf=tmp_path / "Band.pdf",
        chapters=("a.md", "b.md"),
    )
    manager._doclayout_finished(ergebnis)
    protokoll = _text(manager.studio.log_records)
    assert "2 Kapiteldatei(en)" in protokoll
    assert "Band.docx" in protokoll
    assert "Band.pdf" in protokoll


def test_the_pdf_path_lands_on_the_clipboard(manager, tmp_path: Path):
    """Wie beim normalen Render -- man will sie gleich oeffnen koennen."""
    ergebnis = TypesetResult(
        docx=tmp_path / "Band.docx", pdf=tmp_path / "Band.pdf", chapters=("a.md",)
    )
    manager._doclayout_finished(ergebnis)
    assert manager.studio.clipboard == [str(tmp_path / "Band.pdf")]


def test_without_a_pdf_the_docx_still_counts(manager, tmp_path: Path):
    """Kein Notfall: Die Datei laesst sich oeffnen, nur nicht anzeigen."""
    ergebnis = TypesetResult(
        docx=tmp_path / "Band.docx",
        pdf=None,
        chapters=("a.md",),
        note="LibreOffice wurde nicht gefunden.",
    )
    manager._doclayout_finished(ergebnis)
    protokoll = _text(manager.studio.log_records)
    assert "Band.docx" in protokoll
    assert "LibreOffice" in protokoll
    assert manager.studio.clipboard == []


def test_pandoc_warnings_reach_the_log(manager, tmp_path: Path):
    """Sie betreffen das Manuskript des Autors, nicht dieses Werkzeug."""
    ergebnis = TypesetResult(
        docx=tmp_path / "Band.docx",
        pdf=None,
        chapters=("a.md",),
        warnings=("[WARNING] Div unclosed at a.md line 7",),
    )
    manager._doclayout_finished(ergebnis)
    assert "Div unclosed" in _text(manager.studio.log_records)


def test_many_warnings_are_capped_but_counted(manager, tmp_path: Path):
    """Vierzig Zeilen Pandoc verdecken sonst alles andere im Protokoll."""
    ergebnis = TypesetResult(
        docx=tmp_path / "Band.docx",
        pdf=None,
        chapters=("a.md",),
        warnings=tuple(f"[WARNING] Nummer {i}" for i in range(25)),
    )
    manager._doclayout_finished(ergebnis)
    protokoll = _text(manager.studio.log_records)
    assert "Nummer 0" in protokoll
    assert "Nummer 24" not in protokoll
    assert "15 weitere" in protokoll


def test_a_failure_is_reported_not_swallowed(manager):
    manager._doclayout_failed("Pandoc nicht gefunden.")
    protokoll = _text(manager.studio.log_records)
    assert "Pandoc nicht gefunden." in protokoll
    assert any(stufe == "error" for _m, stufe in manager.studio.log_records)


# ---------------------------------------------------------------------------
# Der Start
# ---------------------------------------------------------------------------


def test_an_unknown_template_stops_before_anything_runs(manager, monkeypatch):
    """Der Fehler faellt sofort auf, nicht erst nach Minuten."""
    import threading

    monkeypatch.setattr(
        threading, "Thread",
        lambda *a, **k: pytest.fail("es haette nichts starten duerfen"),
    )
    manager._start_doclayout_typeset("gibt_es_nicht")
    assert "nicht lesbar" in _text(manager.studio.log_records)
    assert manager._render_running is False


def test_the_template_label_is_logged(manager, monkeypatch):
    """Wer hinterher ins Protokoll sieht, muss die benutzte Vorlage finden."""
    gestartet: list[object] = []

    class Faden:
        def __init__(self, *a, **k):
            gestartet.append(k.get("target"))

        def start(self):
            pass

    monkeypatch.setattr("export_manager.threading.Thread", Faden)
    manager._start_doclayout_typeset("IFJN_layout")
    protokoll = _text(manager.studio.log_records)
    assert "Formatvorlage" in protokoll
    assert gestartet, "der Lauf gehoert in einen eigenen Faden"


def test_without_a_book_nothing_starts(tmp_path: Path, monkeypatch):
    class OhneBuch(_FakeStudio):
        def get_current_book(self):
            return None

    manager = ExportManager(OhneBuch(tmp_path))
    monkeypatch.setattr(
        "export_manager.threading.Thread",
        lambda *a, **k: pytest.fail("ohne Buch darf nichts starten"),
    )
    manager._start_doclayout_typeset("IFJN_layout")
    assert "Kein Buch" in _text(manager.studio.log_records)
