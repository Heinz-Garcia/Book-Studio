"""El-Pitugrafo Look & Feel — SSOT für Book Studio Qt.

Angeglichen an GrammarGraph ``src/gui/styles.py``.
Wird über ``ui_qt.theme.apply_theme`` app-weit gesetzt.
"""

from __future__ import annotations

from pathlib import Path

#: SVG-Pfeile fuer SpinBox (CSS-border-Dreiecke werden unter Windows oft zu Balken).
_ICON_DIR = Path(__file__).resolve().parent / "icons"


def _icon_url(name: str) -> str:
    """Qt-Stylesheet-URL (forward slashes, auch unter Windows)."""
    return _ICON_DIR.joinpath(name).as_posix()


_SPIN_UP = _icon_url("spin_up.svg")
_SPIN_DOWN = _icon_url("spin_down.svg")
_SPIN_UP_OFF = _icon_url("spin_up_disabled.svg")
_SPIN_DOWN_OFF = _icon_url("spin_down_disabled.svg")

# Oeffentlich fuer andere Stylesheets (z.B. dunkler Layout-Editor).
SPIN_ARROW_UP = _SPIN_UP
SPIN_ARROW_DOWN = _SPIN_DOWN
SPIN_ARROW_UP_DISABLED = _SPIN_UP_OFF
SPIN_ARROW_DOWN_DISABLED = _SPIN_DOWN_OFF

