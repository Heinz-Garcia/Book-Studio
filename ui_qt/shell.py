"""Qt-Hauptfenster (Phase 1: leere Shell + Menü-Stub)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ui_qt.facade import StudioFacade


class MainWindow(QMainWindow):
    def __init__(self, facade: "StudioFacade") -> None:
        super().__init__()
        self._facade = facade
        self.setWindowTitle('Quarto Book Studio (Qt) — Phase 1')
        self.resize(1100, 700)

        facade.set_log_hook(self._on_log)
        self._build_menu()
        self._build_central()
        self.statusBar().showMessage("Qt-UI aktiv (BOOK_STUDIO_UI=qt / --ui qt)")

        facade.log("Qt-Shell gestartet (Phase 1 Fundament).", "info")
        if facade.import_path is not None:
            facade.log(f"Import-Pfad übergeben: {facade.import_path}", "info")

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Datei")
        quit_action = QAction("Beenden", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("&Hilfe")
        about_action = QAction("Über Qt-Migration…", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_central(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        hint = QLabel(
            "<b>Book Studio — Qt-Migrations-Shell</b><br/>"
            "Phase 1: Fundament. Buchstruktur, Menüs und Dialoge folgen in späteren Phasen.<br/>"
            "Tk-UI: Standardstart ohne Flag. Qt-UI: <code>BOOK_STUDIO_UI=qt</code> oder "
            "<code>python book_studio.py --ui qt</code>."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QLabel("Verfügbare Dateien\n(Platzhalter)")
        left.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        left.setStyleSheet("background:#fff; border:1px solid #c5cad3; padding:8px;")
        right = QLabel("Buchstruktur\n(Platzhalter)")
        right.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right.setStyleSheet("background:#fff; border:1px solid #c5cad3; padding:8px;")
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        self._log = QPlainTextEdit()
        self._log.setObjectName("qtLog")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        layout.addWidget(self._log)

        self.setCentralWidget(central)

    def _on_log(self, message: str, level: str) -> None:
        self._log.appendPlainText(f"[{level}] {message}")
        self.statusBar().showMessage(message, 5000)

    def _show_about(self) -> None:
        self._facade.log(
            "PySide6-Migrationspfad — siehe .doc/pyside6-migration-plan.md",
            "info",
        )
        self.statusBar().showMessage("Siehe Log / Migrationsplan.", 5000)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — Qt API
        self._facade.set_log_hook(None)
        super().closeEvent(event)
