"""Bausteine, aus denen die Formulare des Layout-Editors gebaut sind.

Zahlenfelder mit der richtigen Einheit, ein Farbwähler, der Farbtokens genauso
versteht wie Hexwerte, und das (i) vor jeder erklärungsbedürftigen
Beschriftung. Kleinteilig, aber überall gleich — und deshalb an einer Stelle
statt in fünf Formularen.

Ohne Bezug zum Layout-Editor im Übrigen: Diese Widgets kennen weder eine
Definition noch eine Sitzung. Sie nehmen Werte entgegen und geben Werte zurück.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QColorDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from services.constants import StatusFg
from tools.doclayout.schema import LayoutError


_ALIGN_LABELS = {
    "left": "linksbündig",
    "center": "zentriert",
    "right": "rechtsbündig",
    "justify": "Blocksatz",
}

#: Ampelfarben des Buchabgleichs. Bewusst kraeftig: eine fehlende Zuordnung
#: ist der haeufigste Grund fuer ein enttaeuschendes .docx.
_CHECK_ALERT = "#b45309"
_CHECK_OK = "#16a34a"


#: Welche Farbe gerade zu welchem Objektnamen gehoert. Der Dialog setzt das
#: beim Umschalten der Helligkeit; die Formulare fragen nur.
_AKTUELLE_TOENE: dict[str, str] = {}


def set_tone_palette(farben: dict[str, str]) -> None:
    """Legt fest, welche Farbe zu welcher Rolle gehoert."""
    _AKTUELLE_TOENE.clear()
    _AKTUELLE_TOENE.update(farben)


def apply_tone(widget: QWidget) -> None:
    """Faerbt *widget* nach seiner Rolle -- einzeln, nicht ueber den Dialog.

    Warum einzeln: Sobald ein Widget ein Stylesheet traegt, malt Qt seine
    **Kinder** nicht mehr im Systemstil. Eine einzige Farbregel auf dem Dialog
    kostete deshalb allen Auswahlfeldern ihren nativen Rahmen -- sie bekamen
    einen harten schwarzen Kasten oben und unten. Am Etikett selbst richtet
    dieselbe Regel keinen Schaden an.

    Zu rufen, wann immer sich der Objektname aendert -- die Textbreitenanzeige
    wechselt zwischen "unauffaellig" und "stimmt nicht" -- oder die Helligkeit.
    """
    farbe = _AKTUELLE_TOENE.get(widget.objectName())
    widget.setStyleSheet(f"color: {farbe};" if farbe else "")


def _or_inherited(value: float) -> Optional[float]:
    """Negativ heisst «kein eigener Wert» -- so bleibt die echte Null erhalten."""
    return None if value < 0 else value


def _escape_html(text: str) -> str:
    """Fuer Labels im RichText-Modus. Profilnamen tragen Klammern, kein ``<``.

    Trotzdem maskiert: Die Namen kommen aus dem Profilkatalog, und ein
    spaeterer Eintrag mit ``&`` darf die Anzeige nicht zerlegen.
    """
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _mm_spin(maximum: float = 2000.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0.0, maximum)
    box.setDecimals(1)
    box.setSingleStep(0.5)
    box.setSuffix(" mm")
    return box


#: Kantenlaenge des Info-Symbols in Punkten der Oberflaeche.
_INFO_ICON_SIZE = 15

#: Einmal gemalt, vielfach benutzt -- der Editor zeigt ueber vierzig davon.
_INFO_ICON_CACHE: dict[int, "QPixmap"] = {}


def _info_icon(size: int = _INFO_ICON_SIZE) -> "QPixmap":
    """Ein blaues (i) -- gemalt, nicht als Schriftzeichen gesetzt.

    Eine Glyphe waere kuerzer zu schreiben, haengt aber an der Systemschrift:
    Sie faellt je nach Rechner anders aus und fehlt im schlimmsten Fall ganz.
    Gemalt sieht das Symbol ueberall gleich aus und laesst sich in der Groesse
    bestimmen.

    Vierfach gerendert und verkleinert: Das ergibt auch auf hochaufloesenden
    Bildschirmen saubere Kanten, ohne von der Skalierung des Systems abzuhaengen.
    """
    treffer = _INFO_ICON_CACHE.get(size)
    if treffer is not None:
        return treffer

    faktor = 4
    kante = size * faktor
    pixmap = QPixmap(kante, kante)
    pixmap.fill(Qt.GlobalColor.transparent)

    maler = QPainter(pixmap)
    maler.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    maler.setPen(Qt.PenStyle.NoPen)
    maler.setBrush(QColor(StatusFg.PRIMARY))
    maler.drawEllipse(0, 0, kante - 1, kante - 1)

    schrift = maler.font()
    schrift.setPixelSize(int(kante * 0.68))
    schrift.setBold(True)
    schrift.setFamily("Georgia")  # ein »i« mit Serifen liest sich als Symbol
    maler.setFont(schrift)
    maler.setPen(QColor("#ffffff"))
    maler.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "i")
    maler.end()

    klein = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    _INFO_ICON_CACHE[size] = klein
    return klein


def _info(text: str, erklaerung: str) -> QWidget:
    """Beschriftung mit einem (i) davor, das die Erklaerung traegt.

    Der Tooltip haengt an beidem -- Symbol und Text --, damit man ihn nicht
    genau treffen muss.

    Bewusst **ohne** ``setStyleSheet``: Ein Stylesheet auf dem Etikett faerbt
    in Qt auch dessen Tooltip. Genau daher kam grauer Text auf dem
    dunkelblauen Grund der App -- kaum zu lesen, und niemand haette den
    Zusammenhang vermutet.
    """
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)

    symbol = QLabel()
    symbol.setPixmap(_info_icon())
    symbol.setFixedSize(_INFO_ICON_SIZE, _INFO_ICON_SIZE)
    symbol.setCursor(Qt.CursorShape.WhatsThisCursor)
    symbol.setToolTip(erklaerung)
    layout.addWidget(symbol)

    if text:
        beschriftung = QLabel(text)
        beschriftung.setToolTip(erklaerung)
        layout.addWidget(beschriftung)
    layout.addStretch(1)
    host.setToolTip(erklaerung)
    return host


def _share_label_tooltips(widget: QWidget) -> None:
    """Gibt jede Etikett-Erklaerung an ihr Feld weiter.

    Man faehrt mal ueber das (i), mal ueber das Eingabefeld -- beide sollen
    antworten. Den Text zweimal hinzuschreiben waere der sichere Weg, dass
    eine Fassung veraltet; deshalb wird er hier einmal verteilt.

    Felder mit eigenem Tooltip bleiben unberuehrt: Wo etwas Spezifischeres
    steht, ist es Absicht.
    """
    for layout in widget.findChildren(QFormLayout):
        for zeile in range(layout.rowCount()):
            etikett = layout.itemAt(zeile, QFormLayout.ItemRole.LabelRole)
            feld = layout.itemAt(zeile, QFormLayout.ItemRole.FieldRole)
            if etikett is None or feld is None:
                continue
            quelle = etikett.widget()
            ziel = feld.widget()
            if quelle is None or ziel is None:
                continue
            if quelle.toolTip() and not ziel.toolTip():
                ziel.setToolTip(quelle.toolTip())


def _pt_spin(maximum: float = 400.0, minimum: float = 0.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(2)
    box.setSingleStep(0.5)
    box.setSuffix(" pt")
    return box


#: Wie viele Schriften hoechstens in eine Auswahl kommen. Auf einem Rechner mit
#: Designer-Installationen sind es leicht tausend; alle in ein Aufklappfeld zu
#: legen macht es unbenutzbar, ohne etwas zu gewinnen.
_MAX_SCHRIFTEN = 400


def _font_combo(
    *, fixed_pitch: bool = False, empty_label: str = ""
) -> QComboBox:
    """Ein Auswahlfeld mit den installierten Schriften.

    Vorher waren die drei Schriftfelder freie Texteingaben. Das ist die
    schlechteste Form fuer diesen Zweck: Man muss den Namen genau kennen, ein
    Tippfehler faellt nicht auf, und die Schrift faellt im fertigen Dokument
    stillschweigend auf eine Ersatzschrift zurueck -- sichtbar erst auf Papier.

    **Trotzdem bleibt das Feld beschreibbar.** Eine Vorlage wird nicht immer
    auf dem Rechner gesetzt, auf dem sie entsteht: Wer fuer eine Druckerei
    baut, muss eine Schrift eintragen koennen, die hier gar nicht installiert
    ist. Auswaehlen ist der Normalfall, Tippen bleibt moeglich.

    *fixed_pitch* zeigt nur Schriften fester Breite -- fuer Code ist alles
    andere schlicht falsch. *empty_label* stellt einen leeren Eintrag voran
    (fuer "wie die Grundschrift").
    """
    from PySide6.QtGui import QFontDatabase

    box = QComboBox()
    box.setEditable(True)
    box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    box.setMinimumContentsLength(18)

    if empty_label:
        box.addItem(empty_label, "")

    familien = [
        familie
        for familie in QFontDatabase.families()
        if not familie.startswith("@")  # senkrechte Ostasien-Varianten
        and (not fixed_pitch or QFontDatabase.isFixedPitch(familie))
    ]
    for familie in familien[:_MAX_SCHRIFTEN]:
        box.addItem(familie, familie)
        # Jeder Name in seiner eigenen Schrift -- man waehlt das Aussehen,
        # nicht die Zeichenkette.
        box.setItemData(box.count() - 1, QFont(familie), Qt.ItemDataRole.FontRole)

    if box.completer() is not None:
        box.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    return box


def font_value(box: QComboBox) -> str:
    """Der gewaehlte Schriftname -- leer heisst "keine eigene Wahl".

    Gelesen wird ueber die hinterlegten Daten und nicht ueber den Anzeigetext:
    Der Leereintrag heisst sichtbar "— wie Grundschrift —", und genau das darf
    nicht als Schriftname im Layout landen.
    """
    treffer = box.findText(box.currentText())
    if treffer >= 0:
        daten = box.itemData(treffer)
        if daten is not None:
            return str(daten)
    return box.currentText().strip()


def set_font_value(box: QComboBox, familie: str) -> None:
    """Traegt *familie* ein -- auch eine, die hier nicht installiert ist.

    Eine Vorlage entsteht nicht immer auf dem Rechner, auf dem sie gesetzt
    wird. Ein Layout, das eine fremde Schrift nennt, darf sie beim Oeffnen
    nicht verlieren.
    """
    text = str(familie or "").strip()
    if not text:
        leer = box.findData("")
        box.setCurrentIndex(leer if leer >= 0 else -1)
        if leer < 0:
            box.setCurrentText("")
        return
    treffer = box.findData(text)
    if treffer >= 0:
        box.setCurrentIndex(treffer)
    else:
        box.setCurrentText(text)


class _ColorButton(QToolButton):
    """Farbwähler, der Token-Namen genauso akzeptiert wie Hex-Werte.

    Eine einmal gesetzte Farbe ließ sich lange nicht mehr loswerden: Der
    Farbwähler kann nur wählen, und ``None`` — „geerbt" — kommt in ihm nicht
    vor. Wer versehentlich einen Hintergrund vergeben hatte, musste die YAML
    von Hand aufmachen. Deshalb der Rechtsklick, und deshalb steht er im
    Tooltip: eine Möglichkeit, die niemand findet, gibt es nicht.
    """

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._value: Optional[str] = None
        self._resolver: Callable[[Optional[str]], Optional[str]] = lambda v: v
        self.setMinimumWidth(120)
        self.setToolTip(
            "Klick: Farbe wählen. Rechtsklick: zurück auf »geerbt«."
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.clicked.connect(self._pick)
        self.customContextMenuRequested.connect(self._clear)

    def _clear(self) -> None:
        """Zurueck auf «geerbt» -- der Weg heraus aus einer gesetzten Farbe."""
        if self._value is None:
            return
        self._value = None
        self._repaint()
        self.changed.emit()

    def set_resolver(self, resolver: Callable[[Optional[str]], Optional[str]]) -> None:
        self._resolver = resolver

    def value(self) -> Optional[str]:
        return self._value

    def set_value(self, value: Optional[str]) -> None:
        self._value = value or None
        self._repaint()

    def _repaint(self) -> None:
        if not self._value:
            self.setText("— geerbt —")
            self.setStyleSheet("")
            return
        try:
            hex_value = self._resolver(self._value)
        except LayoutError:
            hex_value = None
        self.setText(str(self._value))
        if hex_value and hex_value != "auto":
            colour = QColor(f"#{hex_value}")
            contrast = "#000" if colour.lightness() > 140 else "#fff"
            self.setStyleSheet(
                f"background-color: #{hex_value}; color: {contrast}; "
                f"border: 1px solid #888; padding: 3px;"
            )
        else:
            self.setStyleSheet("")

    def _pick(self) -> None:
        try:
            current = self._resolver(self._value) or "888888"
        except LayoutError:
            current = "888888"
        chosen = QColorDialog.getColor(QColor(f"#{current}"), self, "Farbe wählen")
        if not chosen.isValid():
            return
        self._value = chosen.name().lstrip("#").upper()
        self._repaint()
        self.changed.emit()


__all__ = [
    "_ALIGN_LABELS",
    "_CHECK_ALERT",
    "_CHECK_OK",
    "_INFO_ICON_SIZE",
    "_ColorButton",
    "_escape_html",
    "_font_combo",
    "_info",
    "_info_icon",
    "_mm_spin",
    "_or_inherited",
    "_pt_spin",
    "apply_tone",
    "font_value",
    "set_font_value",
    "set_tone_palette",
    "_share_label_tooltips",
]
