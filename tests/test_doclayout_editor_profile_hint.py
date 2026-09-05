"""Der Editor sagt, wo seine Seite vom Druck abweicht — und dass sie ihn nicht steuert.

Zwei Missverständnisse, die dieselbe Wurzel haben: Wer Breite und Ränder
einstellt, nimmt an, damit auch die PDF zu bestimmen. Tatsächlich entsteht die
über das Layout-Profil der Export-Einstellungen; die Einträge dieses Werkzeugs
stehen unter ``format.docx``.

Also sagt das Seiten-Formular, ob es sich mit dem Druckprofil deckt, und der
Bericht nach »Auf Buchprojekt anwenden« sagt dazu, was er **nicht** betrifft.

Die Vorschau wird stillgelegt — geprüft wird die Auskunft, nicht der Satz.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import ui_qt.dialogs.doclayout_editor_dialog as editor_modul  # noqa: E402
from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.profiles import definition_from_profile  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import (  # noqa: E402
    DocLayoutEditorDialog,
)

#: Profil, gegen das die Tests vergleichen. Fest gewählt, damit sie nicht von
#: der Sitzung des Entwicklerrechners abhängen.
PROFIL = "paperback"


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])
@pytest.fixture(autouse=True)
def _keine_echte_sitzung(monkeypatch):
    """Haelt jeden Test dieser Datei von der echten ``session_state.json`` fern.

    Regression aus der Entstehung dieser Datei: Einzelne Tests ersetzten
    ``qt_session.load_session``, um ein Druckprofil vorzugeben -- aber nicht
    ``update_ui_state``. Beim Schliessen legt der Dialog dort seine
    Fenstergroesse ab, und ``update_ui_state`` baut die neue Datei aus dem
    Ergebnis von ``load_session`` auf. Es schrieb also die leere Attrappe in
    die **echte** Sitzungsdatei und loeschte dabei die Export-Einstellungen des
    Benutzers -- Datenverlust durch einen Test.

    Autouse und nicht je Test: Wer hier einen Test dazuschreibt, soll nicht
    daran denken muessen.
    """
    import ui_qt.dialogs.doclayout_editor_dialog as modul

    monkeypatch.setattr(modul.qt_session, "update_ui_state", lambda *a, **k: None)


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    replace(load_layout("IFJN_layout"), name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


@pytest.fixture()
def dialog(qapp, library: Path, monkeypatch):
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_active_layout_profile", lambda self: PROFIL
    )
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    dlg.show()
    QApplication.processEvents()
    yield dlg
    dlg._session.mark_clean()
    dlg.close()


def _seite_waehlen(dlg: DocLayoutEditorDialog) -> None:
    for row in range(dlg.nav_list.count()):
        data = dlg.nav_list.item(row).data(Qt.ItemDataRole.UserRole)
        if data and data[0] == "section" and "Seite" in data[1]:
            dlg.nav_list.setCurrentRow(row)
            QApplication.processEvents()
            return
    raise AssertionError("Abschnitt »Seite und Ränder« nicht gefunden")


def _text(dlg: DocLayoutEditorDialog) -> str:
    return re.sub("<[^>]+>", " ", dlg.page_form.profile_match.text())


# ---------------------------------------------------------------------------
# Die Anzeige
# ---------------------------------------------------------------------------


def test_der_abgleich_erscheint_beim_oeffnen_der_seite(dialog):
    _seite_waehlen(dialog)
    assert dialog.page_form.profile_match.isVisible()


def test_er_nennt_das_profil_und_die_abweichenden_masse(dialog):
    _seite_waehlen(dialog)
    text = _text(dialog)
    assert "Paperback" in text
    assert "Breite" in text
    assert "210" in text and "135" in text, text


def test_er_sagt_dass_die_pdf_davon_unberuehrt_bleibt(dialog):
    """Das eigentliche Missverstaendnis -- es steht ausdruecklich da."""
    _seite_waehlen(dialog)
    text = _text(dialog)
    assert "Word-Fassung" in text
    assert "Layout-Profil" in text


def test_uebernehmen_bringt_die_meldung_zur_deckung(dialog):
    _seite_waehlen(dialog)
    index = dialog.page_form.profile_combo.findData(PROFIL)
    assert index >= 0
    dialog.page_form.profile_combo.setCurrentIndex(index)
    dialog._apply_profile()
    QApplication.processEvents()
    assert "Deckt sich" in _text(dialog)


def test_die_meldung_folgt_der_eingabe(dialog):
    """Wer an der Breite dreht, sieht sofort, ob er sich entfernt."""
    _seite_waehlen(dialog)
    index = dialog.page_form.profile_combo.findData(PROFIL)
    dialog.page_form.profile_combo.setCurrentIndex(index)
    dialog._apply_profile()
    QApplication.processEvents()
    assert "Deckt sich" in _text(dialog)

    dialog.page_form.width.setValue(dialog.page_form.width.value() + 20.0)
    QApplication.processEvents()
    assert "Weicht" in _text(dialog)
    assert "Breite" in _text(dialog)


def test_ein_unbekanntes_profil_behauptet_nichts(dialog, monkeypatch):
    """Lieber keine Auskunft als eine falsche ueber den Druck."""
    _seite_waehlen(dialog)
    assert dialog.page_form.profile_match.isVisible(), "Vorbedingung: es stand etwas da"

    monkeypatch.setattr(
        DocLayoutEditorDialog, "_active_layout_profile", lambda self: "gibt_es_nicht"
    )
    # Direkt aufgerufen: ``setCurrentRow`` auf dieselbe Zeile loest kein
    # Signal aus, der Abschnitt wuerde also gar nicht neu aufgebaut.
    dialog._refresh_profile_comparison()
    QApplication.processEvents()
    assert not dialog.page_form.profile_match.isVisible()


# ---------------------------------------------------------------------------
# Woher das Profil kommt
# ---------------------------------------------------------------------------


def test_das_profil_kommt_aus_den_export_einstellungen(qapp, library, monkeypatch):
    """Dieselbe Quelle wie ``export_manager`` -- sonst waere die Aussage falsch."""
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )
    monkeypatch.setattr(
        editor_modul.qt_session,
        "load_session",
        lambda *a, **k: {"export_options": {"layout_profile": "paperback-bleed"}},
    )
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    try:
        assert dlg._active_layout_profile() == "paperback-bleed"
    finally:
        dlg._session.mark_clean()
        dlg.close()


def test_ohne_sitzung_gilt_dieselbe_vorgabe_wie_im_export(
    qapp, library, monkeypatch
):
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )
    monkeypatch.setattr(
        editor_modul.qt_session, "load_session", lambda *a, **k: {}
    )
    monkeypatch.setattr(
        editor_modul, "_FALLBACK_LAYOUT_PROFILE", "taschenbuch-bod", raising=False
    )
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    try:
        # Entweder die App-Vorgabe oder der eingebaute Standard -- beides ist
        # eine gueltige Antwort, "nichts" waere es nicht.
        assert dlg._active_layout_profile()
    finally:
        dlg._session.mark_clean()
        dlg.close()


def test_eine_kaputte_sitzung_wirft_nicht(qapp, library, monkeypatch):
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )

    def kaputt(*a, **k):
        raise OSError("session_state.json unlesbar")

    monkeypatch.setattr(editor_modul.qt_session, "load_session", kaputt)
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    try:
        assert dlg._active_layout_profile() == editor_modul._FALLBACK_LAYOUT_PROFILE
    finally:
        dlg._session.mark_clean()
        dlg.close()


# ---------------------------------------------------------------------------
# Der Bericht nach dem Anwenden
# ---------------------------------------------------------------------------


class _Ergebnis:
    def __init__(self, text: str = "Layout angewandt auf: X") -> None:
        self._text = text

    def summary(self) -> str:
        return self._text


def test_der_bericht_sagt_dass_es_die_word_fassung_betrifft(dialog):
    """Den genauen Wortlaut prueft ``test_doclayout_scope_notice``."""
    from tools.doclayout import DOCX_ONLY_NOTICE

    bericht = dialog._apply_report(_Ergebnis())
    assert "Layout angewandt auf: X" in bericht
    assert DOCX_ONLY_NOTICE in bericht


def test_bei_abweichung_nennt_der_bericht_das_druckprofil(dialog):
    bericht = dialog._apply_report(_Ergebnis())
    assert "Paperback" in bericht
    assert "Breite" in bericht


def test_bei_deckung_bleibt_der_bericht_knapp(dialog):
    """Ohne Abweichung keine Aufzaehlung -- der Kernsatz bleibt trotzdem."""
    from tools.doclayout import DOCX_ONLY_NOTICE

    dialog._session.replace_definition(
        definition_from_profile(dialog._definition, PROFIL)
    )
    bericht = dialog._apply_report(_Ergebnis())
    assert DOCX_ONLY_NOTICE in bericht
    assert "Breite" not in bericht
