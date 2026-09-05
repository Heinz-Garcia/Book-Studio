"""Dunkle Fassung -- ausschliesslich fuer den Layout-Editor.

Der Grund ist kein Geschmack, sondern Lesbarkeit: rechts im Fenster steht ein
weisses Blatt Papier. Liegt die Bedienung ringsum ebenfalls auf Weiss, geht die
Grenze zwischen Werkzeug und Werkstueck verloren -- man sucht das Dokument im
Fenster. Auf dunklem Grund steht es fuer sich.

Bewusst **nicht** appweit: ``ui_qt.theme`` bleibt der helle El-Pitugrafo-Look
fuer Book Studio. Dieses Stylesheet wird auf die Dialoginstanz gesetzt und gilt
damit nur fuer sie und ihre Kinder.

Die Vorschau selbst bleibt unberuehrt. Sie zeigt, was Writer aus der Vorlage
macht, und das ist weisses Papier -- es einzufaerben hiesse, die Vorschau zu
faelschen.
"""

from __future__ import annotations

#: Grundtoene. An einer Stelle, damit eine Korrektur nicht sechs Regeln braucht.
BACKGROUND = "#23262b"
PANEL = "#2b2f36"
INPUT = "#1e2126"
BORDER = "#3d434d"
TEXT = "#e6e8ec"
TEXT_MUTED = "#9aa3af"
ACCENT = "#4da3ff"
SELECTION = "#2f5d94"
BUTTON = "#343a44"
BUTTON_HOVER = "#3f4653"
BUTTON_PRESSED = "#2b3039"

DARK_STYLESHEET = f"""
QDialog, QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT};
}}
QLabel {{
    color: {TEXT};
    background: transparent;
}}

/* Kurzhilfe: die App faerbt sie hellblau mit dunkler Schrift. */
QFrame#HelpBar {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QLabel#HelpBarText, QLabel#HelpBarIcon {{
    color: {TEXT_MUTED};
    background: transparent;
}}

QGroupBox {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
}}
QGroupBox::title {{
    /* Das App-Thema legt hier eine helle Flaeche unter den Titel. Ohne eigene
       Angabe bliebe sie stehen -- eine hellblaue Insel im dunklen Rahmen. */
    color: {ACCENT};
    background: {PANEL};
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 0px;
    padding: 0 6px;
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: {SELECTION};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}

/* Der Auswahlkasten bekommt bewusst **kein** ``padding``. Als Widget-Stylesheet
   verkuerzt es die Aufklappliste um feste 16 Pixel: Qt bemisst das Popup dann
   kleiner, als die Zeilen brauchen, und die letzten Eintraege verschwinden
   hinter einem Bildlaufpfeil, obwohl reichlich Platz waere. ``min-height``
   erreicht dieselbe Hoehe ohne diese Nebenwirkung. */
QComboBox {{
    background-color: {INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    min-height: 22px;
    selection-background-color: {SELECTION};
}}
QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox:disabled {{ color: {TEXT_MUTED}; background-color: {BACKGROUND}; }}

/* Aufklapp-Pfeil bewusst NICHT gestaltet.

   Ein Pfeil aus zwei Rahmenlinien braucht eine 45-Grad-Drehung, um wie ein
   Winkel auszusehen -- und ``transform`` gibt es in Qt-Stylesheets nicht. Die
   Ecke bleibt stehen und sieht aus wie ein verdrehtes L.

   Auch ``QComboBox::drop-down`` allein zu gestalten hilft nicht: Sobald diese
   Unterkomponente eine eigene Regel hat, zeichnet Qt den nativen Pfeil gar
   nicht mehr -- der Kasten steht dann ohne jeden Hinweis da.

   Ohne beide Regeln zeichnet Fusion sein eigenes Dreieck, und das ist auf
   dunklem Grund einwandfrei sichtbar. Gemessen, nicht vermutet. */

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {TEXT_MUTED};
    background-color: {BACKGROUND};
}}
QComboBox QAbstractItemView {{
    background-color: {INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {SELECTION};
}}

QPushButton, QToolButton {{
    background-color: {BUTTON};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 12px;
}}
QPushButton:hover, QToolButton:hover {{ background-color: {BUTTON_HOVER}; }}
QPushButton:pressed, QToolButton:pressed {{ background-color: {BUTTON_PRESSED}; }}
QPushButton:disabled {{
    background-color: {BACKGROUND};
    color: {TEXT_MUTED};
    border: 1px solid {BACKGROUND};
}}
QToolButton:checked {{
    background-color: {SELECTION};
    border: 1px solid {ACCENT};
}}

QListWidget {{
    background-color: {INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QListWidget::item:selected {{
    background-color: {SELECTION};
    color: {TEXT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {PANEL};
}}
QTabBar::tab {{
    background: {BUTTON};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    padding: 4px 12px;
}}
QTabBar::tab:selected {{
    background: {PANEL};
    color: {TEXT};
    border-bottom-color: {PANEL};
}}

QCheckBox {{ color: {TEXT}; background: transparent; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER};
    border-radius: 2px;
    background: {INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

QScrollArea, QScrollArea > QWidget {{ background-color: {BACKGROUND}; }}
QSplitter::handle {{ background-color: {BORDER}; }}
QToolTip {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
"""