# Generische Regeln (MainWindow + alle Dialoge). Keine Dialog-ObjectNames.
# Wie GrammarGraph: helles Panel — kein dunkler Scroll-Hintergrund hinter GroupBoxes.
PITU_CORE_STYLESHEET = """
QWidget {
    background: #f4f6fb;
    color: #1c2740;
    font-size: 10.5pt;
}
QMainWindow, QDialog {
    background: #f4f6fb;
    color: #1c2740;
}
QToolTip {
    background: #2d3a5e;
    color: #e8eeff;
    border: 1px solid #5a7dd6;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 10pt;
    font-weight: 500;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #d7deee;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 0px;
    padding: 0 6px;
    color: #334b86;
    background: #f4f6fb;
}
/* Checkbare GroupBox (z. B. Rahmen Oben/Unten/…): gleiches Kästchen wie QCheckBox.
   Ohne eigene Indicator-Regel malt Qt nach QGroupBox-Stylesheet nichts Sichtbares. */
QGroupBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #5a7dd6;
    border-radius: 3px;
    background: #fbfcff;
}
QGroupBox::indicator:checked {
    background: #2f5cc8;
    border: 1px solid #2f5cc8;
}
QLabel {
    color: #1c2740;
    background: transparent;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: #fbfcff;
    border: 1px solid #c8d3ec;
    border-radius: 7px;
    padding: 6px 8px;
    color: #1c2740;
    min-height: 22px;
}
/* QComboBox absichtlich getrennt von QLineEdit:
   Vertikales padding am Kasten verkürzt die Aufklappliste; zusammen mit
   Fusion/Windows erscheinen dann dicke schwarze Balken oben/unten am Popup.
   Nur horizontales Padding + min-height (wie Layout-Editor). */
QComboBox {
    background: #fbfcff;
    border: 1px solid #c8d3ec;
    border-radius: 7px;
    padding: 0px 8px;
    color: #1c2740;
    min-height: 28px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #5a7dd6;
}
QComboBox:focus {
    border: 1px solid #5a7dd6;
}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {
    background: #eef1f8;
    border: 1px dashed #b8c4dc;
    color: #8899bb;
}
QComboBox:disabled {
    background: #eef1f8;
    border: 1px dashed #b8c4dc;
    color: #8899bb;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1c2740;
    border: 1px solid #c8d3ec;
    border-radius: 0px;
    outline: none;
    padding: 0px;
    margin: 0px;
    selection-background-color: #2f5cc8;
    selection-color: #ffffff;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    min-height: 22px;
    border: none;
    color: #1c2740;
    background-color: #ffffff;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #dce5f8;
    color: #1c2740;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #2f5cc8;
    color: #ffffff;
}
QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #eef1f8;
    border: 1px dashed #b8c4dc;
    color: #8899bb;
}
/* Nach Stylesheet auf dem SpinBox selbst zeichnet Qt keine nativen Pfeile mehr.
   SVG-Dreiecke statt border-Tricks (die unter Windows oft als Balken enden). */
QSpinBox, QDoubleSpinBox {
    padding-right: 22px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #c8d3ec;
    background: #eef1f8;
    border-top-right-radius: 6px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #c8d3ec;
    background: #eef1f8;
    border-bottom-right-radius: 6px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #dce4f5;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(SPIN_UP_PLACEHOLDER);
    width: 10px;
    height: 6px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(SPIN_DOWN_PLACEHOLDER);
    width: 10px;
    height: 6px;
}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {
    image: url(SPIN_UP_OFF_PLACEHOLDER);
}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {
    image: url(SPIN_DOWN_OFF_PLACEHOLDER);
}
QCheckBox {
    color: #1c2740;
    background: transparent;
    spacing: 8px;
    padding-top: 2px;
    padding-bottom: 2px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #5a7dd6;
    border-radius: 3px;
    background: #fbfcff;
}
QCheckBox::indicator:checked {
    background: #2f5cc8;
    border: 1px solid #2f5cc8;
}
QCheckBox::indicator:disabled {
    border: 1px solid #c9d5f0;
    background: #eef1f8;
}
QCheckBox:disabled {
    color: #8899bb;
}
QPushButton {
    background: #2f5cc8;
    color: #ffffff;
    border: 0;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: #234fb8;
}
QPushButton:pressed {
    background: #1d449f;
}
QPushButton:disabled {
    background: #a7b4d7;
    color: #eef2ff;
}
QScrollArea {
    border: none;
    background: #f4f6fb;
}
QScrollArea > QWidget {
    background: #f4f6fb;
}
QTableWidget, QTreeWidget, QListWidget {
    background: #ffffff;
    alternate-background-color: #f0f4f8;
    color: #1c2740;
    border: 1px solid #c8d3ec;
    border-radius: 6px;
    outline: none;
}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background: #d6e6f5;
    color: #1c2740;
}
QHeaderView::section {
    background: #e9eefb;
    color: #2b3f72;
    border: 1px solid #c8d3ec;
    padding: 6px 8px;
    font-weight: 600;
}
/* Vorschau-Flächen (Cover / Assets) bleiben dunkel */
QLabel#kdpCoverPreview, QLabel#assetManagerPreview {
    background: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 8px;
}
QWidget#kdpCoverLeftHost, QScrollArea#kdpCoverLeftScroll,
QScrollArea#kdpCoverLeftScroll > QWidget {
    background: #f4f6fb;
}
/* SizeGrip sichtbar (nicht weiß auf weiß) — nur Cover-Designer */
QDialog#kdpCoverDialog QSizeGrip {
    width: 10px;
    height: 10px;
    background-color: #fca5a5;
    border: 1px solid #ef4444;
    border-radius: 1px;
}
/* Log bleibt dunkel */
QPlainTextEdit#qtLog {
    background: #0f1628;
    color: #d8e1ff;
    border: 1px solid #27385f;
    font-family: Consolas, "Courier New", monospace;
    font-size: 10pt;
}
"""

PITU_CORE_STYLESHEET = (
    PITU_CORE_STYLESHEET
    .replace("SPIN_UP_PLACEHOLDER", _SPIN_UP)
    .replace("SPIN_DOWN_PLACEHOLDER", _SPIN_DOWN)
    .replace("SPIN_UP_OFF_PLACEHOLDER", _SPIN_UP_OFF)
    .replace("SPIN_DOWN_OFF_PLACEHOLDER", _SPIN_DOWN_OFF)
)

# Abwärtskompatibler Alias (früher dialog-scoped).
PITU_DIALOG_STYLESHEET = PITU_CORE_STYLESHEET

__all__ = [
    "PITU_CORE_STYLESHEET",
    "PITU_DIALOG_STYLESHEET",
    "SPIN_ARROW_UP",
    "SPIN_ARROW_DOWN",
    "SPIN_ARROW_UP_DISABLED",
    "SPIN_ARROW_DOWN_DISABLED",
]
