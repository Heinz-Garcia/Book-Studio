"""Hinweis auf Textklassen ohne Absatzformat.

Der Generator fuehrt jederzeit neue Fenced-Div-Klassen ein (``.spanisch``,
``.key-takeaway``). Ohne zugeordnetes Absatzformat bleibt so ein Block in der
``.docx`` gewoehnlicher Fliesstext: Die Auszeichnung steht sichtbar im
Markdown und ist im Druck trotzdem wirkungslos -- und niemand erfaehrt davon.

Dieser Dialog ist die fehlende Rueckmeldung. Er kennt zwei Anlaesse:

``IMPORT``
    Direkt nach der Uebernahme eines Exports. Er *meldet und bietet an*; der
    Import ist bereits gelaufen und wird nicht zurueckgenommen.

``TYPESET``
    Vor dem Satz. Hier entsteht der Schaden, deshalb haelt der Lauf an --
    fortfahren bleibt aber moeglich, die Entscheidung gehoert dem Benutzer.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.doclayout.usage import suggested_style_id


class Anlass(str, Enum):
    IMPORT = "import"
    TYPESET = "typeset"


class Antwort(str, Enum):
    EDITOR = "editor"        # Layout-Editor oeffnen
    WEITER = "weiter"        # trotzdem fortfahren / spaeter
    ABBRUCH = "abbruch"      # Vorgang abbrechen


class MissingClassesDialog(QDialog):
    """Listet Klassen ohne Absatzformat samt Namensvorschlag."""

    def __init__(
        self,
        klassen: Iterable[str],
        *,
        anlass: Anlass,
        counts: Optional[dict[str, int]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._antwort = Antwort.WEITER
        self._klassen = [str(k).strip().lstrip(".") for k in klassen if str(k).strip()]
        self._counts = dict(counts or {})
        self.setWindowTitle(
            "Neue Textarten ohne Layout"
            if anlass is Anlass.IMPORT
            else "Buch setzen — Textarten ohne Layout"
        )
        self.setMinimumWidth(560)
        self._build(anlass)

    # -- Aufbau ------------------------------------------------------------
    def _build(self, anlass: Anlass) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        kopf = QLabel(self._kopftext(anlass))
        kopf.setWordWrap(True)
        kopf.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(kopf)

        tabelle = QTableWidget(len(self._klassen), 3, self)
        tabelle.setHorizontalHeaderLabels(["Textart", "Vorkommen", "Vorschlag Formatvorlage"])
        tabelle.verticalHeader().setVisible(False)
        tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabelle.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        vorhanden: list[str] = []
        for zeile, name in enumerate(self._klassen):
            vorschlag = suggested_style_id(name, vorhanden)
            vorhanden.append(vorschlag)
            anzahl = self._counts.get(name)
            tabelle.setItem(zeile, 0, QTableWidgetItem(f".{name}"))
            tabelle.setItem(
                zeile, 1, QTableWidgetItem("—" if anzahl is None else f"{anzahl}×")
            )
            tabelle.setItem(zeile, 2, QTableWidgetItem(vorschlag))
        tabelle.resizeColumnsToContents()
        tabelle.horizontalHeader().setStretchLastSection(True)
        hoehe = min(220, 32 + 28 * max(1, len(self._klassen)))
        tabelle.setMinimumHeight(hoehe)
        layout.addWidget(tabelle)
        self.table = tabelle

        fuss = QLabel(
            "Im Layout-Editor legst du dafür Absatzformate an "
            "(<i>Fehlende Formate anlegen</i> erzeugt sie in einem Zug) "
            "und gestaltest sie anschließend."
        )
        fuss.setWordWrap(True)
        fuss.setTextFormat(Qt.TextFormat.RichText)
        fuss.setStyleSheet("QLabel { color: #475569; }")
        layout.addWidget(fuss)

        knoepfe = QDialogButtonBox(self)
        self.btn_editor = QPushButton("Layout-Editor öffnen …")
        self.btn_editor.setDefault(True)
        knoepfe.addButton(self.btn_editor, QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_editor.clicked.connect(self._auf_editor)

        if anlass is Anlass.IMPORT:
            self.btn_weiter = QPushButton("Später")
            knoepfe.addButton(self.btn_weiter, QDialogButtonBox.ButtonRole.RejectRole)
        else:
            self.btn_weiter = QPushButton("Trotzdem fortfahren")
            knoepfe.addButton(self.btn_weiter, QDialogButtonBox.ButtonRole.DestructiveRole)
            self.btn_abbruch = QPushButton("Abbrechen")
            knoepfe.addButton(self.btn_abbruch, QDialogButtonBox.ButtonRole.RejectRole)
            self.btn_abbruch.clicked.connect(self._auf_abbruch)
        self.btn_weiter.clicked.connect(self._auf_weiter)
        layout.addWidget(knoepfe)

    def _kopftext(self, anlass: Anlass) -> str:
        anzahl = len(self._klassen)
        wort = "Textart" if anzahl == 1 else "Textarten"
        if anlass is Anlass.IMPORT:
            return (
                f"<b>{anzahl} neue {wort} ohne Absatzformat.</b><br>"
                "Der übernommene Export enthält Auszeichnungen, für die in keinem "
                "Layout der Bibliothek eine Vorlage existiert. Sie erscheinen im "
                "Satz als gewöhnlicher Fließtext und sind vom Fachtext nicht zu "
                "unterscheiden."
            )
        return (
            f"<b style='color:#991b1b;'>{anzahl} {wort} ohne Absatzformat — "
            "der Satz würde sie als Fließtext ausgeben.</b><br>"
            "Die Auszeichnung steht im Markdown, bleibt im Druck aber wirkungslos. "
            "Du kannst fortfahren; das Ergebnis enthält diese Abschnitte dann "
            "ohne eigene Gestaltung."
        )

    # -- Antworten ---------------------------------------------------------
    def _auf_editor(self) -> None:
        self._antwort = Antwort.EDITOR
        self.accept()

    def _auf_weiter(self) -> None:
        self._antwort = Antwort.WEITER
        self.accept()

    def _auf_abbruch(self) -> None:
        self._antwort = Antwort.ABBRUCH
        self.reject()

    @property
    def antwort(self) -> Antwort:
        return self._antwort


def ask_about_missing_classes(
    klassen: Iterable[str],
    *,
    anlass: Anlass,
    counts: Optional[dict[str, int]] = None,
    parent: Optional[QWidget] = None,
) -> Antwort:
    """Dialog zeigen und die Entscheidung zurueckgeben.

    Ohne fehlende Klassen wird nichts gezeigt und ``WEITER`` gemeldet -- die
    Aufrufstellen brauchen dadurch keine eigene Fallunterscheidung.
    """
    namen = [str(k).strip().lstrip(".") for k in klassen if str(k).strip()]
    if not namen:
        return Antwort.WEITER
    dialog = MissingClassesDialog(namen, anlass=anlass, counts=counts, parent=parent)
    dialog.exec()
    return dialog.antwort
