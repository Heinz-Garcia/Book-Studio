"""Nacharbeit nach einem Automatik-Lauf -- die Fragen kommen am Ende, nicht unterwegs.

Zeigt den vollständigen DOCX-Pfad und fragt nach dem, was offen ist:

* **Fehlende Ressourcen:** „Datei wählen…“ oder „Platzhalter einsetzen“.
* **Absatzformate ohne Zuordnung:** ein Format der Vorlage wählen oder
  „Als Fließtext fortsetzen“; Shortcut in den Layout-Editor.
* **Pflichtseiten:** Link auf die benutzte Vorlage (★ = wörtlich gleich) und
  Shortcut in den Skeleton-Editor -- um die Vorlage selbst zu korrigieren.

Danach „DOCX neu setzen“. Logik: ``services/nacharbeit.py``.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services import nacharbeit

__all__ = ["NacharbeitDialog", "open_nacharbeit_dialog"]


def _oeffne(pfad: str | Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(pfad)))


def _eintrag(titel: str, detail: str = "") -> tuple[QFrame, QHBoxLayout]:
    """Ein Punkt als Block: Titel, Erklärung, darunter die Knöpfe -- nichts läuft rechts hinaus."""
    rahmen = QFrame()
    rahmen.setFrameShape(QFrame.Shape.StyledPanel)
    senkrecht = QVBoxLayout(rahmen)
    kopf = QLabel(f"<b>{titel}</b>")
    kopf.setWordWrap(True)
    senkrecht.addWidget(kopf)
    if detail:
        text = QLabel(detail)
        text.setWordWrap(True)
        senkrecht.addWidget(text)
    knoepfe = QHBoxLayout()
    senkrecht.addLayout(knoepfe)
    return rahmen, knoepfe


class NacharbeitDialog(QDialog):
    """Offene Punkte eines Automatik-Laufs beantworten und die DOCX neu setzen."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        book: Path,
        layout_name: str,
        docx: str = "",
        lauf_ordner: Path | None = None,
        library_root: Path | None = None,
        skeleton_profil: str = "",
    ) -> None:
        super().__init__(parent)
        self.book = Path(book)
        self.layout_name = layout_name
        self.lauf_ordner = Path(lauf_ordner) if lauf_ordner else None
        self.library_root = library_root
        self.geaendert = False
        self.setWindowTitle(f"Automatik – Nacharbeit: {self.book.name}")
        self.resize(900, 720)
        self.punkte: dict[str, Any] = nacharbeit.offene_punkte(
            self.book, layout_name=layout_name, library_root=library_root, skeleton_profil=skeleton_profil
        )

        lay = QVBoxLayout(self)
        lay.addWidget(self._kopf(docx))
        rumpf = QWidget()
        self._rumpf = QVBoxLayout(rumpf)
        self._rumpf.addWidget(self._ressourcen())
        self._rumpf.addWidget(self._formate())
        self._rumpf.addWidget(self._ivz())
        self._rumpf.addWidget(self._pflichtseiten())
        self._rumpf.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(rumpf)
        lay.addWidget(scroll, 1)

        self.protokoll = QPlainTextEdit()
        self.protokoll.setReadOnly(True)
        self.protokoll.setMaximumHeight(110)
        self.protokoll.setPlaceholderText("Was hier entschieden wird, steht in diesem Protokoll.")
        lay.addWidget(self.protokoll)

        knoepfe = QHBoxLayout()
        knoepfe.addStretch(1)
        self.neu_setzen = QPushButton("DOCX neu setzen")
        self.neu_setzen.clicked.connect(self._setze_neu)
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.accept)
        knoepfe.addWidget(self.neu_setzen)
        knoepfe.addWidget(schliessen)
        lay.addLayout(knoepfe)

    # ── Kopf: DOCX und Berichte ───────────────────────────────────────

    def _kopf(self, docx: str) -> QWidget:
        box = QGroupBox("Ergebnis")
        raster = QGridLayout(box)
        raster.addWidget(QLabel("DOCX:"), 0, 0)
        self.docx_feld = QLineEdit(docx)
        self.docx_feld.setReadOnly(True)
        raster.addWidget(self.docx_feld, 0, 1)
        oeffnen = QPushButton("Öffnen")
        oeffnen.clicked.connect(lambda: _oeffne(self.docx_feld.text()))
        ordner = QPushButton("Ordner")
        ordner.clicked.connect(lambda: _oeffne(Path(self.docx_feld.text()).parent))
        raster.addWidget(oeffnen, 0, 2)
        raster.addWidget(ordner, 0, 3)
        zeile = QHBoxLayout()
        if self.lauf_ordner is not None:
            for datei, text in (
                ("automatik_gegenueberstellung.html", "Gegenüberstellung Vorfassung ↔ übernommen"),
                ("automatik_bericht.md", "Abschlussbericht"),
            ):
                pfad = self.lauf_ordner / datei
                if pfad.is_file():
                    knopf = QPushButton(text)
                    knopf.clicked.connect(lambda _=False, p=pfad: _oeffne(p))
                    zeile.addWidget(knopf)
        zeile.addStretch(1)
        raster.addLayout(zeile, 1, 0, 1, 4)
        return box

    def _melde(self, text: str) -> None:
        self.protokoll.appendPlainText(text)

    # ── Fehlende Ressourcen ───────────────────────────────────────────

    def _ressourcen(self) -> QWidget:
        eintraege = self.punkte["fehlende_ressourcen"]
        box = QGroupBox(f"Fehlende Ressourcen ({len(eintraege)})")
        senkrecht = QVBoxLayout(box)
        if not eintraege:
            senkrecht.addWidget(QLabel("Keine – alle Bilder sind da."))
        for eintrag in eintraege:
            rahmen, knoepfe = _eintrag(
                eintrag["ziel"],
                f"verwendet in: {', '.join(eintrag['fundstellen'])}<br>erwartet unter: {eintrag['ablage']}",
            )
            status = QLabel("offen")
            waehlen = QPushButton("Datei wählen…")
            platzhalter = QPushButton("Platzhalter einsetzen")
            waehlen.clicked.connect(lambda _=False, e=eintrag, s=status: self._waehle_datei(e, s))
            platzhalter.clicked.connect(lambda _=False, e=eintrag, s=status: self._platzhalter(e, s))
            for w in (waehlen, platzhalter):
                knoepfe.addWidget(w)
            knoepfe.addWidget(status)
            knoepfe.addStretch(1)
            senkrecht.addWidget(rahmen)
        return box

    def _waehle_datei(self, eintrag: dict, status: QLabel) -> None:
        quelle, _filter = QFileDialog.getOpenFileName(self, f"Datei für {eintrag['ziel']}")
        if not quelle:
            return
        try:
            ziel = nacharbeit.uebernimm_ressource(quelle, eintrag["ablage"])
        except OSError as exc:
            QMessageBox.warning(self, "Ressource", str(exc))
            return
        status.setText("✅ übernommen")
        self.geaendert = True
        self._melde(f"Ressource {eintrag['ziel']}: {quelle} → {ziel}")

    def _platzhalter(self, eintrag: dict, status: QLabel) -> None:
        try:
            ziel = nacharbeit.setze_platzhalter(eintrag["ablage"], name=Path(eintrag["ziel"]).name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Platzhalter", str(exc))
            return
        status.setText("✅ Platzhalter")
        self.geaendert = True
        self._melde(f"Ressource {eintrag['ziel']}: Platzhalter eingesetzt → {ziel}")

    # ── Absatzformate ─────────────────────────────────────────────────

    def _formate(self) -> QWidget:
        eintraege = self.punkte["formate_ohne_zuordnung"]
        box = QGroupBox(f"Absatzformate ohne Zuordnung ({len(eintraege)}) — Vorlage „{self.layout_name}“")
        senkrecht = QVBoxLayout(box)
        if not eintraege:
            senkrecht.addWidget(QLabel("Keine – alle Auszeichnungen haben ein Absatzformat."))
        for eintrag in eintraege:
            rahmen, knoepfe = _eintrag(
                f".{eintrag['klasse']}",
                f"in: {', '.join(eintrag['dateien'])}<br>Probe: {eintrag['probe'][:200]}",
            )
            auswahl = QComboBox()
            # Bewusst ohne Vorbelegung: ein Klick auf „Zuordnen“ ohne Wahl
            # darf nicht still den Fließtext zum Titel machen.
            auswahl.addItem("— Absatzformat wählen —", "")
            for name in self.punkte["absatzformate"]:
                auswahl.addItem(name, name)
            status = QLabel("offen")
            zuordnen = QPushButton("Zuordnen")
            zuordnen.setEnabled(False)
            auswahl.currentIndexChanged.connect(
                lambda _i, a=auswahl, z=zuordnen: z.setEnabled(bool(a.currentData()))
            )
            fliesstext = QPushButton("Als Fließtext fortsetzen")
            zuordnen.clicked.connect(
                lambda _=False, e=eintrag, a=auswahl, s=status: self._ordne_zu(e, str(a.currentData()), s)
            )
            fliesstext.clicked.connect(
                lambda _=False, e=eintrag, s=status: self._ordne_zu(e, nacharbeit.FLIESSTEXT, s)
            )
            for w in (auswahl, zuordnen, fliesstext, status):
                knoepfe.addWidget(w)
            knoepfe.addStretch(1)
            senkrecht.addWidget(rahmen)
        editor = QPushButton("Im Layout-Editor öffnen …")
        editor.clicked.connect(self._layout_editor)
        senkrecht.addWidget(editor)
        return box

    def _ordne_zu(self, eintrag: dict, absatzformat: str, status: QLabel) -> None:
        try:
            pfad = nacharbeit.ordne_zu(self.layout_name, eintrag["klasse"], absatzformat)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Zuordnung", str(exc))
            return
        status.setText(f"✅ → {absatzformat}")
        self.geaendert = True
        wie = "als Fließtext fortgesetzt" if absatzformat == nacharbeit.FLIESSTEXT else f"→ {absatzformat}"
        self._melde(f"Klasse .{eintrag['klasse']} {wie} (Vorlage {pfad})")

    def _layout_editor(self) -> None:
        try:
            from ui_qt.dialogs.doclayout_editor_dialog import open_doclayout_editor_qt

            open_doclayout_editor_qt(parent=self, focus_unmapped=True)
        except (ImportError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Layout-Editor", f"Layout-Editor nicht zu öffnen: {exc}")

    # ── Verzeichnis ───────────────────────────────────────────────────

    def _ivz(self) -> QWidget:
        """Zu lange Verzeichniseintraege -- nur anzeigen: Die Ueberschriften
        liefert der Generator, gekuerzt wird dort (oder in Word)."""
        eintraege = self.punkte.get("ivz_zu_lang") or []
        box = QGroupBox(f"Verzeichniseinträge, die umbrechen ({len(eintraege)})")
        senkrecht = QVBoxLayout(box)
        if not eintraege:
            senkrecht.addWidget(QLabel("Keine – jeder Eintrag passt in eine Zeile."))
            return box
        grenze = min(e["grenze"] for e in eintraege)
        hinweis = QLabel(
            f"Höchstens etwa {grenze} Zeichen je Eintrag (Vorlage „{self.layout_name}“). "
            "Kürzen in der Quelle (GrammarGraph) oder in Word."
        )
        hinweis.setWordWrap(True)
        senkrecht.addWidget(hinweis)
        for eintrag in eintraege:
            rahmen, _knoepfe = _eintrag(
                html.escape(eintrag["titel"]),
                f"Ebene {eintrag['ebene']}: {eintrag['zeichen']} Zeichen "
                f"(Grenze ≈ {eintrag['grenze']}; {eintrag['breite_mm']} mm für {eintrag['platz_mm']} mm Platz)",
            )
            senkrecht.addWidget(rahmen)
        return box

    # ── Pflichtseiten ─────────────────────────────────────────────────

    def _pflichtseiten(self) -> QWidget:
        seiten = self.punkte["pflichtseiten"]
        box = QGroupBox(f"Pflichtseiten aus Vorlagen ({len(seiten)}) — in Word prüfen, Vorlage korrigieren")
        senkrecht = QVBoxLayout(box)
        for seite in seiten:
            rahmen, knoepfe = _eintrag(seite["pfad"], seite["herkunft"])
            im_buch = QPushButton("Im Buch öffnen")
            im_buch.clicked.connect(lambda _=False, p=self.book / seite["pfad"]: _oeffne(p))
            knoepfe.addWidget(im_buch)
            vorlagen = seite["vorlagen"]
            if vorlagen:
                erste = vorlagen[0]
                knopf = QToolButton()
                marke = "★ " if erste["identisch"] else ""
                knopf.setText(f"Vorlage öffnen: {marke}{erste['profil']}")
                knopf.setToolTip(erste["pfad"])
                knopf.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                knopf.clicked.connect(lambda _=False, p=erste["pfad"]: _oeffne(p))
                menue = QMenu(knopf)
                for vorlage in vorlagen:
                    zeichen = "★ " if vorlage["identisch"] else ""
                    aktion = menue.addAction(f"{zeichen}{vorlage['profil']} — {vorlage['pfad']}")
                    aktion.triggered.connect(lambda _=False, p=vorlage["pfad"]: _oeffne(p))
                knopf.setMenu(menue)
                knoepfe.addWidget(knopf)
            else:
                knoepfe.addWidget(QLabel("keine Vorlage in der Bibliothek"))
            knoepfe.addStretch(1)
            senkrecht.addWidget(rahmen)
        hinweis = QLabel("★ = wörtlich gleich mit der Seite im Buch, also die benutzte Vorlage.")
        senkrecht.addWidget(hinweis)
        editor = QPushButton("Skeleton-Editor öffnen …")
        editor.clicked.connect(self._skeleton_editor)
        senkrecht.addWidget(editor)
        return box

    def _skeleton_editor(self) -> None:
        try:
            from ui_qt.dialogs.skeleton_editor_dialog import open_skeleton_editor_qt

            open_skeleton_editor_qt(parent=self)
        except (ImportError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Skeleton-Editor", f"Skeleton-Editor nicht zu öffnen: {exc}")

    # ── Neu setzen ────────────────────────────────────────────────────

    def _setze_neu(self) -> None:
        self.neu_setzen.setEnabled(False)
        self._melde("Setze DOCX neu …")
        QApplication.processEvents()
        try:
            ergebnis = nacharbeit.setze_docx_neu(self.book, self.layout_name)
        finally:
            self.neu_setzen.setEnabled(True)
        if ergebnis["docx"]:
            self.docx_feld.setText(ergebnis["docx"])
        self._melde(ergebnis["meldung"])
        for warnung in ergebnis["warnungen"]:
            self._melde(f"⚠ {warnung}")
        self.geaendert = False


#: Offene Nacharbeit-Fenster (sonst räumt der Garbage Collector sie weg).
_OFFEN: list[NacharbeitDialog] = []


def open_nacharbeit_dialog(**kwargs: Any) -> int:
    """Eigenständig oder aus dem Studio: Dialog **nicht modal** zeigen.

    Nicht modal, weil er Layout- und Skeleton-Editor öffnet -- aus einem
    modalen Dialog bekämen die keine Eingaben (Schutztest
    ``test_modal_oeffnet_keine_freien_fenster``). Eigenständig gestartet läuft
    die Ereignisschleife, bis das letzte Fenster zu ist.
    """
    eigene_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    dialog = NacharbeitDialog(kwargs.pop("parent", None), **kwargs)
    dialog.setModal(False)
    _OFFEN.append(dialog)
    dialog.finished.connect(lambda _r, d=dialog: _OFFEN.remove(d) if d in _OFFEN else None)
    dialog.show()
    return app.exec() if eigene_app else 0
