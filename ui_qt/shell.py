"""Qt-Hauptfenster — Phase 2: Buchstruktur-Trees."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.book_workspace import StructureSession, discover_books
from ui_qt.widgets.structure_panel import StructurePanel

if TYPE_CHECKING:
    from ui_qt.facade import StudioFacade


class MainWindow(QMainWindow):
    def __init__(self, facade: "StudioFacade") -> None:
        super().__init__()
        self._facade = facade
        self._session: Optional[StructureSession] = None
        self._books: list[Path] = []
        self.setWindowTitle("Quarto Book Studio (Qt) — Phase 2")
        self.resize(1200, 760)

        facade.set_log_hook(self._on_log)
        self._build_menu()
        self._build_central()
        self.statusBar().showMessage("Qt-UI Phase 2 — Buchstruktur")

        facade.log("Qt-Shell gestartet (Phase 2 Buchstruktur).", "info")
        self._refresh_book_list()
        if facade.import_path is not None:
            facade.log(f"Import-Pfad übergeben: {facade.import_path}", "info")
            self._try_select_book(Path(facade.import_path))

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Datei")

        reload_action = QAction("Bücher neu laden", self)
        reload_action.triggered.connect(self._refresh_book_list)
        file_menu.addAction(reload_action)

        save_action = QAction("Struktur speichern", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save)
        file_menu.addAction(save_action)
        file_menu.addSeparator()

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

        top = QHBoxLayout()
        top.addWidget(QLabel("Buchprojekt:"))
        self.book_combo = QComboBox()
        self.book_combo.setMinimumWidth(360)
        self.book_combo.currentIndexChanged.connect(self._on_book_chosen)
        top.addWidget(self.book_combo, stretch=1)
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self._refresh_book_list)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        hint = QLabel(
            "Phase 2: Einrücken / Ausrücken / Hoch / Runter, Drag&Drop in der Buchstruktur, "
            "Speichern → <code>_quarto.yml</code>. Undo: Strg+Z."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        self.structure = StructurePanel()
        layout.addWidget(self.structure, stretch=1)

        self._log = QPlainTextEdit()
        self._log.setObjectName("qtLog")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        layout.addWidget(self._log)

        self.setCentralWidget(central)

    def _refresh_book_list(self) -> None:
        current = self.book_combo.currentData()
        self.book_combo.blockSignals(True)
        self.book_combo.clear()
        self._books = discover_books()
        self.book_combo.addItem("— Buch wählen —", None)
        for book in self._books:
            self.book_combo.addItem(book.name, book)
        self.book_combo.blockSignals(False)
        self._facade.log(f"{len(self._books)} Buchprojekt(e) gefunden.", "info")
        if current is not None:
            self._try_select_book(Path(current))

    def _try_select_book(self, book: Path) -> None:
        book = book.resolve()
        for i in range(self.book_combo.count()):
            data = self.book_combo.itemData(i)
            if data is not None and Path(data).resolve() == book:
                self.book_combo.setCurrentIndex(i)
                return
        # Nicht in der Liste → trotzdem laden
        self._load_book(book)

    def _on_book_chosen(self, index: int) -> None:
        data = self.book_combo.itemData(index)
        if data is None:
            self._session = None
            self._facade.current_book = None
            self.structure.set_session(None)
            return
        self._load_book(Path(data))

    def _load_book(self, book: Path) -> None:
        session = StructureSession(book, log=self._facade.log)
        try:
            session.load()
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            self._facade.log(f"Laden fehlgeschlagen: {exc}", "error")
            return
        self._session = session
        self._facade.current_book = book
        self.structure.set_session(session)
        self.setWindowTitle(f"Quarto Book Studio (Qt) — {book.name}")
        self.statusBar().showMessage(f"Geladen: {book}")

    def _save(self) -> None:
        if self._session and self._session.save():
            self.statusBar().showMessage("Gespeichert.", 4000)

    def _on_log(self, message: str, level: str) -> None:
        self._log.appendPlainText(f"[{level}] {message}")
        self.statusBar().showMessage(message, 5000)

    def _show_about(self) -> None:
        self._facade.log(
            "PySide6-Migration Phase 2 — siehe .doc/pyside6-migration-plan.md",
            "info",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._facade.set_log_hook(None)
        super().closeEvent(event)
