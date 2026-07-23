"""Minimales Qt-Theme (Phase 1 Stub)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

# Neutral, kein „AI-Lila“ — klarer Desktop-Look als Platzhalter.
_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #f5f6f8;
    color: #1a1d23;
    font-size: 13px;
}
QMenuBar {
    background-color: #e8eaee;
    spacing: 4px;
}
QMenuBar::item:selected {
    background-color: #d0d5de;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #9aa3b2;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
}
QMenu::item:selected {
    background-color: #d0d5de;
}
QMenu::separator {
    height: 1px;
    background: #c5cad3;
    margin: 4px 8px;
}
QStatusBar {
    background-color: #e8eaee;
}
QFrame#iconLegend {
    background-color: #eef1f5;
    border: 1px solid #c5cad3;
    border-radius: 4px;
    margin-top: 12px;
    min-width: 240px;
}
QLabel#iconLegendTitle {
    font-weight: 600;
    font-size: 14px;
    color: #1a1d23;
    padding-bottom: 2px;
}
QLabel#iconLegendLine {
    color: #334155;
    font-size: 13px;
}
QWidget#structureMidColumn QPushButton {
    font-size: 13px;
    padding: 6px 12px;
    min-height: 32px;
}
QLabel#structureColumnTitle {
    font-size: 13px;
    font-weight: 600;
    color: #1a1d23;
    padding-bottom: 0px;
}
QTreeWidget#structureTree {
    background-color: #ffffff;
    border: 1px solid #c5cad3;
    border-radius: 2px;
    show-decoration-selected: 1;
}
QTreeWidget#structureTree::item:selected {
    background-color: #d6e6f5;
    color: #1a1d23;
}
QDialog#bookProjectsDialog {
    background-color: #f5f6f8;
}
QDialog#bookProjectsDialog QTreeWidget {
    background-color: #ffffff;
    alternate-background-color: #f0f4f8;
    color: #1a1d23;
    border: 1px solid #c5cad3;
    border-radius: 4px;
    outline: none;
}
QDialog#bookProjectsDialog QTreeWidget::item {
    color: #1a1d23;
    padding: 4px 6px;
}
QDialog#bookProjectsDialog QTreeWidget::item:selected,
QDialog#bookProjectsDialog QTreeWidget::item:selected:active,
QDialog#bookProjectsDialog QTreeWidget::item:selected:!active {
    background-color: #d6e6f5;
    color: #1a1d23;
}
QDialog#bookProjectsDialog QTreeWidget::item:hover {
    background-color: #e8f0f8;
}
QFrame#bookProjectsSection {
    background-color: #ffffff;
    border: 1px solid #c5cad3;
    border-radius: 6px;
}
QLabel#bookProjectsSectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #1a1d23;
}
QLabel#bookProjectsHint {
    color: #5b6573;
    font-size: 12px;
}
QPushButton#bookProjectsPrimary {
    background-color: #2f5d9f;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton#bookProjectsPrimary:hover {
    background-color: #264a80;
}
QPushButton#bookProjectsDanger {
    color: #8b1e1e;
}
QDialog#skeletonEditorDialog {
    background-color: #f5f6f8;
}
QDialog#skeletonEditorDialog QTreeWidget {
    background-color: #ffffff;
    alternate-background-color: #f0f4f8;
    color: #1a1d23;
    border: 1px solid #c5cad3;
    border-radius: 4px;
    outline: none;
}
QDialog#skeletonEditorDialog QTreeWidget::item {
    color: #1a1d23;
    padding: 3px 6px;
}
QDialog#skeletonEditorDialog QTreeWidget::item:selected,
QDialog#skeletonEditorDialog QTreeWidget::item:selected:active,
QDialog#skeletonEditorDialog QTreeWidget::item:selected:!active {
    background-color: #d6e6f5;
    color: #1a1d23;
}
QDialog#skeletonEditorDialog QTreeWidget::item:hover {
    background-color: #e8f0f8;
}
QFrame#skeletonEditorSection {
    background-color: #ffffff;
    border: 1px solid #c5cad3;
    border-radius: 6px;
}
QLabel#skeletonEditorSectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #1a1d23;
}
QLabel#skeletonEditorHint {
    color: #5b6573;
    font-size: 12px;
}
QPushButton#skeletonEditorPrimary {
    background-color: #2f5d9f;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton#skeletonEditorPrimary:hover {
    background-color: #264a80;
}
QPlainTextEdit#qtLog {
    background-color: #1e2229;
    color: #d7dde8;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    border: 1px solid #c5cad3;
}
"""


def apply_theme(app: "QApplication") -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_STYLESHEET)
