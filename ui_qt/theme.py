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
QStatusBar {
    background-color: #e8eaee;
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
