"""Qt-Hauptfenster — Phase 3: Menü, Session, Recent Projects."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional

from PySide6.QtGui import QCloseEvent, QGuiApplication, QShowEvent
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui_qt.book_workspace import StructureSession, discover_books, repo_root
from ui_qt.command_host import CommandHost
from ui_qt.menu_builder import build_menu_bar
from ui_qt import qt_session
from ui_qt.studio_bridge import UiScheduler
from ui_qt.widgets.structure_panel import StructurePanel
from ui_qt.widgets.work_path_bar import WorkPathBar
from services.work_path import assess_work_path, gate_action
from ui_qt.work_path_guidance import (
    go_label_for_action,
    prompt_need_book,
    prompt_redirect_stage,
)

if TYPE_CHECKING:
    from ui_qt.facade import StudioFacade

# Mittelspalte: drei Button-Zeilen weniger (Speichern/Laden, Einrücken×2, Ausrücken×2).
_MID_COLUMN_COMPACT_HEIGHT_DELTA = 126
# Einmalige Verbreiterung: Fenster +240 (Mitte +120, links/rechts je +60).
_WINDOW_WIDTH_BOOST = 240
_DEFAULT_WINDOW_WIDTH = 1200 + _WINDOW_WIDTH_BOOST
_DEFAULT_WINDOW_HEIGHT = 760 - _MID_COLUMN_COMPACT_HEIGHT_DELTA
_MIN_WINDOW_HEIGHT = 520
#: Vertikaler Split Struktur/Log: Anteil des Logs (0–1). Eingeklappte
#: Flächen erhöhen den Log-Anteil — der Platz wandert dorthin, nicht in
#: leeren Mittelspalten-Stretch.
_LOG_SPLIT_RATIO_BASE = 0.22
_LOG_SPLIT_EXTRA_WORK_PATH = 0.08
_LOG_SPLIT_EXTRA_ICON_LEGEND = 0.18
_LOG_SPLIT_RATIO_MAX = 0.55
_UI_WORK_PATH_COLLAPSED = "work_path_collapsed"
_UI_ICON_LEGEND_COLLAPSED = "icon_legend_collapsed"


class MainWindow(QMainWindow):
    def __init__(self, facade: "StudioFacade") -> None:
        super().__init__()
        self._facade = facade
        self._session: Optional[StructureSession] = None
        self._books: list[Path] = []
        self._commands = CommandHost(self)
        self._ui_scheduler = UiScheduler(self)
        self._pending_ui_state_updates: dict[str, object] = {}
        self.setWindowTitle(self._window_title_from_version())
        self.resize(_DEFAULT_WINDOW_WIDTH, _DEFAULT_WINDOW_HEIGHT)

        facade.set_log_hook(self._on_log)
        self._apply_saved_geometry()
        self._rebuild_menu_bar()
        self._build_central()
        self.statusBar().showMessage("Qt-UI bereit")
        facade.log("Qt-Shell gestartet.", "info")
        self._refresh_book_list()
        if facade.activate_book is not None or facade.import_path is not None:
            # Bridge-Import: richtiges Arbeitsbuch aktivieren — NICHT zuerst
            # die Session (z. B. Brustkrebs) laden, sonst landet Provenance falsch.
            select_path = facade.activate_book or facade.import_path
            assert select_path is not None
            facade.log(f"Import-Pfad übergeben: {facade.import_path or select_path}", "info")
            if facade.activate_book is not None:
                facade.log(f"Arbeitsbuch aktivieren: {facade.activate_book}", "info")
            selected = self._try_select_book(Path(select_path))
            if selected:
                try:
                    # Provenance/Hooks: Roh-Lieferung (inbox), falls vorhanden
                    hook_source = facade.import_path or select_path
                    self.as_export_studio()._fire_plugin_hooks_after_book_import(
                        import_path=hook_source
                    )
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    facade.log(f"after_book_import Hook: {exc}", "warning")
            else:
                facade.log(
                    "Import-Buch konnte nicht aktiviert werden — "
                    "Provenance-Hook übersprungen.",
                    "warning",
                )
                self._restore_active_book()
        else:
            self._restore_active_book()
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

        # Eine Zeile: links Buchprojekt (50%), rechts Suche (50%)
        top = QHBoxLayout()
        top.setSpacing(12)

        book_half = QWidget()
        book_row = QHBoxLayout(book_half)
        book_row.setContentsMargins(0, 0, 0, 0)
        book_row.setSpacing(6)
        book_row.addWidget(QLabel("Buchprojekt:"))
        self.book_combo = QComboBox()
        self.book_combo.setMinimumWidth(140)
        self.book_combo.setMaxVisibleItems(20)
        self.book_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.book_combo.setMinimumContentsLength(14)
        self.book_combo.currentIndexChanged.connect(self._on_book_chosen)
        book_row.addWidget(self.book_combo, stretch=1)
        copy_btn = QPushButton("📋")
        copy_btn.setFixedWidth(36)
        copy_btn.setToolTip("Projektnamen in die Zwischenablage kopieren")
        copy_btn.clicked.connect(self._copy_book_name_to_clipboard)
        book_row.addWidget(copy_btn)
        pdfs_btn = QPushButton("🗺️")
        pdfs_btn.setFixedWidth(36)
        pdfs_btn.setToolTip("Ablegen — Render-Archiv für dieses Buch")
        pdfs_btn.clicked.connect(self._open_finished_pdfs)
        book_row.addWidget(pdfs_btn)
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self._refresh_book_list)
        book_row.addWidget(refresh_btn)
        top.addWidget(book_half, stretch=1)

        self.structure = StructurePanel(
            icon_legend_collapsed=self._load_icon_legend_collapsed(),
        )
        self.structure.icon_legend_collapsed_changed.connect(
            self._on_icon_legend_collapsed_changed
        )
        self.structure.structure_changed.connect(self._refresh_work_path)
        top.addWidget(self.structure.search_bar, stretch=1)
        layout.addLayout(top)

        self.work_path = WorkPathBar(
            on_next=self._work_path_next,
            on_pipeline=self._run_studio_pipeline,
            on_refresh=self._refresh_work_path,
            on_stage=self._work_path_run_action,
            on_collapsed_changed=self._on_work_path_collapsed_changed,
            collapsed=self._load_work_path_collapsed(),
        )
        layout.addWidget(self.work_path)

        self._restore_banner = QWidget()
        self._restore_banner.setObjectName("restoredSourceBanner")
        banner_row = QHBoxLayout(self._restore_banner)
        banner_row.setContentsMargins(0, 0, 0, 0)
        self._restore_banner_label = QLabel("")
        self._restore_banner_label.setWordWrap(True)
        self._restore_banner_label.setStyleSheet(
            "background:#fef3c7; color:#78350f; padding:6px 10px; border-radius:4px;"
        )
        banner_row.addWidget(self._restore_banner_label, stretch=1)
        banner_dismiss = QPushButton("✕")
        banner_dismiss.setFixedWidth(28)
        banner_dismiss.setToolTip("Hinweis ausblenden")
        banner_dismiss.clicked.connect(self.clear_restored_source_banner)
        banner_row.addWidget(banner_dismiss)
        self._restore_banner.setVisible(False)
        layout.addWidget(self._restore_banner)

        self._main_split = QSplitter(Qt.Orientation.Vertical)
        self._main_split.setObjectName("mainStructureLogSplit")
        self._main_split.setChildrenCollapsible(False)
        self._main_split.addWidget(self.structure)

        self._log = QPlainTextEdit()
        self._log.setObjectName("qtLog")
        self._log.setReadOnly(True)
        # Kein maximumHeight: der Splitter bestimmt die Höhe.
        self._log.setMinimumHeight(80)
        self._main_split.addWidget(self._log)
        self._main_split.setStretchFactor(0, 3)
        self._main_split.setStretchFactor(1, 1)
        layout.addWidget(self._main_split, stretch=1)

        self.setCentralWidget(central)
        self._refresh_work_path()

    def _rebuild_menu_bar(self) -> None:
        mode = qt_session.resolve_ui_mode()
        self.setMenuBar(
            build_menu_bar(
                self,
                resolve=self._commands.resolve,
                recent_builder=self._populate_recent_menu,
                ui_mode=mode,
            )
        )

    def toggle_ui_mode(self) -> None:
        """Wechselt geführt ↔ Werkstatt und baut die Menüleiste neu."""
        current = qt_session.resolve_ui_mode()
        nxt = "workshop" if current == "guided" else "guided"
        qt_session.set_ui_mode(nxt)
        self._rebuild_menu_bar()
        label = "geführt" if nxt == "guided" else "Werkstatt"
        self.statusBar().showMessage(f"Einstiegsmodus: {label}", 5000)
        self._facade.log(
            f"Einstiegsmodus: {label} "
            f"({'Studio-Wartung / Buch-Werkzeuge' if nxt == 'guided' else 'Tools / Plugins'}).",
            "info",
        )

    def focus_work_path_bar(self) -> None:
        """Nach Tool-Schließen: Hauptfenster und Arbeitsweg-Leiste in den Fokus."""
        try:
            self.raise_()
            self.activateWindow()
            bar = getattr(self, "work_path", None)
            if bar is not None:
                bar.setFocus(Qt.FocusReason.OtherFocusReason)
                primary = getattr(bar, "_primary_cta", None)
                if primary is not None and primary.isEnabled():
                    primary.setFocus(Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            pass

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
            from ui_qt.work_path_guidance import warn_need_book

            warn_need_book(
                self,
                title="Zwischenablage",
                message=(
                    "Kein Buchprojekt gewählt.\n\n"
                    "Stufe G: zuerst ein Buch wählen, dann den Namen kopieren."
                ),
            )
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
            from ui_qt.work_path_guidance import warn_need_book

            warn_need_book(
                self,
                title="PDF Manager",
                message=(
                    "Kein Buchprojekt gewählt.\n\n"
                    "Stufe G: zuerst ein Buch wählen, dann den PDF Manager öffnen."
                ),
            )
            return
        from ui_qt.dialogs.post_render_dialog import open_finished_pdfs_for_book

        open_finished_pdfs_for_book(self, Path(book), log=self._facade.log)

    def _open_current_export_pdf(self) -> None:
        """Neueste Export-PDF des aktiven Buchs öffnen (kein Render)."""
        book = self._facade.current_book
        if book is None:
            from ui_qt.work_path_guidance import warn_need_book

            warn_need_book(
                self,
                title="Export-PDF",
                message=(
                    "Kein Buchprojekt gewählt.\n\n"
                    "Stufe G: zuerst ein Buch wählen."
                ),
            )
            return
        try:
            from tools.live_preview.preview_render import newest_output_pdf
            from tools.mapping_manager.actions import open_path

            pdf = newest_output_pdf(Path(book))
        except (ImportError, OSError, TypeError, ValueError):
            pdf = None
        if pdf is not None and Path(pdf).is_file():
            open_path(Path(pdf))
            self._facade.log(f"Export-PDF geöffnet: {Path(pdf).name}", "info")
            self.statusBar().showMessage(f"PDF geöffnet: {Path(pdf).name}", 4000)
            return
        self._facade.log(
            "Keine Export-PDF gefunden — PDF Manager öffnen.", "warning"
        )
        self._open_finished_pdfs()

    def _ask_render_when_pdf_exists(self) -> str:
        """Bei grünem Render: Öffnen, Neu rendern oder Abbruch.

        Rückgabe: ``\"open\"`` | ``\"render\"`` | ``\"cancel\"``.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Render")
        box.setText("Es liegt bereits eine Export-PDF vor.")
        box.setInformativeText("Was möchten Sie tun?")
        btn_render = box.addButton(
            "Neu rendern…", QMessageBox.ButtonRole.AcceptRole
        )
        btn_open = box.addButton(
            "PDF öffnen", QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(btn_render)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_render:
            return "render"
        if clicked is btn_open:
            return "open"
        return "cancel"

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
        # Beim Bridge-Import nicht hier die alte Session aktivieren —
        # der Import-Pfad wird danach gezielt geladen.
        if self._facade.import_path is not None or self._facade.activate_book is not None:
            return
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
        if not isinstance(ui, dict):
            ui = {}
        geom = ui.get("window_geometry")
        parsed = qt_session.parse_geometry(str(geom)) if geom else None
        if parsed:
            w, h, x, y = parsed
            if not ui.get("mid_column_compact_applied"):
                h = max(_MIN_WINDOW_HEIGHT, h - _MID_COLUMN_COMPACT_HEIGHT_DELTA)
                self._pending_ui_state_updates["mid_column_compact_applied"] = True
            if not ui.get("window_width_boost_240_applied"):
                w = w + _WINDOW_WIDTH_BOOST
                self._pending_ui_state_updates["window_width_boost_240_applied"] = True
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
            updates = self._pending_ui_state_updates or None
            qt_session.save_session(
                current_book=self._facade.current_book,
                geometry=self._current_geometry_string(),
                ui_state_updates=updates,
            )
            self._pending_ui_state_updates = {}
        except (OSError, TypeError, ValueError) as exc:
            self._facade.log(f"Session konnte nicht gespeichert werden: {exc}", "warning")

    def _try_select_book(self, book: Path) -> bool:
        book = book.resolve()
        if qt_session.is_ephemeral_book_path(book):
            self._facade.log(
                f"Temporäres Test-Buch ignoriert: {book.name} "
                f"(stammt aus Pytest — bitte echtes Buch wählen).",
                "warning",
            )
            fallback = qt_session.pick_restorable_book()
            if fallback is not None and fallback.resolve() != book:
                return self._try_select_book(fallback)
            return False
        for i in range(self.book_combo.count()):
            data = self.book_combo.itemData(i)
            if data is not None and Path(data).resolve() == book:
                # Index setzen und immer laden (Signal kann ausbleiben)
                self.book_combo.blockSignals(True)
                self.book_combo.setCurrentIndex(i)
                self.book_combo.blockSignals(False)
                self._load_book(book)
                return True
        # Nicht in der Discovery-Liste → nicht heimlich laden (führt zu „Band_T“-Chaos)
        self._facade.log(
            f"Buch nicht in der Liste (Suchpfade prüfen): {book.name}",
            "warning",
        )
        return False
    def show_restored_source_banner(self, text: str) -> None:
        """Persistenter Hinweis über der Kapitelstruktur: die gerade
        geladene Quelle ist ein wiederhergestellter Stand (siehe
        `ui_qt.dialogs.mapping_manager_dialog._restore_source_selected`),
        nicht der zuletzt bearbeitete. Bleibt sichtbar bis manuell
        ausgeblendet oder das Buch über die Dropdown-Liste gewechselt wird
        (siehe `_on_book_chosen`) -- Programm-interne Buchwechsel
        (`_try_select_book`, z. B. durch den Restore-Flow selbst) lassen ihn
        bewusst stehen."""
        self._restore_banner_label.setText(text)
        self._restore_banner.setVisible(True)

    def clear_restored_source_banner(self) -> None:
        self._restore_banner.setVisible(False)
        self._restore_banner_label.setText("")

    def _on_book_chosen(self, index: int) -> None:
        self.clear_restored_source_banner()
        data = self.book_combo.itemData(index)
        if data is None:
            self._session = None
            self._facade.current_book = None
            self.structure.set_session(None)
            self._persist_session()
            self._refresh_work_path()
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
        self._refresh_work_path()
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

    def _structure_paths_for_work_path(self) -> list[str] | None:
        session = getattr(self.structure, "_session", None)
        if session is None or getattr(session, "book_nodes", None) is None:
            return None
        from ui_qt import structure_ops as ops

        return ops.collect_paths(session.book_nodes)

    def _refresh_work_path(self) -> None:
        """Liest Stufen G–J aus dem aktiven Buch und aktualisiert die Leiste."""
        state = assess_work_path(
            self._facade.current_book,
            repo_root=repo_root(),
            structure_paths=self._structure_paths_for_work_path(),
        )
        self.work_path.apply_state(state)
        if state.summary:
            self.statusBar().showMessage(state.summary, 6000)

    def _load_work_path_collapsed(self) -> bool:
        return self._load_ui_flag(_UI_WORK_PATH_COLLAPSED)

    def _load_icon_legend_collapsed(self) -> bool:
        return self._load_ui_flag(_UI_ICON_LEGEND_COLLAPSED)

    def _load_ui_flag(self, key: str) -> bool:
        try:
            state = qt_session.load_session()
        except (OSError, ValueError, TypeError):
            return False
        ui = state.get("ui_state") if isinstance(state, dict) else None
        if not isinstance(ui, dict):
            return False
        return bool(ui.get(key))

    def _on_work_path_collapsed_changed(self, collapsed: bool) -> None:
        self._persist_ui_flag(_UI_WORK_PATH_COLLAPSED, collapsed)
        self._apply_log_split()

    def _on_icon_legend_collapsed_changed(self, collapsed: bool) -> None:
        self._persist_ui_flag(_UI_ICON_LEGEND_COLLAPSED, collapsed)
        self._apply_log_split()

    def _persist_ui_flag(self, key: str, value: bool) -> None:
        self._pending_ui_state_updates[key] = bool(value)
        try:
            qt_session.update_ui_state({key: bool(value)})
        except OSError:
            pass

    def _log_split_ratio(self) -> float:
        ratio = _LOG_SPLIT_RATIO_BASE
        if self.work_path.collapsed:
            ratio += _LOG_SPLIT_EXTRA_WORK_PATH
        if self.structure.icon_legend_collapsed:
            ratio += _LOG_SPLIT_EXTRA_ICON_LEGEND
        return min(_LOG_SPLIT_RATIO_MAX, ratio)

    def _apply_log_split(self) -> None:
        """Gibt freigewordenen Platz dem Log — nicht der Mittelspalte."""
        total = max(0, self._main_split.size().height())
        if total < 120:
            # Noch nicht layoutet — später erneut versuchen.
            self.schedule_ui(self._apply_log_split, delay=50)
            return
        log_h = max(80, int(total * self._log_split_ratio()))
        struct_h = max(120, total - log_h)
        self._main_split.setSizes([struct_h, log_h])

    def _work_path_next(self) -> None:
        state = assess_work_path(
            self._facade.current_book,
            repo_root=repo_root(),
            structure_paths=self._structure_paths_for_work_path(),
        )
        action = state.next_action_id
        if not action:
            if prompt_need_book(
                self,
                title="Arbeitsweg",
                message=(
                    "Kein nächster Schritt — bitte zuerst ein Buch wählen.\n\n"
                    "Stufe G: Bücher wählen."
                ),
            ):
                self._work_path_run_action("book_projects")
            return
        self._work_path_run_action(action)

    def _work_path_run_action(self, action: str, *, skip_gate: bool = False) -> None:
        """Führt die Aktion einer Arbeitsweg-Stufe aus (Menü-äquivalent)."""
        from services.work_path import StageKind
        from ui_qt.work_path_guidance import prompt_why_red

        state = assess_work_path(
            self._facade.current_book,
            repo_root=repo_root(),
            structure_paths=self._structure_paths_for_work_path(),
        )
        if not skip_gate:
            chip = next((c for c in state.checklist if c.action == action), None)
            if chip is not None and chip.kind == StageKind.BLOCKED:
                next_a = state.next_action_id or "book_projects"
                why = chip.detail or "Zuerst den hervorgehobenen Schritt."
                if prompt_why_red(
                    self,
                    title=f"Arbeitsweg — {chip.label}",
                    why=why,
                    go_label=go_label_for_action(next_a),
                ):
                    self._work_path_run_action(next_a, skip_gate=True)
                return

        if not skip_gate:
            gate = gate_action(
                action,
                self._facade.current_book,
                repo_root=repo_root(),
                structure_paths=self._structure_paths_for_work_path(),
            )
            if not gate.allowed:
                redirect = gate.redirect_action
                if redirect == "delivery_intake":
                    if prompt_why_red(
                        self,
                        title="Arbeitsweg",
                        why=gate.message,
                        go_label=go_label_for_action(redirect),
                    ):
                        self._work_path_run_action("delivery_intake", skip_gate=True)
                    return
                if redirect == "book_projects":
                    if prompt_need_book(self, title="Arbeitsweg", message=gate.message):
                        self._work_path_run_action("book_projects", skip_gate=True)
                    return
                if redirect:
                    if prompt_why_red(
                        self,
                        title="Arbeitsweg",
                        why=gate.message,
                        go_label=go_label_for_action(redirect),
                    ):
                        self._work_path_run_action(redirect, skip_gate=True)
                    return
                QMessageBox.information(self, "Arbeitsweg", gate.message or "Aktion blockiert.")
                return

        if action == "delivery_intake":
            self._accept_delivery_interactive()
            return
        if action == "book_projects":
            cb = self._commands.resolve("plugin:book_projects")
            if cb is not None:
                cb()
            else:
                from ui_qt.plugin_dispatch import run_plugin_qt

                if not run_plugin_qt("book_projects", self):
                    from plugins.book_projects import run as run_books

                    run_books(studio=self.as_export_studio(), parent=self)
            self._refresh_book_list()
            self._refresh_work_path()
            return
        if action == "open_quarto_config_editor":
            self._commands.open_quarto_config_editor()
            self._refresh_work_path()
            return
        if action == "open_rahmen_editor":
            self._commands.open_rahmen_editor()
            self._refresh_work_path()
            return
        if action == "open_kapitel_editor":
            self._commands.open_kapitel_editor()
            self._refresh_work_path()
            return
        if action == "markup_inventory":
            from ui_qt.dialogs.doclayout_markup_inventory_dialog import (
                open_markup_inventory_qt,
            )

            open_markup_inventory_qt(
                studio=self.as_export_studio(),
                parent=self,
                book_path=self._facade.current_book,
                focus_gaps=True,
            )
            self._refresh_work_path()
            return
        if action == "accept_kapitel_as_is":
            # Skip gehört in den GG-Dialog (türkiser Button), nicht als Solo-Modal.
            action = "gg_content_swap"
        if action in {
            "skeleton_populate",
            "gg_content_swap",
            "kdp_cover",
        }:
            cb = self._commands.resolve(f"plugin:{action}")
            if cb is not None:
                cb()
            else:
                from ui_qt.plugin_dispatch import run_plugin_qt

                run_plugin_qt(action, self)
            self._refresh_work_path()
            return
        if action == "render":
            # Grün: wählen — ansehen oder erneut rendern (nicht still nur öffnen).
            render_chip = next(
                (c for c in state.checklist if c.id == "render"), None
            )
            if render_chip is not None and render_chip.kind == StageKind.OK:
                choice = self._ask_render_when_pdf_exists()
                if choice == "open":
                    self._open_current_export_pdf()
                    return
                if choice != "render":
                    return
            self._commands.run_quarto_render()
            self._refresh_work_path()
            return
        if action == "publisher_compliance":
            cb = self._commands.resolve("plugin:publisher_compliance")
            if cb is not None:
                cb()
            else:
                from plugins.publisher_compliance import run as run_compliance

                run_compliance(studio=self.as_export_studio(), parent=self)
            # Gate I („gesehen“) setzt open_publisher_compliance_qt nur,
            # wenn der Dialog wirklich geöffnet wurde — nicht bei Early-Return.
            self._refresh_work_path()
            return
        if action == "mapping_manager":
            cb = self._commands.resolve("plugin:mapping_manager")
            if cb is not None:
                cb()
            else:
                self._open_finished_pdfs()
            self._refresh_work_path()
            return
        self._facade.log(f"Unbekannte Arbeitsweg-Aktion: {action}", "warning")

    def _accept_delivery_interactive(self) -> Optional[Path]:
        """F′: Lieferung wählen, materialisieren, Buch aktivieren. Rückgabe: Buchpfad."""
        from services.delivery_intake import (
            accept_delivery,
            gate_f_ok,
            list_actionable_deliveries,
            list_book_deliveries,
            list_delivery_candidates,
            newest_actionable_delivery,
        )
        from services.work_path import read_book_run
        from ui_qt.work_path_guidance import prompt_pick_delivery

        root = repo_root()
        book = self._facade.current_book
        actionable = list_actionable_deliveries(root, book)
        # Alle Läufe dieses Buchs (inkl. älter / bereits übernommen)
        candidates = list_book_deliveries(root, book)
        if not candidates:
            candidates = list_delivery_candidates(root)
        if not candidates:
            QMessageBox.information(
                self,
                "Lieferung übernehmen",
                "Keine Lieferung in der Inbox gefunden.\n\n"
                "GrammarGraph-Export nach production/inbox/ legen oder "
                "Bücher manuell wählen.",
            )
            return None

        recommended = newest_actionable_delivery(root, book)
        if recommended is None:
            recommended = candidates[0]

        recorded = None
        hint = ""
        if book is not None:
            try:
                data = read_book_run(Path(book))
                art = (
                    data.get("artifacts")
                    if isinstance(data.get("artifacts"), dict)
                    else {}
                )
                recorded = str((art or {}).get("delivery") or "").strip() or None
            except (OSError, TypeError, ValueError):
                recorded = None
            if actionable and gate_f_ok(Path(book)):
                newest = actionable[0]
                hint = (
                    f"Für dieses Buch gibt es einen neueren Lauf in der Inbox:\n"
                    f"  {newest.label}\n\n"
                    "Der empfohlene Eintrag ist vorausgewählt. "
                    "Einen älteren Stand können Sie trotzdem wählen "
                    "(Sicherheitsabfrage)."
                )
            elif actionable and len(candidates) > 1:
                hint = (
                    "Mehrere Läufe in der Inbox — empfohlen ist der neueste.\n"
                    "Einen älteren Stand können Sie trotzdem wählen "
                    "(Sicherheitsabfrage)."
                )

        chosen = prompt_pick_delivery(
            self,
            candidates,
            recommended=recommended,
            actionable=actionable,
            recorded_path=recorded,
            hint=hint,
        )
        if chosen is None:
            return None

        try:
            result = accept_delivery(chosen.path, repo=root)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(
                self,
                "Lieferung übernehmen",
                f"Übernahme fehlgeschlagen:\n{exc}",
            )
            return None

        self._facade.log(
            f"Lieferung übernommen: {chosen.path.name} -> {result.book_path.name}",
            "success",
        )
        self._refresh_book_list()
        self._try_select_book(result.book_path)
        self._refresh_work_path()
        return result.book_path

    def _run_studio_pipeline(self, *, from_delivery: bool = False) -> None:
        """Teilkette: optional F′ -> Smart-G′ -> Render -> Freigabe -> Archiv."""
        from pathlib import Path as _Path

        from services.studio_pipeline import (
            InterruptDecision,
            PipelineHooks,
            PipelineOptions,
            run_studio_chain,
        )
        from services.work_path import gate_action
        from ui_qt.work_path_guidance import (
            go_label_for_action,
            prompt_need_book,
            prompt_pipeline_interrupt,
            prompt_redirect_stage,
        )

        book = self._facade.current_book
        start_at = "delivery" if from_delivery else "skeleton"

        if from_delivery or book is None:
            accepted = self._accept_delivery_interactive()
            if accepted is None and book is None:
                return
            if accepted is not None:
                book = accepted

        gate = gate_action("studio_pipeline", book, repo_root=repo_root())
        if not gate.allowed:
            if gate.redirect_action == "delivery_intake":
                if prompt_redirect_stage(
                    self,
                    title="Teilkette",
                    message=gate.message,
                    go_label=go_label_for_action(gate.redirect_action),
                ):
                    self._work_path_run_action("delivery_intake")
                return
            if gate.redirect_action == "book_projects":
                if prompt_need_book(self, title="Teilkette", message=gate.message):
                    self._work_path_run_action("book_projects")
                return
            if gate.redirect_action and prompt_redirect_stage(
                self,
                title="Teilkette",
                message=gate.message,
                go_label=go_label_for_action(gate.redirect_action),
            ):
                self._work_path_run_action(gate.redirect_action)
            return

        assert book is not None
        book_path = _Path(book)

        def _log(msg: str, level: str = "info") -> None:
            self._facade.log(msg, level)

        def _export_opts() -> dict:
            bridge = self.as_export_studio()
            opts = dict(bridge.get_last_export_options() or {})
            if opts:
                return opts
            try:
                from session_state import read_session_state

                data = read_session_state(repo_root() / "session_state.json")
                raw = (data or {}).get("export_options") if isinstance(data, dict) else {}
                return dict(raw) if isinstance(raw, dict) else {}
            except (ImportError, OSError, TypeError, ValueError):
                return {}

        def _skeleton_profile() -> Optional[_Path]:
            try:
                from tools.skeleton.config import read_skeleton_settings
                from tools.skeleton.manifest import (
                    list_profiles,
                    resolve_library_root,
                    resolve_profile_dir,
                )

                root = repo_root()
                settings = read_skeleton_settings(root)
                library = resolve_library_root(
                    root, str(settings.get("library_path") or "tools/skeleton/library")
                )
                profiles = list_profiles(library)
                if not profiles:
                    return None
                name = str(settings.get("default_profile") or profiles[0])
                if name not in profiles:
                    name = profiles[0]
                return resolve_profile_dir(library, name)
            except (ImportError, OSError, TypeError, ValueError, KeyError):
                return None

        def _interrupt(outcome):
            decision = prompt_pipeline_interrupt(self, outcome)
            details = getattr(outcome, "details", None) or {}
            redirect = str(details.get("_open_redirect") or "").strip()
            if decision == InterruptDecision.ABORT and redirect:
                self._work_path_run_action(redirect, skip_gate=True)
            return decision

        def _retry(stage_id: str) -> None:
            if stage_id == "delivery":
                self._work_path_run_action("delivery_intake", skip_gate=True)
                return
            if stage_id == "render":
                self._commands.run_quarto_render()
                return
            if stage_id == "skeleton":
                cb = self._commands.resolve("plugin:skeleton_populate")
                if cb is not None:
                    cb()
                return
            if stage_id == "compliance":
                self._work_path_run_action("publisher_compliance", skip_gate=True)
                return
            if stage_id == "archive":
                self._work_path_run_action("mapping_manager", skip_gate=True)

        def _resolve_delivery(_book: _Path) -> Optional[_Path]:
            return None

        label = (
            "Teilkette ab Lieferung (F′ -> Render -> Freigabe -> Archiv)…"
            if from_delivery
            else "Teilkette gestartet (Skeleton -> Render -> Freigabe -> Archiv)…"
        )
        self._facade.log(label, "header")
        result = run_studio_chain(
            book_path,
            options=PipelineOptions(),
            hooks=PipelineHooks(
                log=_log,
                get_export_options=_export_opts,
                resolve_skeleton_profile=_skeleton_profile,
                on_interrupt=_interrupt,
                on_retry_stage=_retry,
                resolve_delivery=_resolve_delivery,
                repo_root=repo_root(),
            ),
            start_at=start_at,
        )
        level = {
            "passed": "success",
            "failed": "error",
            "aborted": "warning",
        }.get(result.status, "info")
        self._facade.log(
            f"Teilkette beendet: {result.status} — {result.message}",
            level,
        )
        self._refresh_work_path()

    def _save(self) -> bool:
        if self._session is None:
            return False
        from ui_qt.structure_snapshot import (
            default_structure_snapshot_label,
            prompt_structure_snapshot_label,
        )

        label = prompt_structure_snapshot_label(
            self,
            default=default_structure_snapshot_label(book_name=self._session.book_path),
            book_name=self._session.book_path,
            title="In Quarto speichern",
        )
        if label is None:
            return False
        if self._session.save(snapshot_label=label):
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
        from ui_qt.dialogs.about_dialog import show_about_dialog

        show_about_dialog(
            self,
            version_line=self._window_title_from_version(),
            repo=repo_root(),
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt-Vertrag
        super().showEvent(event)
        # Splitter kennt seine Höhe erst nach dem ersten Show.
        self.schedule_ui(self._apply_log_split, delay=0)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._persist_session()
        self._facade.set_log_hook(None)
        super().closeEvent(event)
