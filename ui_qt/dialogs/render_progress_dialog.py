"""Der Fortschritt eines Renders -- sichtbar, statt nur im Protokoll.

Bisher lief ein Render stumm: eine Statuszeile, dann Minuten, in denen nichts
darauf hindeutete, ob noch gearbeitet wird. Wer auf ein Buch mit tausend Seiten
wartet, hat dann zwei schlechte Moeglichkeiten -- weiterwarten oder abschiessen.

Drei Entscheidungen, die hier drinstecken:

**Modal, aber nicht verschlossen.** Der Dialog haelt das Hauptfenster an, damit
niemand mitten im Lauf die Struktur umbaut. Er hat aber zwei Ausgaenge:
*Ausblenden* laesst den Lauf weiterlaufen und gibt das Fenster frei, *Abbrechen*
beendet ihn wirklich. Ein modaler Dialog ohne Ausgang waere ein Gefaengnis --
gerade bei etwas, das auch haengen kann.

**Der Balken luegt nicht.** Er zeigt echten Fortschritt, wo Quarto welchen
meldet (``[3/57] kapitel.md``), und feste Marken fuer die Phasen davor und
danach. 100 % gibt es erst, wenn wirklich Schluss ist -- siehe
``services.render_progress``.

**Die letzte Zeile steht darunter.** Nicht das ganze Protokoll: Wer zusieht,
will wissen, dass es weitergeht, und nicht lesen. Das Protokoll bleibt, wo es
war (F4).
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.render_progress import ProgressStep

#: Wie oft die verstrichene Zeit nachgezogen wird.
_TICK_MS = 500


class RenderProgressDialog(QDialog):
    """Zeigt den Fortschritt eines laufenden Renders."""

    #: Der Benutzer hat abgebrochen. Der Aufrufer beendet den Lauf.
    cancelled = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        title: str = "Buch wird gerendert",
        subject: str = "",
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        # Kein Schliessknopf im Rahmen: Er saehe aus wie "Abbrechen", waere aber
        # nur "Ausblenden" -- zwei sehr verschiedene Dinge, und der Unterschied
        # kostet hier eine Stunde Rechenzeit.
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._cancelled = False
        self._finished = False
        self._started_at = time.monotonic()
        if on_cancel is not None:
            self.cancelled.connect(on_cancel)

        aussen = QVBoxLayout(self)

        self.subject_label = QLabel(subject or "")
        self.subject_label.setWordWrap(True)
        if subject:
            aussen.addWidget(self.subject_label)
        else:
            self.subject_label.hide()

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        aussen.addWidget(self.bar)

        self.step_label = QLabel("Render startet ...")
        self.step_label.setWordWrap(True)
        aussen.addWidget(self.step_label)

        self.elapsed_label = QLabel("0:00")
        self.elapsed_label.setObjectName("RenderElapsed")
        aussen.addWidget(self.elapsed_label)

        knoepfe = QHBoxLayout()
        knoepfe.addStretch(1)
        self.hide_button = QPushButton("Ausblenden")
        self.hide_button.setToolTip(
            "Schliesst nur dieses Fenster. Der Render laeuft weiter; "
            "das Protokoll (F4) zeigt ihn."
        )
        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.setToolTip("Beendet den laufenden Render wirklich.")
        knoepfe.addWidget(self.hide_button)
        knoepfe.addWidget(self.cancel_button)
        aussen.addLayout(knoepfe)

        self.hide_button.clicked.connect(self.hide)
        self.cancel_button.clicked.connect(self._on_cancel)

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # -- Auskunft ----------------------------------------------------------

    @property
    def was_cancelled(self) -> bool:
        """Ob der Benutzer abgebrochen hat -- die Frage, die der Lauf stellt."""
        return self._cancelled

    # -- Anzeige -----------------------------------------------------------

    def apply_step(self, step: ProgressStep) -> None:
        """Uebernimmt einen Stand aus :class:`services.render_progress.RenderProgress`."""
        if self._finished:
            return
        self.bar.setValue(max(0, min(100, step.percent)))
        self.step_label.setText(step.label)

    def finish(self, *, ok: bool = True, label: str = "") -> None:
        """Schliesst den Lauf ab und beendet den Dialog.

        Auch im Fehlerfall: Die Meldung gehoert ins Protokoll und in einen
        eigenen Kasten, nicht in einen Fortschrittsbalken, den niemand mehr
        ansieht.
        """
        self._finished = True
        self._timer.stop()
        if ok:
            self.bar.setValue(100)
        self.step_label.setText(label or ("Fertig" if ok else "Abgebrochen"))
        self.accept() if ok else self.reject()

    # -- Innenleben --------------------------------------------------------

    def _tick(self) -> None:
        vergangen = int(time.monotonic() - self._started_at)
        self.elapsed_label.setText(f"{vergangen // 60}:{vergangen % 60:02d}")

    def _on_cancel(self) -> None:
        """Einmal ist genug -- ein zweiter Klick soll nichts mehr ausloesen."""
        if self._cancelled:
            return
        self._cancelled = True
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Wird abgebrochen ...")
        self.step_label.setText("Abbruch angefordert -- der Lauf wird beendet.")
        self.cancelled.emit()

    def reject(self) -> None:  # noqa: D102 - QDialog-Vertrag
        """Esc soll nicht heimlich abbrechen.

        Der Tastendruck fuehlt sich an wie "Fenster zu", nicht wie "Lauf
        beenden". Solange gearbeitet wird, wird er deshalb als *Ausblenden*
        gedeutet -- der Weg zum echten Abbruch steht als Knopf daneben.
        """
        if not self._finished:
            self.hide()
            return
        super().reject()


__all__ = ["RenderProgressDialog"]
