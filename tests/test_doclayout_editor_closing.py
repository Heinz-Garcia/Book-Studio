"""Alle Wege aus dem Editor muessen dasselbe tun.

Regression: Das Aufraeumen stand nur in ``closeEvent`` -- und das laeuft beim
Schliessen-Knopf und bei Esc gar nicht, denn beide rufen ``reject()``. Also
blieb bei jedem Besuch ein Temp-Ordner mit ``reference.docx``, PDF und
LibreOffice-Profil liegen, und ein noch laufender Vorschau-Thread verlor sein
Fenster unter sich.

Umgekehrt lief das Fensterkreuz durch ``closeEvent`` **und** das darin
aufgerufene ``reject()`` -- die Rueckfrage nach ungespeicherter Arbeit stand
zweimal da.

Die Vorschau wird stillgelegt: geprueft wird das Verlassen des Fensters, nicht
der Satz. Der eine Test, der einen laufenden Lauf braucht, bringt seinen
eigenen mit.
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import ui_qt.dialogs.doclayout_editor_dialog as editor_modul  # noqa: E402
import ui_qt.dialogs.doclayout_preview_runner as runner_modul  # noqa: E402
from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.preview import PreviewResult  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import (  # noqa: E402
    DocLayoutEditorDialog,
)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    replace(load_layout("IFJN_layout"), name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


@pytest.fixture()
def ohne_vorschau(monkeypatch):
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )


@pytest.fixture()
def fragen(monkeypatch) -> list[str]:
    """Zaehlt die Rueckfragen und verwirft die Aenderungen."""
    gesehen: list[str] = []

    def question(parent, title, text, *args, **kwargs):
        gesehen.append(text)
        return QMessageBox.StandardButton.Discard

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return gesehen


def _offen(library: Path) -> DocLayoutEditorDialog:
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    dlg.show()
    QApplication.processEvents()
    return dlg


# ---------------------------------------------------------------------------
# Aufraeumen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("weg", ["reject", "close", "accept"])
def test_jeder_weg_raeumt_die_werkstatt_ab(qapp, library, ohne_vorschau, weg):
    dlg = _offen(library)
    werkstatt = dlg._runner.work_dir
    assert werkstatt.is_dir(), "Vorbedingung: die Werkstatt gibt es"

    getattr(dlg, weg)()
    QApplication.processEvents()

    assert not werkstatt.exists(), f"{weg}() liess den Temp-Ordner liegen"


@pytest.mark.parametrize("weg", ["reject", "close"])
def test_ungespeicherte_arbeit_wird_genau_einmal_erfragt(
    qapp, library, ohne_vorschau, fragen, weg
):
    dlg = _offen(library)
    dlg._session.mark_dirty()

    getattr(dlg, weg)()
    QApplication.processEvents()

    assert len(fragen) == 1, f"{weg}() fragte {len(fragen)}-mal"


def test_abbrechen_haelt_das_fenster_offen_und_raeumt_nicht(
    qapp, library, ohne_vorschau, monkeypatch
):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    dlg = _offen(library)
    werkstatt = dlg._runner.work_dir
    dlg._session.mark_dirty()

    dlg.reject()
    QApplication.processEvents()

    assert dlg.isVisible(), "das Fenster haette offen bleiben muessen"
    assert werkstatt.is_dir(), "abgebrochen heisst: nichts angefasst"
    assert dlg._dirty is True

    dlg._session.mark_clean()
    dlg.close()


def test_ohne_aenderungen_wird_nichts_gefragt(qapp, library, ohne_vorschau, fragen):
    dlg = _offen(library)
    dlg.reject()
    assert fragen == []


def test_zweimal_schliessen_raeumt_nur_einmal(qapp, library, ohne_vorschau, fragen):
    """``close()`` nach ``reject()`` ist der uebliche Ablauf im Testcode."""
    dlg = _offen(library)
    dlg._session.mark_dirty()
    dlg.reject()
    dlg.close()
    QApplication.processEvents()
    assert len(fragen) == 1


def test_speichern_beim_schliessen_schreibt_die_datei(
    qapp, library, ohne_vorschau, monkeypatch
):
    """Der Weg »Speichern« aus der Rueckfrage muss weiter funktionieren."""
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save),
    )
    dlg = _offen(library)
    ziel = sorted(dlg._definition.styles)[0]
    dlg._session.replace_definition(
        replace(
            dlg._definition,
            styles={
                **dlg._definition.styles,
                ziel: replace(dlg._definition.styles[ziel], size_pt=17.0),
            },
        )
    )

    dlg.reject()
    QApplication.processEvents()

    assert load_layout("Probe", library).styles[ziel].size_pt == 17.0


# ---------------------------------------------------------------------------
# Der laufende Vorschaulauf
# ---------------------------------------------------------------------------


def test_ein_laufender_vorschaulauf_wird_beim_schliessen_abgeloest(
    qapp, library, monkeypatch
):
    """Er darf weder abgewuergt noch mit dem Fenster zusammen abgeraeumt werden.

    Ein ``QThread``, dessen letzte Referenz waehrend des Laufs verschwindet,
    reisst den Prozess mit. Deshalb wird er abgekoppelt und -- falls er noch
    laeuft -- festgehalten, bis er von selbst fertig ist.
    """

    def langsam(definition, work_dir, **kwargs):
        time.sleep(0.4)
        docx = Path(work_dir) / "vorschau.docx"
        docx.parent.mkdir(parents=True, exist_ok=True)
        docx.write_bytes(b"docx")
        return PreviewResult(docx=docx, pdf=None, markdown=docx, note="")

    monkeypatch.setattr(runner_modul, "render_preview", langsam)
    dlg = _offen(library)
    QApplication.processEvents()
    assert dlg._runner.worker is not None and dlg._runner.worker.isRunning()
    laeuft = dlg._runner.worker

    dlg.close()
    QApplication.processEvents()

    assert dlg._runner.worker is None, "der Lauf haengt noch am Fenster"
    assert dlg._closed is True
    # Entweder er war rechtzeitig fertig, oder er wird festgehalten -- nur
    # nicht beides nicht.
    assert not laeuft.isRunning() or laeuft in runner_modul.LINGERING_WORKERS
    laeuft.wait(5000)


def test_ein_abgeloester_lauf_traegt_sich_wieder_aus(qapp, library, monkeypatch):
    """Sonst waere die Liste der Nachzuegler ein Leck mit anderem Namen."""

    def langsam(definition, work_dir, **kwargs):
        time.sleep(0.3)
        docx = Path(work_dir) / "vorschau.docx"
        docx.parent.mkdir(parents=True, exist_ok=True)
        docx.write_bytes(b"docx")
        return PreviewResult(docx=docx, pdf=None, markdown=docx, note="")

    monkeypatch.setattr(runner_modul, "render_preview", langsam)
    dlg = _offen(library)
    QApplication.processEvents()
    laeuft = dlg._runner.worker
    assert laeuft is not None

    dlg.close()
    laeuft.wait(5000)
    QApplication.processEvents()

    assert laeuft not in runner_modul.LINGERING_WORKERS


def test_ein_fertig_gewordener_lauf_meldet_sich_nicht_mehr_am_fenster(
    qapp, library, monkeypatch
):
    """Nach dem Abloesen darf kein Ergebnis mehr an tote Widgets gehen.

    Abgefangen wird an der Anzeige und nicht an ``_on_preview_ready``: Die
    Verbindung entsteht beim Start des Laufs und zeigt auf die damals
    gebundene Methode -- sie spaeter am Objekt zu ersetzen, aendert nichts und
    ergaebe einen Test, der auch ohne die Korrektur gruen waere.
    """
    angekommen: list[object] = []
    monkeypatch.setattr(
        editor_modul._PreviewPane,
        "show_result",
        lambda self, result: angekommen.append(result),
    )

    def langsam(definition, work_dir, **kwargs):
        time.sleep(0.8)
        docx = Path(work_dir) / "vorschau.docx"
        docx.parent.mkdir(parents=True, exist_ok=True)
        docx.write_bytes(b"docx")
        return PreviewResult(docx=docx, pdf=None, markdown=docx, note="")

    monkeypatch.setattr(runner_modul, "render_preview", langsam)
    dlg = _offen(library)
    laeuft = dlg._runner.worker
    assert laeuft is not None and laeuft.isRunning()

    dlg.close()
    laeuft.wait(5000)
    QApplication.processEvents()

    assert angekommen == [], "das Ergebnis erreichte ein bereits geschlossenes Fenster"
