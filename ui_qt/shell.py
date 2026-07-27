"""Qt-Hauptfenster — Phase 3: Menü, Session, Recent Projects."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional

from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtCore import Qt
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
from ui_qt.studio_bridge import UiScheduler
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
        self._ui_scheduler = UiScheduler(self)
        self.setWindowTitle(self._window_title_from_version())
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
            try:
                self.as_export_studio()._fire_plugin_hooks_after_book_import(
                    import_path=facade.import_path
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                facade.log(f"after_book_import Hook: {exc}", "warning")

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
        self.book_combo.setMinimumWidth(420)
        self.book_combo.setMaxVisibleItems(20)
        self.book_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.book_combo.setMinimumContentsLength(36)
        self.book_combo.currentIndexChanged.connect(self._on_book_chosen)
        top.addWidget(self.book_combo, stretch=1)
        copy_btn = QPushButton("📋")
        copy_btn.setFixedWidth(36)
        copy_btn.setToolTip("Projektnamen in die Zwischenablage kopieren")
        copy_btn.clicked.connect(self._copy_book_name_to_clipboard)
        top.addWidget(copy_btn)
        pdfs_btn = QPushButton("🗺️")
        pdfs_btn.setFixedWidth(36)
        pdfs_btn.setToolTip("Fertige PDFs dieses Buchs")
        pdfs_btn.clicked.connect(self._open_finished_pdfs)
        top.addWidget(pdfs_btn)
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self._refresh_book_list)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

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

    def _copy_book_name_to_clipboard(self) -> None:
        book = self._facade.current_book
        if book is None:
            data = self.book_combo.currentData()
            book = Path(data) if data is not None else None
        if book is None:
            QMessageBox.information(self, "Zwischenablage", "Kein Buchprojekt gewählt.")
            return
        name = Path(book).name
        QGuiApplication.clipboard().setText(name)
        self.statusBar().showMessage(f"Projektname kopiert: {name}", 4000)
        self._facade.log(f"Projektname in Zwischenablage: {name}", "info")

    def _open_finished_pdfs(self) -> None:
        book = self._facade.current_book
        if book is None:
            data = self.book_combo.currentData()
            book = Path(data) if data is not None else None
        if book is None:
            QMessageBox.information(self, "Fertige PDFs", "Bitte zuerst ein Buchprojekt wählen.")
            return
        from ui_qt.dialogs.post_render_dialog import open_finished_pdfs_for_book

        open_finished_pdfs_for_book(self, Path(book), log=self._facade.log)

    def _refresh_book_list(self) -> None:
        prefer = self._facade.current_book
        self.book_combo.blockSignals(True)
        self.book_combo.clear()
        self._books = [
            b for b in discover_books() if not qt_session.is_ephemeral_book_path(b)
        ]
        self.book_combo.addItem("— Buch wählen —", None)
        for book in self._books:
            from tools.book_projects.label import read_display_name

            label = read_display_name(book)
            text = f"{label}  ·  {book.name}" if label else book.name
            self.book_combo.addItem(text, book)
            tip_idx = self.book_combo.count() - 1
            self.book_combo.setItemData(tip_idx, str(book), Qt.ItemDataRole.ToolTipRole)
        self.book_combo.blockSignals(False)
        self._facade.log(f"{len(self._books)} Buchprojekt(e) gefunden.", "info")
        target = prefer
        if target is None or qt_session.is_ephemeral_book_path(target):
            target = qt_session.pick_restorable_book()
        if target is not None:
            self._try_select_book(Path(target))

    def _restore_active_book(self) -> None:
        book = qt_session.pick_restorable_book()
        if book is not None:
            self._try_select_book(book)
            return
        self._facade.log(
            "Kein gültiges Buch in der Session (Pytest-/Temp-Pfade werden ignoriert).",
            "info",
        )

    def _apply_saved_geometry(self) -> None:
        state = qt_session.load_session()
        ui = state.get("ui_state") if isinstance(state, dict) else None
        geom = ui.get("window_geometry") if isinstance(ui, dict) else None
        parsed = qt_session.parse_geometry(str(geom)) if geom else None
        if parsed:
            w, h, x, y = parsed
            self.resize(w, h)
            self.move(x, y)
        self._ensure_window_fully_visible()

    def _ensure_window_fully_visible(self) -> None:
        """Zentriert das Fenster auf seinem Bildschirm, falls die (ggf. gespeicherte)
        Position es ganz oder teilweise außerhalb des aktuell verfügbaren
        Bildschirmbereichs platzieren würde - z. B. nach einem Monitor- oder
        Auflösungswechsel seit dem letzten Speichern der Session. Eine bewusst
        gewählte Position (z. B. auf einem zweiten Monitor) bleibt unangetastet,
        solange das Fenster dort vollständig sichtbar ist. Die Fenstergröße wird
        NICHT angetastet - `availableGeometry()` liefert unter Windows bei
        Multi-Monitor-/DPI-Skalierungs-Setups teils falsche (zu kleine) Werte,
        ein Verkleinern darauf hätte das Fenster unnötig schmal gemacht."""
        frame = self.frameGeometry()
        screen = QGuiApplication.screenAt(frame.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        if avail.contains(frame):
            return
        frame.moveCenter(avail.center())
        self.move(frame.topLeft())

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
        if qt_session.is_ephemeral_book_path(book):
            self._facade.log(
                f"Temporäres Test-Buch ignoriert: {book.name} "
                f"(stammt aus Pytest — bitte echtes Buch wählen).",
                "warning",
            )
            fallback = qt_session.pick_restorable_book()
            if fallback is not None and fallback.resolve() != book:
                self._try_select_book(fallback)
            return
        for i in range(self.book_combo.count()):
            data = self.book_combo.itemData(i)
            if data is not None and Path(data).resolve() == book:
                # Index setzen und immer laden (Signal kann ausbleiben)
                self.book_combo.blockSignals(True)
                self.book_combo.setCurrentIndex(i)
                self.book_combo.blockSignals(False)
                self._load_book(book)
                return
        # Nicht in der Discovery-Liste → nicht heimlich laden (führt zu „Band_T“-Chaos)
        self._facade.log(
            f"Buch nicht in der Liste (Suchpfade prüfen): {book.name}",
            "warning",
        )

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
        self.setWindowTitle(self._window_title_from_version())
        self.statusBar().showMessage(f"Geladen: {book}")
        self._persist_session()
        # Leere Struktur: nur Log/Status — kein Modal (besonders nicht beim Start)
        if not session.book_nodes:
            self.statusBar().showMessage(
                f"„{book.name}“: noch keine Kapitel in der Struktur.",
                8000,
            )
            self._facade.log(
                f"„{book.name}“ hat in _quarto.yml noch keine Kapitel "
                f"(chapters: []). Struktur rechts ist leer — Kapitel aus der "
                f"linken Liste hinzufügen oder anderes Projekt wählen.",
                "info",
            )
    def _save(self) -> bool:
        if self._session and self._session.save():
            self.statusBar().showMessage("Gespeichert.", 4000)
            self._persist_session()
            return True
        return False

    def schedule_ui(self, callback, delay: int = 0) -> None:
        self._ui_scheduler.post(callback, delay_ms=max(0, int(delay)))

    def _on_log(self, message: str, level: str) -> None:
        def _apply() -> None:
            self._log.appendPlainText(f"[{level}] {message}")
            self.statusBar().showMessage(message, 5000)

        self.schedule_ui(_apply)

    def _window_title_from_version(self) -> str:
        """Fenstertitel = Inhalt von ``version.txt`` (SSOT-Anzeigezeile)."""
        try:
            text = (repo_root() / "version.txt").read_text(encoding="utf-8").strip()
        except OSError:
            return "Quarto Book Studio"
        return text or "Quarto Book Studio"

    def _show_about(self) -> None:
        version = self._window_title_from_version()
        QMessageBox.about(
            self,
            "Über Book Studio (Qt)",
            f"{version}\n\n"
            "Quarto Book Studio — PySide6-UI.\n"
            "Aktives Buch siehe Dropdown und Statuszeile.",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._persist_session()
        self._facade.set_log_hook(None)
        super().closeEvent(event)
