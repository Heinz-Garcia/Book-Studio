"""Qt-Theme SSOT — El-Pitugrafo Look & Feel für die gesamte App."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ui_qt.pitugrafo_look import PITU_CORE_STYLESHEET

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

# App-spezifische Ergänzungen (ObjectNames / Hauptfenster-Struktur).
# Kernfarben/Checkboxen/Buttons kommen aus PITU_CORE_STYLESHEET.
_APP_EXTRAS = """
QMenuBar {
    background-color: #e9eefb;
    spacing: 4px;
    color: #1c2740;
}
QMenuBar::item:selected {
    background-color: #dce5f8;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #c8d3ec;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    color: #1c2740;
}
QMenu::item:selected {
    background-color: #dce5f8;
}
QMenu::separator {
    height: 1px;
    background: #c8d3ec;
    margin: 4px 8px;
}
QStatusBar {
    background-color: #e9eefb;
    color: #1c2740;
}
QFrame#iconLegend {
    background-color: #eef1f8;
    border: 1px solid #c8d3ec;
    border-radius: 6px;
    margin-top: 12px;
    min-width: 240px;
}
QLabel#iconLegendTitle {
    font-weight: 600;
    font-size: 14px;
    color: #1c2740;
    padding-bottom: 2px;
}
QLabel#iconLegendLine {
    color: #334b86;
    font-size: 13px;
}
QWidget#structureMidColumn QPushButton {
    background: #e8eaee;
    color: #1c2740;
    border: 1px solid #c5cad3;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 12px;
    min-height: 32px;
}
QWidget#structureMidColumn QPushButton:hover {
    background: #d8dde5;
    color: #1c2740;
}
QWidget#structureMidColumn QPushButton:pressed {
    background: #c5cad3;
    color: #1c2740;
}
QWidget#structureMidColumn QPushButton:disabled {
    background: #f0f1f4;
    color: #8899bb;
    border: 1px solid #d8dde5;
}
QLabel#structureColumnTitle {
    font-size: 13px;
    font-weight: 600;
    color: #1c2740;
    padding-bottom: 0px;
}
QTreeWidget#structureTree {
    background-color: #ffffff;
    border: 1px solid #c8d3ec;
    border-radius: 6px;
    show-decoration-selected: 1;
}
QTreeWidget#structureTree::item:selected {
    background-color: #d6e6f5;
    color: #1c2740;
}
QFrame#bookProjectsSection,
QFrame#skeletonEditorSection,
QFrame#assetManagerSection {
    background-color: #ffffff;
    border: 1px solid #c8d3ec;
    border-radius: 8px;
}
QLabel#bookProjectsSectionTitle,
QLabel#skeletonEditorSectionTitle,
QLabel#assetManagerSectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #334b86;
}
QLabel#bookProjectsHint,
QLabel#assetManagerHint {
    color: #5b6785;
    font-size: 12px;
}
QPushButton#bookProjectsDanger,
QPushButton#finishedPdfsDanger,
QPushButton#assetManagerDanger {
    background: #fef2f2;
    color: #8b1e1e;
    border: 1px solid #f3b3ab;
}
QPushButton#bookProjectsDanger:hover,
QPushButton#finishedPdfsDanger:hover,
QPushButton#assetManagerDanger:hover {
    background: #fee2e2;
}
QLabel#skeletonEditorStatus {
    color: #1a7f4b;
    font-weight: 600;
    padding-left: 8px;
}
QLabel#skeletonEditorFrontmatterWarning {
    background-color: #fdecea;
    color: #8a1f11;
    border: 1px solid #f3b3ab;
    border-left: 4px solid #c62828;
    border-radius: 6px;
    padding: 8px 10px;
    font-weight: 600;
}
QLabel#assetManagerBadgeUsed {
    background-color: #e9eefb;
    color: #2f5cc8;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#assetManagerBadgeFree {
    background-color: #e7f6ed;
    color: #1b6b3a;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#assetManagerBadgePool {
    background-color: #f1f0f7;
    color: #4b4568;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
}
QFrame#HelpBar {
    background-color: #eaf1fb;
    border: 1px solid #b9d3ef;
    border-left: 4px solid #2f5cc8;
    border-radius: 6px;
    margin-bottom: 8px;
}
QLabel#HelpBarIcon {
    font-size: 16pt;
    color: #2f5cc8;
}
QLabel#HelpBarText {
    color: #1c2740;
    font-size: 13px;
}
"""


def apply_theme(app: "QApplication") -> None:
    """Fusion + El-Pitugrafo-Kern + App-Extras — gilt für Hauptfenster und alle Dialoge."""
    app.setStyle("Fusion")
    app.setStyleSheet(PITU_CORE_STYLESHEET + "\n" + _APP_EXTRAS)
