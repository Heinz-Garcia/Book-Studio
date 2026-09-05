"""Der Buchsatz des Layout-Editors -- ein Lauf, ein Faden, ein Ergebnis.

Anders als die Vorschau (``doclayout_preview_runner``) hat dieser Lauf keine
Eingabepause und kein Nachholen: Er wird ausdruecklich angefordert, dauert je
nach Umfang Sekunden bis Minuten und passiert genau einmal. Was er mit der
Vorschau teilt, ist der Umgang mit dem Ende: Ein ``QThread``, dessen letzte
Referenz waehrend des Laufs verschwindet, reisst den Prozess mit ("QThread:
Destroyed while thread is still running"). Deshalb dieselbe Wartebank.

Keine Politik hier: ob gesetzt werden darf, entscheidet der Dialog; was der
Benutzer davon sieht, zeigt der Dialog. Dieses Modul kennt nur den Lauf.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.typeset import typeset_book

_LOG = logging.getLogger(__name__)

#: Wie lange beim Schliessen auf einen laufenden Satz gewartet wird. Kurz:
#: Das Ergebnis landet als Datei im Buch und geht nicht verloren, wenn das
#: Fenster vorher zugeht.
WORKER_WAIT_MS = 2000

#: Laeufe, die das Schliessen ihres Fensters ueberdauert haben -- siehe
#: ``doclayout_preview_runner.LINGERING_WORKERS``, gleicher Grund.
LINGERING_WORKERS: set["TypesetWorker"] = set()


class TypesetWorker(QThread):
    """Setzt ein ganzes Buch in einem eigenen Thread."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, definition: LayoutDefinition, book_path: Path) -> None:
        super().__init__()
        self._definition = definition
        self._book_path = book_path

    def run(self) -> None:  # noqa: D102 - QThread-Vertrag
        try:
            result = typeset_book(self._definition, self._book_path)
        except LayoutError as exc:
            self.failed.emit(str(exc))
        except OSError as exc:
            self.failed.emit(f"Buch konnte nicht gesetzt werden: {exc}")
        else:
            self.finished_ok.emit(result)


class TypesetRunner(QObject):
    """Haelt hoechstens einen Buchsatz am Leben."""

    #: Ein Lauf hat begonnen.
    busy = Signal()
    #: Fertig; das Argument ist ein ``TypesetResult``.
    ready = Signal(object)
    #: Gescheitert; das Argument ist der Grund.
    failed = Signal(str)

    def __init__(
        self, parent: Optional[QObject] = None, *, wait_ms: int = WORKER_WAIT_MS
    ) -> None:
        super().__init__(parent)
        self._wait_ms = wait_ms
        self._worker: Optional[TypesetWorker] = None
        self._released = False

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @property
    def released(self) -> bool:
        return self._released

    def start(self, definition: LayoutDefinition, book_path: Path) -> bool:
        """Setzt *book_path*. Liefert ``False``, wenn schon einer laeuft.

        Ein zweiter Lauf wird **nicht** eingereiht: Zwei Saetze desselben Buchs
        schrieben in dieselben Dateien, und wer zuletzt fertig wird, gewinnt --
        ohne dass jemand wuesste, welcher das war.
        """
        if self._released or self.is_running:
            return False
        self._worker = TypesetWorker(definition, Path(book_path))
        self._worker.finished_ok.connect(self.ready)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._on_finished)
        self.busy.emit()
        self._worker.start()
        return True

    def _on_finished(self) -> None:
        self._worker = None

    def release(self) -> None:
        """Trennt einen laufenden Satz vom Fenster. Mehrfach rufen ist erlaubt."""
        if self._released:
            return
        self._released = True
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        for signal in (worker.finished_ok, worker.failed, worker.finished):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                pass
        if worker.isRunning():
            LINGERING_WORKERS.add(worker)
            worker.finished.connect(lambda w=worker: LINGERING_WORKERS.discard(w))
            if worker.wait(self._wait_ms):
                LINGERING_WORKERS.discard(worker)
            else:
                _LOG.debug("Buchsatz laeuft nach dem Schliessen weiter")


__all__ = [
    "LINGERING_WORKERS",
    "WORKER_WAIT_MS",
    "TypesetRunner",
    "TypesetWorker",
]
