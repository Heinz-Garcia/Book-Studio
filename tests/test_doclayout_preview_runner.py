"""Der Vorschaulauf als eigene Einheit — ohne Dialog, ohne Pandoc.

Vorher lag dieser Lebenszyklus verstreut im Editor: fünf Zustandsfelder
zwischen sechs Methoden, mit Invarianten, die nirgends standen. Zwei der vier
Blocker saßen genau dort. Jetzt hat er einen eigenen Vertrag, und der lässt
sich für sich prüfen.

``render_preview`` wird ersetzt: Geprüft wird die Verwaltung der Läufe, nicht
das Setzen.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import ui_qt.dialogs.doclayout_preview_runner as runner_modul  # noqa: E402
from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.preview import PreviewResult  # noqa: E402
from tools.doclayout.schema import LayoutError  # noqa: E402
from ui_qt.dialogs.doclayout_preview_runner import PreviewRunner  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def definition():
    return load_layout("IFJN_layout")


@pytest.fixture()
def runner(qapp):
    """Kurze Eingabepause und kurze Wartezeit -- Tests sollen nicht bummeln."""
    r = PreviewRunner(delay_ms=30, wait_ms=2000)
    yield r
    r.release()


def _ergebnis(work_dir) -> PreviewResult:
    docx = Path(work_dir) / "vorschau.docx"
    docx.parent.mkdir(parents=True, exist_ok=True)
    docx.write_bytes(b"docx")
    return PreviewResult(docx=docx, pdf=None, markdown=docx, note="")


def _sofort(monkeypatch):
    monkeypatch.setattr(
        runner_modul, "render_preview", lambda d, w, **k: _ergebnis(w)
    )


def _langsam(monkeypatch, sekunden: float = 0.4):
    def langsam(d, w, **k):
        time.sleep(sekunden)
        return _ergebnis(w)

    monkeypatch.setattr(runner_modul, "render_preview", langsam)


def _warte_auf(bedingung, grenze: float = 5.0) -> bool:
    """Ereignisschleife drehen, bis *bedingung* wahr ist."""
    ende = time.monotonic() + grenze
    while time.monotonic() < ende:
        QApplication.processEvents()
        if bedingung():
            return True
        time.sleep(0.01)
    return bedingung()


# ---------------------------------------------------------------------------
# Werkstatt
# ---------------------------------------------------------------------------


def test_die_werkstatt_entsteht_beim_anlegen(runner):
    assert runner.work_dir.is_dir()


def test_release_raeumt_die_werkstatt_ab(qapp):
    r = PreviewRunner(delay_ms=10)
    werkstatt = r.work_dir
    r.release()
    assert not werkstatt.exists()


def test_release_darf_mehrfach_gerufen_werden(qapp):
    """Der Dialog wird auf mehreren Wegen verlassen; keiner soll das wissen."""
    r = PreviewRunner(delay_ms=10)
    r.release()
    r.release()
    assert r.released is True


def test_nach_release_wird_nichts_mehr_angefordert(qapp, definition, monkeypatch):
    _sofort(monkeypatch)
    r = PreviewRunner(delay_ms=10)
    r.release()
    r.schedule()
    r.start(definition)
    assert r.worker is None


# ---------------------------------------------------------------------------
# Eingabepause
# ---------------------------------------------------------------------------


def test_schedule_meldet_sich_nach_der_pause(runner):
    faellig: list[int] = []
    runner.due.connect(lambda: faellig.append(1))
    runner.schedule()
    assert _warte_auf(lambda: faellig), "»due« kam nicht"


def test_erneutes_schedule_verschiebt_die_pause(runner):
    """Wer weitertippt, soll nicht mitten im Wort gesetzt bekommen."""
    faellig: list[int] = []
    runner.due.connect(lambda: faellig.append(1))
    for _ in range(5):
        runner.schedule()
        QApplication.processEvents()
        time.sleep(0.01)
    assert not faellig, "waehrend des Tippens haette nichts faellig sein duerfen"
    assert _warte_auf(lambda: faellig)
    assert len(faellig) == 1


def test_start_beendet_eine_laufende_pause(runner, definition, monkeypatch):
    """Sonst liefe nach dem Knopfdruck gleich noch ein zweiter Lauf an."""
    _sofort(monkeypatch)
    faellig: list[int] = []
    runner.due.connect(lambda: faellig.append(1))
    runner.schedule()
    runner.start(definition)
    assert _warte_auf(lambda: not runner.is_running)
    time.sleep(0.1)
    QApplication.processEvents()
    assert faellig == []


# ---------------------------------------------------------------------------
# Ein Lauf nach dem anderen
# ---------------------------------------------------------------------------


def test_ein_lauf_meldet_busy_und_ready(runner, definition, monkeypatch):
    _sofort(monkeypatch)
    verlauf: list[str] = []
    runner.busy.connect(lambda: verlauf.append("busy"))
    runner.ready.connect(lambda _r: verlauf.append("ready"))
    runner.start(definition)
    assert _warte_auf(lambda: "ready" in verlauf)
    assert verlauf == ["busy", "ready"]


def test_ein_fehler_meldet_sich_als_solcher(runner, definition, monkeypatch):
    def kaputt(d, w, **k):
        raise LayoutError("geht nicht")

    monkeypatch.setattr(runner_modul, "render_preview", kaputt)
    gruende: list[str] = []
    runner.failed.connect(gruende.append)
    runner.start(definition)
    assert _warte_auf(lambda: gruende)
    assert gruende == ["geht nicht"]


def test_ein_zweiter_lauf_woehrend_des_ersten_wird_nachgeholt(
    runner, definition, monkeypatch
):
    """Nicht abbrechen: Ein halb geschriebenes Verzeichnis zeigte weder alt noch neu."""
    _langsam(monkeypatch, 0.3)
    faellig: list[int] = []
    runner.due.connect(lambda: faellig.append(1))

    runner.start(definition)
    erster = runner.worker
    runner.start(definition)
    assert runner.worker is erster, "der erste Lauf wurde abgebrochen"

    assert _warte_auf(lambda: faellig), "das Nachholen wurde nicht gemeldet"


def test_ohne_nachholen_kommt_kein_zweites_due(runner, definition, monkeypatch):
    _sofort(monkeypatch)
    faellig: list[int] = []
    runner.due.connect(lambda: faellig.append(1))
    runner.start(definition)
    assert _warte_auf(lambda: not runner.is_running)
    time.sleep(0.1)
    QApplication.processEvents()
    assert faellig == []


def test_nach_dem_lauf_haengt_kein_worker_mehr(runner, definition, monkeypatch):
    _sofort(monkeypatch)
    runner.start(definition)
    assert _warte_auf(lambda: runner.worker is None)
    assert runner.is_running is False


# ---------------------------------------------------------------------------
# Abloesen eines laufenden Laufs
# ---------------------------------------------------------------------------


def test_ein_laufender_lauf_wird_festgehalten_statt_abgeraeumt(
    qapp, definition, monkeypatch
):
    _langsam(monkeypatch, 0.5)
    r = PreviewRunner(delay_ms=10, wait_ms=50)
    r.start(definition)
    laeuft = r.worker
    assert laeuft is not None and laeuft.isRunning()

    r.release()

    assert r.worker is None
    assert laeuft in runner_modul.LINGERING_WORKERS
    assert _warte_auf(lambda: laeuft not in runner_modul.LINGERING_WORKERS)


def test_ein_rechtzeitig_fertiger_lauf_wird_nicht_festgehalten(
    qapp, definition, monkeypatch
):
    _langsam(monkeypatch, 0.1)
    r = PreviewRunner(delay_ms=10, wait_ms=4000)
    r.start(definition)
    laeuft = r.worker
    r.release()
    assert laeuft not in runner_modul.LINGERING_WORKERS


def test_ein_abgeloester_lauf_meldet_nichts_mehr(qapp, definition, monkeypatch):
    _langsam(monkeypatch, 0.3)
    r = PreviewRunner(delay_ms=10, wait_ms=50)
    angekommen: list[object] = []
    r.ready.connect(angekommen.append)
    r.start(definition)
    laeuft = r.worker

    r.release()
    assert laeuft is not None
    laeuft.wait(5000)
    QApplication.processEvents()

    assert angekommen == [], "das Ergebnis erreichte einen abgeloesten Empfaenger"
