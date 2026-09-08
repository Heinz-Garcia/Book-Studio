"""Qt-Dialog: Satzprüfung und Regelkreis aus der Oberfläche starten.

Beide Werkzeuge sind eigenständige Kommandozeilenprogramme
(``tools/satzpruefer``, ``tools/satzregelkreis``) und bleiben es. Dieser
Dialog sammelt nur die Parameter ein, startet den Prozess und zeigt dessen
Ausgabe mit — er enthält keine Satzlogik. Damit gilt weiter: Wer kein
Book Studio hat, kann die Werkzeuge trotzdem benutzen, und ein Fehler in der
Oberfläche kann kein Buch beschädigen.

Warum ``QProcess`` und kein Thread: Der Regelkreis rendert das Buch mehrfach
und läuft Minuten. Ein Unterprozess lässt sich abbrechen, blockiert die
Oberfläche nicht und liefert seine Ausgabe zeilenweise, während er läuft --
bei einem Lauf, der drei Minuten dauert, ist das der Unterschied zwischen
"hängt" und "arbeitet".
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QProcess, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui_qt.widgets.help_bar import HelpBar

#: Wurzel des Repos -- von hier aus laufen die ``python -m tools.*``-Aufrufe.
_REPO_ROOT = Path(__file__).resolve().parents[2]

_HINWEIS_REGELKREIS = (
    "Der Regelkreis rendert das Buch mehrfach (rund eine halbe Minute je "
    "Durchgang) und schreibt dabei Schriftgrößen in die Formatvorlage "
    "typst-show.typ des Buches — in einen markierten Block, den ein "
    "Folgelauf ersetzt.\n\nDas Manuskript wird nicht angefasst.\n\nStarten?"
)


class SatzWerkzeugeQtDialog(QDialog):
    """Ein Fenster, zwei Werkzeuge, eine gemeinsame Ausgabe."""

    def __init__(self, parent: Optional[QWidget], *, buch: Path,
                 pdf: Optional[Path], layout_profil: Optional[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Satzprüfung & Regelkreis")
        self.resize(860, 620)
        self._buch = buch
        self._pdf = pdf
        self._prozess: Optional[QProcess] = None
        self._bericht: Optional[Path] = None

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "satz_werkzeuge")
        layout.addWidget(QLabel(f"<b>Buch:</b> {buch.name}"))
        self._pdf_label = QLabel()
        self._pdf_label.setWordWrap(True)
        layout.addWidget(self._pdf_label)
        self._zeige_pdf()

        layout.addWidget(self._baue_pruefung())
        layout.addWidget(self._baue_regelkreis(layout_profil))

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setPlaceholderText("Die Ausgabe des Werkzeugs erscheint hier.")
        layout.addWidget(self.log, 1)

        fuss = QHBoxLayout()
        self.btn_abbrechen = QPushButton("Lauf abbrechen")
        self.btn_abbrechen.setEnabled(False)
        self.btn_abbrechen.clicked.connect(self._abbrechen)
        fuss.addWidget(self.btn_abbrechen)
        self.btn_bericht = QPushButton("Bericht öffnen")
        self.btn_bericht.setEnabled(False)
        self.btn_bericht.clicked.connect(self._bericht_oeffnen)
        fuss.addWidget(self.btn_bericht)
        fuss.addStretch(1)
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.reject)
        fuss.addWidget(schliessen)
        layout.addLayout(fuss)

    # ── Aufbau ──────────────────────────────────────────────────────────

    def _baue_pruefung(self) -> QGroupBox:
        box = QGroupBox("Satzprüfung — misst ein fertiges PDF, ändert nichts")
        zeile = QHBoxLayout(box)
        self.btn_pruefen = QPushButton("🔍 Prüfen")
        self.btn_pruefen.clicked.connect(self._pruefen)
        zeile.addWidget(self.btn_pruefen)
        andere = QPushButton("Anderes PDF…")
        andere.clicked.connect(self._pdf_waehlen)
        zeile.addWidget(andere)
        zeile.addStretch(1)
        return box

    def _baue_regelkreis(self, layout_profil: Optional[str]) -> QGroupBox:
        from tools.layout_profiles import DEFAULT_LAYOUT_PROFILE_ID, LAYOUT_PROFILES

        box = QGroupBox(
            "Regelkreis — rendert wiederholt und passt die Formatvorlage an"
        )
        aussen = QVBoxLayout(box)
        zeile = QHBoxLayout()
        zeile.addWidget(QLabel("Layout-Profil:"))
        self.profil = QComboBox()
        for profil in LAYOUT_PROFILES:
            self.profil.addItem(profil.label, profil.id)
        gewuenscht = layout_profil or DEFAULT_LAYOUT_PROFILE_ID
        treffer = self.profil.findData(gewuenscht)
        if treffer >= 0:
            self.profil.setCurrentIndex(treffer)
        zeile.addWidget(self.profil, 1)

        zeile.addWidget(QLabel("max. Iterationen:"))
        self.iterationen = QSpinBox()
        self.iterationen.setRange(1, 20)
        self.iterationen.setValue(5)
        zeile.addWidget(self.iterationen)
        aussen.addLayout(zeile)

        zeile2 = QHBoxLayout()
        self.btn_regelkreis = QPushButton("⚙ Regelkreis starten")
        self.btn_regelkreis.clicked.connect(self._regelkreis)
        zeile2.addWidget(self.btn_regelkreis)
        grenzen = QPushButton("Grenzwerte…")
        grenzen.setToolTip(
            "Wählt und öffnet grenzen.toml (Regelkreis) oder schwellen.toml "
            "(Satzprüfung)."
        )
        grenzen.clicked.connect(self._grenzen_oeffnen)
        zeile2.addWidget(grenzen)
        zeile2.addStretch(1)
        aussen.addLayout(zeile2)
        return box

    # ── Läufe ───────────────────────────────────────────────────────────

    def _pruefen(self) -> None:
        if self._pdf is None or not self._pdf.is_file():
            QMessageBox.information(
                self, "Satzprüfung",
                "Kein gerendertes PDF gefunden. Zuerst exportieren (F5) oder "
                "über „Anderes PDF…“ eines auswählen.",
            )
            return
        self._bericht = self._pdf.with_name(self._pdf.stem + "_satzpruefung.md")
        self._starte(["-m", "tools.satzpruefer", str(self._pdf)], "Satzprüfung")

    def _regelkreis(self) -> None:
        if QMessageBox.question(
            self, "Regelkreis starten", _HINWEIS_REGELKREIS,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        # Die CLI uebergibt "export/satz_regelkreis" OHNE Endung an
        # bericht.schreibe(); daraus werden .md und .json.
        self._bericht = self._buch / "export" / "satz_regelkreis.md"
        self._starte(
            ["-m", "tools.satzregelkreis", str(self._buch),
             "--layout-profil", str(self.profil.currentData()),
             "--max-iterationen", str(self.iterationen.value())],
            "Regelkreis",
        )

    def _starte(self, argumente: list[str], titel: str) -> None:
        if self._prozess is not None:
            return  # läuft schon; die Knöpfe sind ohnehin gesperrt
        self.log.clear()
        self.log.appendPlainText(f"$ python {' '.join(argumente)}\n")
        prozess = QProcess(self)
        prozess.setWorkingDirectory(str(_REPO_ROOT))
        prozess.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        prozess.readyReadStandardOutput.connect(self._ausgabe_lesen)
        prozess.finished.connect(lambda code, _status: self._fertig(code, titel))
        prozess.errorOccurred.connect(self._prozessfehler)
        self._prozess = prozess
        self._sperren(True)
        prozess.start(sys.executable, argumente)

    def _ausgabe_lesen(self) -> None:
        if self._prozess is None:
            return
        roh = bytes(self._prozess.readAllStandardOutput())
        text = roh.decode("utf-8", errors="replace").rstrip("\n")
        if text:
            self.log.appendPlainText(text)
            leiste = self.log.verticalScrollBar()
            leiste.setValue(leiste.maximum())

    def _fertig(self, code: int, titel: str) -> None:
        self._prozess = None
        self._sperren(False)
        hat_bericht = self._bericht is not None and self._bericht.is_file()
        self.btn_bericht.setEnabled(hat_bericht)
        # Exitcode 1 heisst bei der Satzpruefung "Befunde gefunden", nicht
        # "abgestuerzt" -- das darf keine Fehlermeldung ausloesen.
        if code in (0, 1):
            self.log.appendPlainText(f"\n— {titel} beendet —")
        else:
            self.log.appendPlainText(f"\n— {titel} mit Code {code} abgebrochen —")

    def _prozessfehler(self, _fehler) -> None:
        if self._prozess is None:
            return
        self.log.appendPlainText(f"\nFehler: {self._prozess.errorString()}")

    def _abbrechen(self) -> None:
        if self._prozess is not None:
            self._prozess.kill()

    def _sperren(self, laeuft: bool) -> None:
        self.btn_pruefen.setEnabled(not laeuft)
        self.btn_regelkreis.setEnabled(not laeuft)
        self.btn_abbrechen.setEnabled(laeuft)
        self.setCursor(Qt.CursorShape.BusyCursor if laeuft else Qt.CursorShape.ArrowCursor)

    # ── Kleinkram ───────────────────────────────────────────────────────

    def _zeige_pdf(self) -> None:
        if self._pdf is None:
            self._pdf_label.setText(
                "<b>PDF:</b> <i>keines gefunden — zuerst rendern (F5)</i>"
            )
        else:
            self._pdf_label.setText(f"<b>PDF:</b> {self._pdf}")

    def _pdf_waehlen(self) -> None:
        start = self._pdf.parent if self._pdf else self._buch
        pfad, _ = QFileDialog.getOpenFileName(
            self, "PDF für die Satzprüfung", str(start), "PDF (*.pdf)"
        )
        if pfad:
            self._pdf = Path(pfad)
            self._zeige_pdf()

    def _bericht_oeffnen(self) -> None:
        if self._bericht is not None and self._bericht.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._bericht)))

    def _grenzen_oeffnen(self) -> None:
        """Beide Schwellwert-Dateien erreichbar machen (Hilfe verspricht das)."""
        optionen = [
            ("Regelkreis: grenzen.toml (Schrift-Untergrenzen)",
             _REPO_ROOT / "tools" / "satzregelkreis" / "grenzen.toml"),
            ("Satzprüfung: schwellen.toml (Auslöse-Schwellen)",
             _REPO_ROOT / "tools" / "satzpruefer" / "schwellen.toml"),
        ]
        labels = [label for label, _ in optionen]
        gewaehlt, ok = QInputDialog.getItem(
            self,
            "Grenzwerte",
            "Welche Datei öffnen?",
            labels,
            0,
            False,
        )
        if not ok or not gewaehlt:
            return
        datei = next(path for label, path in optionen if label == gewaehlt)
        if not datei.is_file():
            QMessageBox.warning(
                self, "Grenzwerte", f"Datei nicht gefunden:\n{datei}"
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(datei)))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt-Namensschema)
        """Kein Prozess darf das Fenster überleben."""
        if self._prozess is not None:
            self._prozess.kill()
            self._prozess.waitForFinished(2000)
        super().closeEvent(event)


def open_satz_werkzeuge_qt(studio: Any, parent: Optional[QWidget] = None,
                           **_kwargs) -> None:
    """Einstieg aus dem Plugin: aktives Buch ermitteln, Dialog öffnen."""
    buch = getattr(studio, "current_book", None)
    if not buch:
        QMessageBox.warning(parent, "Satzprüfung & Regelkreis",
                            "Kein Buchprojekt aktiv.")
        return
    buch = Path(buch)

    from tools.live_preview.preview_render import newest_output_pdf

    SatzWerkzeugeQtDialog(
        parent, buch=buch, pdf=newest_output_pdf(buch),
        layout_profil=letztes_layout_profil(buch),
    ).exec()


def letztes_layout_profil(buch: Path) -> Optional[str]:
    """Layout-Profil des zeitlich letzten Renders (SSOT: publish_map)."""
    from tools.publish_map.store import last_layout_profile

    return last_layout_profile(buch)
