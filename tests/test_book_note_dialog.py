"""Das Notizfenster darf keine Arbeit verlieren.

Ein Notizblock, der Getipptes wegwirft, weil jemand den Speichern-Knopf nicht
gefunden hat, ist schlimmer als keiner. Deshalb wird beim Buchwechsel und beim
Schließen von selbst gesichert — der Knopf sagt nur, dass etwas offen ist.

Zusätzlich geprüft: dass die Liste sichtbar macht, wo schon etwas steht. Ohne
das müsste man jedes Buch einzeln anklicken, um zu sehen, ob es eine Notiz hat.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tools.book_note import store  # noqa: E402
from ui_qt.dialogs.book_note_dialog import BookNoteDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def buecher(tmp_path: Path) -> list[Path]:
    gefunden = []
    for name in ("Band_A", "Band_B", "Band_C"):
        ziel = tmp_path / name
        ziel.mkdir()
        (ziel / "_quarto.yml").write_text("project:\n", encoding="utf-8")
        gefunden.append(ziel)
    return gefunden


@pytest.fixture()
def dialog(qapp, buecher, monkeypatch):
    # Fenstergroesse nicht in die echte Sitzung schreiben.
    import ui_qt.dialogs.book_note_dialog as modul

    monkeypatch.setattr(modul.qt_session, "load_session", lambda *a, **k: {})
    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)
    dlg = BookNoteDialog(books=buecher)
    dlg.show()
    QApplication.processEvents()
    yield dlg
    dlg.close()


# ---------------------------------------------------------------------------
# Die Liste
# ---------------------------------------------------------------------------


def test_alle_buecher_stehen_in_der_liste(dialog, buecher):
    assert dialog.book_list.count() == len(buecher)


def test_ein_buch_mit_notiz_traegt_ein_zeichen(qapp, buecher, monkeypatch):
    import ui_qt.dialogs.book_note_dialog as modul

    monkeypatch.setattr(modul.qt_session, "load_session", lambda *a, **k: {})
    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)
    store.save(buecher[1], "steht schon was drin")
    dlg = BookNoteDialog(books=buecher)
    try:
        texte = [dlg.book_list.item(i).text() for i in range(dlg.book_list.count())]
        assert "📝" in texte[1]
        assert "📝" not in texte[0]
    finally:
        dlg.close()


def test_das_gewuenschte_buch_ist_vorgewaehlt(qapp, buecher, monkeypatch):
    import ui_qt.dialogs.book_note_dialog as modul

    monkeypatch.setattr(modul.qt_session, "load_session", lambda *a, **k: {})
    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)
    dlg = BookNoteDialog(books=buecher, select=buecher[2])
    try:
        assert dlg.book_label.text() == "Band_C"
    finally:
        dlg.close()


def test_ohne_buecher_sagt_das_fenster_es(qapp, monkeypatch):
    import ui_qt.dialogs.book_note_dialog as modul

    monkeypatch.setattr(modul.qt_session, "load_session", lambda *a, **k: {})
    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)
    dlg = BookNoteDialog(books=[])
    try:
        assert "Kein Buchprojekt" in dlg.book_label.text()
        assert dlg.editor.isEnabled() is False
    finally:
        dlg.close()


def test_der_pfad_der_notiz_ist_sichtbar(dialog, buecher):
    """Wer sie ausserhalb oeffnen will, soll nicht suchen muessen."""
    assert str(store.note_path(buecher[0])) == dialog.path_label.text()


# ---------------------------------------------------------------------------
# Nichts geht verloren
# ---------------------------------------------------------------------------


def test_tippen_meldet_offene_arbeit(dialog):
    assert dialog.save_button.isEnabled() is False
    dialog.editor.setPlainText("etwas")
    QApplication.processEvents()
    assert dialog.save_button.isEnabled() is True
    assert dialog.status_label.text() == "ungespeichert"


def test_der_knopf_speichert(dialog, buecher):
    dialog.editor.setPlainText("per Knopf")
    QApplication.processEvents()
    dialog.save_button.click()
    assert store.load(buecher[0]).text.strip() == "per Knopf"
    assert dialog.save_button.isEnabled() is False


def test_ein_buchwechsel_speichert_vorher(dialog, buecher):
    """Ein Listenklick darf keine Arbeit kosten."""
    dialog.editor.setPlainText("beim Wechsel gesichert")
    QApplication.processEvents()
    dialog.book_list.setCurrentRow(1)
    QApplication.processEvents()
    assert store.load(buecher[0]).text.strip() == "beim Wechsel gesichert"


def test_ein_buchwechsel_zeigt_die_andere_notiz(dialog, buecher):
    store.save(buecher[1], "Notiz von B")
    dialog.book_list.setCurrentRow(1)
    QApplication.processEvents()
    assert dialog.editor.toPlainText().strip() == "Notiz von B"
    assert dialog.book_label.text() == "Band_B"


def test_schliessen_speichert(qapp, buecher, monkeypatch):
    import ui_qt.dialogs.book_note_dialog as modul

    monkeypatch.setattr(modul.qt_session, "load_session", lambda *a, **k: {})
    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)
    dlg = BookNoteDialog(books=buecher)
    dlg.show()
    QApplication.processEvents()
    dlg.editor.setPlainText("beim Schliessen gesichert")
    QApplication.processEvents()
    dlg.close()
    assert store.load(buecher[0]).text.strip() == "beim Schliessen gesichert"


def test_zweimal_schliessen_ist_harmlos(qapp, buecher, monkeypatch):
    import ui_qt.dialogs.book_note_dialog as modul

    monkeypatch.setattr(modul.qt_session, "load_session", lambda *a, **k: {})
    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)
    dlg = BookNoteDialog(books=buecher)
    dlg.editor.setPlainText("einmal")
    dlg.reject()
    dlg.close()
    assert store.load(buecher[0]).text.strip() == "einmal"


def test_das_zeichen_erscheint_nach_dem_speichern(dialog):
    assert "📝" not in dialog.book_list.item(0).text()
    dialog.editor.setPlainText("jetzt steht was drin")
    QApplication.processEvents()
    dialog.save_button.click()
    assert "📝" in dialog.book_list.item(0).text()


def test_eine_geleerte_notiz_nimmt_das_zeichen_wieder_weg(dialog, buecher):
    store.save(buecher[0], "erst was")
    dialog.editor.setPlainText("")
    QApplication.processEvents()
    dialog.save_button.click()
    assert "📝" not in dialog.book_list.item(0).text()
    assert not store.has_note(buecher[0])


def test_ein_schreibfehler_wird_gemeldet(dialog, monkeypatch):
    """Still zu scheitern waere hier das Schlimmste -- es ist eine Notiz."""
    from PySide6.QtWidgets import QMessageBox

    gemeldet: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda parent, titel, text, *a, **k: gemeldet.append(text)),
    )
    monkeypatch.setattr(
        store, "save", lambda *a, **k: (_ for _ in ()).throw(OSError("Platte voll"))
    )
    dialog.editor.setPlainText("geht nicht")
    QApplication.processEvents()
    dialog.save_button.click()
    assert gemeldet and "Platte voll" in gemeldet[0]


# ---------------------------------------------------------------------------
# Der Menue-Eintrag
# ---------------------------------------------------------------------------


def test_das_plugin_ist_auffindbar():
    import json

    manifest = json.loads(
        (
            Path(__file__).resolve().parent.parent
            / "plugins"
            / "book_note"
            / "plugin.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["entrypoint"] == "plugins.book_note:run"
    assert "Buchnotiz" in manifest["label"]


def test_das_plugin_meldet_sich_als_verfuegbar():
    from plugins.book_note import is_available

    assert is_available() is True


def test_die_hilfe_grenzt_zum_memoblock_ab():
    """Zwei Notiz-Werkzeuge nebeneinander verlangen ein Wort zur Unterscheidung."""
    import json

    manifest = json.loads(
        (
            Path(__file__).resolve().parent.parent
            / "plugins"
            / "book_note"
            / "plugin.json"
        ).read_text(encoding="utf-8")
    )
    assert "Memo-Block" in manifest["help_text"]
    assert "bookconfig/notiz.md" in manifest["help_text"]