# ---------------------------------------------------------------------------
# Nebentoene, die in beiden Helligkeiten lesbar bleiben muessen
# ---------------------------------------------------------------------------
#
# Elf Beschriftungen trugen ihre Farbe frueher als festen Hexwert im Code
# (``setStyleSheet("color: #666")``). Auf dem hellen Grund war das richtig, auf
# ``#23262b`` kam ``#666`` auf einen Kontrast von etwa 1,9:1 -- unter jeder
# Lesbarkeitsschwelle, und der Umschalter zog sie nicht nach, weil er nur das
# Stylesheet des Dialogs tauscht.
#
# Jetzt tragen sie Objektnamen, und die Farbe kommt aus dem Stylesheet. Damit
# gilt sie in beiden Fassungen -- und an einer Stelle statt an elf.

#: Nebensaechliche Auskunft (Textbreite, Statuszeile, Erklaerungen darunter).
MUTED_NAME = "DocLayoutMuted"
#: Etwas, das nicht stimmt (Raender ohne Textbreite, unerzeugbares Layout).
ALERT_NAME = "DocLayoutAlert"
#: Ungespeicherte Aenderungen -- Aufmerksamkeit, aber keine Warnung.
DIRTY_NAME = "DocLayoutDirty"

_NEBENTOENE_HELL = {MUTED_NAME: "#666666", ALERT_NAME: "#b00000", DIRTY_NAME: "#b06000"}
_NEBENTOENE_DUNKEL = {MUTED_NAME: "#9aa3af", ALERT_NAME: "#ff8a80", DIRTY_NAME: "#ffb454"}


#: Die Nebentoene werden **nicht** ueber das Dialog-Stylesheet gesetzt, sondern
#: einzeln auf die betroffenen Widgets (siehe ``doclayout_widgets.apply_tone``).
#:
#: Der Grund kam aus dem Live-Test: Sobald ein Widget ein Stylesheet traegt,
#: malt Qt seine Kinder nicht mehr im Systemstil. Ein Stylesheet auf dem Dialog
#: -- und sei es nur eine Farbregel -- kostete deshalb allen Auswahlfeldern
#: ihren nativen Rahmen; sie bekamen einen harten schwarzen Kasten oben und
#: unten. Im Dunkelmodus faellt das nicht auf, weil ``QComboBox`` dort ohnehin
#: ausdruecklich gestaltet wird -- im Hellmodus sah es kaputt aus.
#:
#: Der Dialog traegt im Hellmodus daher wieder gar kein Stylesheet.
TONE_LIGHT = dict(_NEBENTOENE_HELL)
TONE_DARK = dict(_NEBENTOENE_DUNKEL)


__all__ = [
    "ALERT_NAME",
    "DARK_STYLESHEET",
    "DIRTY_NAME",
    "TONE_DARK",
    "TONE_LIGHT",
    "MUTED_NAME",
]
