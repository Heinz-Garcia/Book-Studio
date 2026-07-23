"""Qt-Hauptfenster — Phase 3: Menü, Session, Recent Projects."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.book_workspace import StructureSession, discover_books, repo_root
from ui_qt.command_host import CommandHost
from ui_qt.menu_builder import build_menu_bar
from ui_qt import qt_session
from ui_qt.widgets.structure_panel import StructurePanel

if TYPE_CHECKING:
    from ui_qt.facade import StudioFacade


class MainWindow(QMainWindow):
    def __init__(self, facade: "StudioFacade") -> None:
        super().__init__()
        self._facade = facade
        self._session: Optional[StructureSession] = None
        self._books: list[Path] = []
        self._commands = CommandHost(self)
        self.setWindowTitle("Quarto Book Studio (Qt)")
        self.resize(1200, 760)

        facade.set_log_hook(self._on_log)
        self._apply_saved_geometry()
        self.setMenuBar(
            build_menu_bar(
                self,
                resolve=self._commands.resolve,
                recent_builder=self._populate_recent_menu,
            )
        )
        self._build_central()
        self.statusBar().showMessage("Qt-UI bereit")
        facade.log("Qt-Shell gestartet.", "info")
        self._refresh_book_list()
        self._restore_active_book()
        if facade.import_path is not None:
            facade.log(f"Import-Pfad übergeben: {facade.import_path}", "info")
            self._try_select_book(Path(facade.import_path))

    def as_plugin_studio(self) -> SimpleNamespace:
        """Minimales studio-ähnliches Objekt für PluginExecutor."""
        return SimpleNamespace(
            current_book=self._facade.current_book,
            log=self._facade.log,
            root=self,
        )

    def as_export_studio(self):
        from ui_qt.studio_bridge import QtStudioBridge

        return QtStudioBridge(self)

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
            "Qt-UI (Default). Legacy-Tk: <code>python book_studio.py --ui tk</code> "
            "bzw. <code>BOOK_STUDIO_UI=tk</code>."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        self.structure = StructurePanel()
        layout.addWidget(self.structure, stretch=1)

        self._log = QPlainTextEdit()
        self._log.setObjectName("qtLog")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        layout.addWidget(self._log)

        self.setCentralWidget(central)

    def _populate_recent_menu(self, menu: QMenu) -> None:
        menu.clear()
        entries = qt_session.list_recent_books(current_book=self._facade.current_book)
        if not entries:
            act = menu.addAction("(noch keine – Buch wechseln speichert die Liste)")
            act.setEnabled(False)
            return
        for entry in entries:
            if entry.get("current"):
                act = menu.addAction(f"● {entry['label']} (aktuell)")
                act.setEnabled(False)
                continue
            path = entry["path"]
            act = menu.addAction(entry["label"])
            act.triggered.connect(lambda _checked=False, p=path: self._try_select_book(p))

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

    def _restore_active_book(self) -> None:
        state = qt_session.load_session()
        key = state.get("active_book_path")
        if not key:
            return
        book = qt_session.resolve_book_key(str(key))
        if book is not None:
            self._try_select_book(book)

    def _apply_saved_geometry(self) -> None:
        state = qt_session.load_session()
        ui = state.get("ui_state") if isinstance(state, dict) else None
        geom = ui.get("window_geometry") if isinstance(ui, dict) else None
        parsed = qt_session.parse_geometry(str(geom)) if geom else None
        if parsed:
            w, h, x, y = parsed
            self.resize(w, h)
            self.move(x, y)

    def _current_geometry_string(self) -> str:
        geo = self.geometry()
        return qt_session.geometry_string(geo.width(), geo.height(), geo.x(), geo.y())

    def _persist_session(self) -> None:
        try:
            qt_session.save_session(
                current_book=self._facade.current_book,
                geometry=self._current_geometry_string(),
            )
        except (OSError, TypeError, ValueError) as exc:
            self._facade.log(f"Session konnte nicht gespeichert werden: {exc}", "warning")

    def _try_select_book(self, book: Path) -> None:
        book = book.resolve()
        for i in range(self.book_combo.count()):
            data = self.book_combo.itemData(i)
            if data is not None and Path(data).resolve() == book:
                self.book_combo.setCurrentIndex(i)
                return
        self._load_book(book)

    def _on_book_chosen(self, index: int) -> None:
        data = self.book_combo.itemData(index)
        if data is None:
            self._session = None
            self._facade.current_book = None
            self.structure.set_session(None)
            self._persist_session()
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
        self._persist_session()

    def _save(self) -> bool:
        if self._session and self._session.save():
            self.statusBar().showMessage("Gespeichert.", 4000)
            self._persist_session()
            return True
        return False

    def _on_log(self, message: str, level: str) -> None:
        self._log.appendPlainText(f"[{level}] {message}")
        self.statusBar().showMessage(message, 5000)

    def _show_about(self) -> None:
        version = "—"
        try:
            version = (repo_root() / "version.txt").read_text(encoding="utf-8").strip()
        except OSError:
            pass
        QMessageBox.about(
            self,
            "Über Book Studio (Qt)",
            f"{version}\n\n"
            "PySide6-Migrationspfad — Phase 3.\n"
            "Siehe .doc/pyside6-migration-plan.md",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._persist_session()
        self._facade.set_log_hook(None)
        super().closeEvent(event)
