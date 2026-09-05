"""Der Vorschaulauf des Layout-Editors — Nebenläufigkeit an einer Stelle.

Setzen dauert einige Sekunden (Pandoc, dann LibreOffice) und läuft deshalb in
einem eigenen Thread. Damit hängt an der Vorschau als einzigem Teil des Editors
ein Lebenszyklus: Ein Lauf kann unterwegs sein, während schon der nächste
angefordert wird; er kann fertig werden, nachdem sein Fenster verschwunden ist;
und seine Werkstatt — ein Temp-Verzeichnis mit ``reference.docx``, PDF und
LibreOffice-Profil — muss danach verschwinden.

Vorher lag das verstreut im Dialog: fünf Zustandsfelder (``_worker``,
``_pending_preview``, ``_preview_dir``, ``_preview_timer``, dazu ``_closed``)
zwischen sechs Methoden, mit Invarianten, die nirgends standen. Genau dort saßen
zwei der vier Blocker — der nicht abgewartete Thread und das nicht abgeräumte
Verzeichnis.

Die Arbeitsteilung
------------------
Dieses Modul kennt **keine** Politik: nicht, ob eine Definition gültig ist,
nicht, ob Pandoc fehlt, nicht, was der Benutzer davon zu sehen bekommt. Es
kennt nur den Lauf. Der Dialog entscheidet, *ob* gesetzt wird, und zeigt das
Ergebnis; dieses Modul sorgt dafür, dass immer höchstens ein Lauf unterwegs ist
und keiner sein Fenster überlebt, ohne dass jemand es merkt.

Der Ablauf einer Eingabe:

    Tippen -> schedule()  --(Eingabepause)-->  due
                                                |
                              Dialog prueft und ruft start(definition)
                                                |
                                       busy -> ready | failed
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from tools.doclayout.preview import render_preview
from tools.doclayout.schema import LayoutDefinition, LayoutError

_LOG = logging.getLogger(__name__)

#: Wartezeit nach der letzten Änderung, bevor neu gesetzt wird.
PREVIEW_DELAY_MS = 1200

#: Wie lange beim Schliessen auf einen laufenden Vorschaulauf gewartet wird.
#: Länger zu warten hieße, das Fenster für etwas offenzuhalten, dessen Ergebnis
#: niemand mehr sehen will.
WORKER_WAIT_MS = 3000

#: Vorschaulaeufe, die das Schliessen ihres Fensters ueberdauert haben.
#: Ein noch laufender ``QThread``, dessen letzte Referenz verschwindet, wird
#: mitsamt seinem C++-Objekt abgeraeumt und reisst den Prozess mit ("QThread:
#: Destroyed while thread is still running"). Hier liegt er, bis er von selbst
#: fertig ist, und traegt sich dann aus.
LINGERING_WORKERS: set["PreviewWorker"] = set()


class PreviewWorker(QThread):
    """Setzt eine Definition in einem eigenen Thread.

    Der Lauf ruft Pandoc und LibreOffice auf und dauert einige Sekunden; im
    GUI-Thread würde das Fenster so lange einfrieren.
    """

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, definition: LayoutDefinition, work_dir: Path) -> None:
        super().__init__()
        self._definition = definition
        self._work_dir = work_dir

    def run(self) -> None:  # noqa: D102 - QThread-Vertrag
        try:
            result = render_preview(self._definition, self._work_dir)
        except LayoutError as exc:
            self.failed.emit(str(exc))
        except OSError as exc:
            self.failed.emit(f"Vorschau nicht möglich: {exc}")
        else:
            self.finished_ok.emit(result)


class PreviewRunner(QObject):
    """Hält höchstens einen Vorschaulauf am Leben und räumt hinter ihm auf."""

    #: Die Eingabepause ist vorbei -- der Dialog darf jetzt pruefen und setzen.
    due = Signal()
    #: Ein Lauf hat begonnen.
    busy = Signal()
    #: Ein Lauf ist fertig; das Argument ist ein ``PreviewResult``.
    ready = Signal(object)
    #: Ein Lauf ist gescheitert; das Argument ist der Grund.
    failed = Signal(str)

    def __init__(
        self,
        parent: Optional[QObject] = None,
        *,
        delay_ms: int = PREVIEW_DELAY_MS,
        wait_ms: int = WORKER_WAIT_MS,
    ) -> None:
        super().__init__(parent)
        self._wait_ms = wait_ms
        self._worker: Optional[PreviewWorker] = None
        self._pending = False
        self._released = False
        self._work_dir = Path(tempfile.mkdtemp(prefix="doclayout_preview_"))

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self.due)

    # -- Auskunft ----------------------------------------------------------

    @property
    def work_dir(self) -> Path:
        """Wo gesetzt wird. Existiert, bis :meth:`release` gerufen wurde."""
        return self._work_dir

    @property
    def worker(self) -> Optional[PreviewWorker]:
        """Der laufende Lauf, oder ``None``."""
        return self._worker

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @property
    def released(self) -> bool:
        return self._released

    # -- Anfordern ---------------------------------------------------------

    def schedule(self) -> None:
        """Nach der Eingabepause ``due`` melden. Erneutes Rufen verschiebt sie."""
        if self._released:
            return
        self._timer.start()

    def start(self, definition: LayoutDefinition) -> None:
        """Setzt *definition* -- oder merkt sich, dass nachzuholen ist.

        Läuft schon einer, wird er **nicht** abgebrochen: Ein halb geschriebenes
        Arbeitsverzeichnis wäre der sichere Weg zu einer Vorschau, die weder
        den alten noch den neuen Stand zeigt. Stattdessen wird nachgeholt,
        sobald er fertig ist -- mit dem dann aktuellen Stand, nicht mit diesem.
        """
        if self._released:
            return
        self._timer.stop()
        if self.is_running:
            self._pending = True
            return
        self._pending = False
        self._worker = PreviewWorker(definition, self._work_dir)
        self._worker.finished_ok.connect(self.ready)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._on_finished)
        self.busy.emit()
        self._worker.start()

    def _on_finished(self) -> None:
        self._worker = None
        if self._pending and not self._released:
            self._pending = False
            # Nicht selbst neu starten: Welche Definition jetzt gilt, weiss
            # der Dialog -- seit der Anforderung koennen weitere Eingaben
            # dazugekommen sein.
            self.due.emit()

    # -- Abloesen ----------------------------------------------------------

    def release(self) -> None:
        """Trennt einen laufenden Lauf vom Fenster und räumt die Werkstatt ab.

        Zuerst die Verbindungen: Ein Lauf, der jetzt noch fertig wird, darf
        keine Widgets mehr anfassen, die es gleich nicht mehr gibt.

        Danach wird kurz gewartet. Wer länger braucht, wird nicht abgewürgt,
        sondern in :data:`LINGERING_WORKERS` festgehalten, bis er von selbst
        fertig ist -- ein ``QThread``, dessen letzte Referenz während des Laufs
        verschwindet, reißt den Prozess mit.

        Mehrfach zu rufen ist ausdrücklich erlaubt: Der Dialog wird auf
        mehreren Wegen verlassen, und keiner davon soll wissen müssen, ob ein
        anderer schon da war.
        """
        if self._released:
            return
        self._released = True
        self._pending = False
        self._timer.stop()

        worker = self._worker
        self._worker = None
        if worker is not None:
            for signal in (worker.finished_ok, worker.failed, worker.finished):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    # Nie verbunden oder schon getrennt -- beides ist in Ordnung.
                    pass
            if worker.isRunning():
                LINGERING_WORKERS.add(worker)
                worker.finished.connect(
                    lambda w=worker: LINGERING_WORKERS.discard(w)
                )
                if worker.wait(self._wait_ms):
                    LINGERING_WORKERS.discard(worker)

        shutil.rmtree(self._work_dir, ignore_errors=True)
        _LOG.debug("Vorschau-Werkstatt abgeraeumt: %s", self._work_dir)


__all__ = [
    "LINGERING_WORKERS",
    "PREVIEW_DELAY_MS",
    "WORKER_WAIT_MS",
    "PreviewRunner",
    "PreviewWorker",
]
