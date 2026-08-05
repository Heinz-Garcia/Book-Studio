"""PDF Manager — lesbare Liste der Render-Ausgaben zum aktiven Buch."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.book_projects.label import read_display_name
from tools.mapping_manager.actions import (
    delete_pdf,
    delete_source_archive,
    open_path,
    rename_pdf,
    restore_source,
    reveal_in_explorer,
)
from tools.mapping_manager.deploy import deploy_pdf, resolve_pdf_deploy_folder
from tools.mapping_manager.loader import load_renders, load_snapshots
from tools.mapping_manager.models import RenderView, SnapshotView, layout_profile_label
from tools.publish_map.store import read_map, remove_render, update_render_fields
from ui_qt.widgets.resize_grip import attach_resize_grip

_COL_DATE = 0
_COL_LAYOUT = 1
_COL_FILE = 2
_COL_NAME = 3
_COL_FORMAT = 4
_COL_STATUS = 5
_COL_SOURCE = 6

_SOURCE_DOT_AVAILABLE = "#16a34a"
_SOURCE_DOT_MISSING = "#dc2626"


class MappingManagerQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self.studio = studio
        self.setObjectName("finishedPdfsDialog")
        self.setWindowTitle("PDF Manager")
        self.setMinimumSize(1200, 640)
        self.resize(1360, 720)
        self._snapshots: list[SnapshotView] = []
        self._renders: list[RenderView] = []
        self._all_renders: list[RenderView] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel("PDF Manager")
        title_font = QFont(title.font())
        title_font.setPointSize(16)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        layout.addWidget(title)

        book_row = QHBoxLayout()
        book_row.addWidget(QLabel("Buch:"))
        self.book_combo = QComboBox()
        self.book_combo.setMinimumWidth(480)
        self.book_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.book_combo.setMinimumContentsLength(40)
        book_row.addWidget(self.book_combo, stretch=1)
        layout.addLayout(book_row)
        self._fill_book_combo()
        self.book_combo.currentIndexChanged.connect(self._on_book_combo_changed)

        row = QHBoxLayout()
        row.addWidget(QLabel("El Pitugrafo Quelle:"))
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.setMinimumWidth(420)
        self.snapshot_combo.currentIndexChanged.connect(self._on_snapshot_changed)
        row.addWidget(self.snapshot_combo, stretch=1)
        self.btn_production_folder = QPushButton("open production folder")
        self.btn_production_folder.setToolTip(
            "Öffnet den GrammarGraph-Export-Ordner dieser El Pitugrafo Quelle im Explorer"
        )
        self.btn_production_folder.clicked.connect(self._open_production_folder)
        row.addWidget(self.btn_production_folder)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._reload_snapshots)
        row.addWidget(refresh)
        layout.addLayout(row)

        filter_row = QHBoxLayout()
        self.empty_label = QLabel("")
        self.empty_label.setStyleSheet("color:#5b6573;")
        filter_row.addWidget(self.empty_label)
        filter_row.addStretch(1)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtern: Datum, Layout, Dateiname, Anzeigename…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMinimumWidth(300)
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Datum", "Layout", "Datei", "Anzeigename (optional)", "Format", "Status", "Quelle"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        # Sortierung per Klick auf Spaltenkopf. WICHTIG: waehrend _fill_table()
        # neu befuellt wird ausdruecklich kurz deaktiviert (siehe dort) - sonst
        # sortiert Qt bei jedem einzelnen setItem()-Aufruf live mit, wodurch
        # Zeilen unter der Schleife durcheinanderrutschen.
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionsMovable(True)
        header.setSortIndicatorShown(True)
        # Autosize: JEDE Spalte folgt automatisch ihrem tatsächlichen Inhalt
        # (kein manuelles Ziehen am Rand nötig, das u. a. über Remote Desktop
        # unzuverlässig sein kann). Bewusst KEINE Stretch-Spalte: eine lange
        # Anzeigename-Notiz würde sonst der Stretch-Spalte (z. B. "Datei")
        # den Platz wegnehmen und sie unlesbar zusammenquetschen. Reicht der
        # Platz insgesamt nicht, zeigt die Tabelle stattdessen einen
        # horizontalen Scrollbalken — nie eine gequetschte Spalte.
        for _col in (
            _COL_DATE, _COL_LAYOUT, _COL_FILE, _COL_NAME, _COL_FORMAT, _COL_STATUS, _COL_SOURCE,
        ):
            header.setSectionResizeMode(_col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table, stretch=1)

        self.path_label = QLabel("Doppelklick oder „Öffnen“: PDF anzeigen. Pfad erscheint hier.")
        self.path_label.setObjectName("finishedPdfsPath")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color:#5b6573; font-size:12px;")
        layout.addWidget(self.path_label)

        actions = QHBoxLayout()
        self.btn_open = QPushButton("Öffnen")
        self.btn_open.setObjectName("finishedPdfsPrimary")
        self.btn_open.setDefault(True)
        self.btn_open.clicked.connect(self._open_selected)
        actions.addWidget(self.btn_open)

        self.btn_name = QPushButton("Anzeigename…")
        self.btn_name.clicked.connect(self._edit_display_name)
        actions.addWidget(self.btn_name)

        self.btn_open_source = QPushButton("Quelle öffnen")
        self.btn_open_source.setToolTip(
            "Buchprojekt dieses Renders im Hauptfenster aktivieren (in situ, keine Kopie) "
            "— direkt weiterbearbeiten und neu rendern"
        )
        self.btn_open_source.clicked.connect(self._open_source_selected)
        actions.addWidget(self.btn_open_source)

        self.btn_reveal_source = QPushButton("Archiv-Quelle im Explorer")
        self.btn_reveal_source.setToolTip(
            "Read-only: zeigt den exakten Quellstand (Kapitel-Markdown, _quarto.yml, ...), "
            "der zu genau dieser PDF geführt hat — dauerhaft archiviert bei diesem Render. "
            "Nicht verfügbar für Renders von vor Einführung dieses Felds."
        )
        self.btn_reveal_source.clicked.connect(self._reveal_source_selected)
        actions.addWidget(self.btn_reveal_source)

        self.btn_reveal = QPushButton("PDF im Explorer")
        self.btn_reveal.setToolTip("Explorer öffnen und diese PDF-Datei markieren")
        self.btn_reveal.clicked.connect(self._reveal_selected)
        actions.addWidget(self.btn_reveal)

        self.btn_copy_path = QPushButton("Pfad kopieren")
        self.btn_copy_path.setToolTip(
            "Vollständigen Pfad inkl. Dateiname der markierten PDF(s) "
            "in die Zwischenablage kopieren (mehrere = eine Zeile je Datei)"
        )
        self.btn_copy_path.clicked.connect(self._copy_selected_path)
        actions.addWidget(self.btn_copy_path)

        self.btn_rename = QPushButton("Dateiname…")
        self.btn_rename.clicked.connect(self._rename_selected)
        actions.addWidget(self.btn_rename)

        self.btn_deploy = QPushButton("Copy to configured folder")
        self.btn_deploy.setToolTip(
            "Markierte PDF(s) in den konfigurierten Deploy-Ordner kopieren "
            "(Studio-Konfiguration: pdf_deploy_folder)"
        )
        self.btn_deploy.clicked.connect(self._deploy_selected)
        actions.addWidget(self.btn_deploy)

        actions.addStretch(1)
        self.btn_restore = QPushButton("Quelle wiederherstellen…")
        self.btn_restore.setObjectName("finishedPdfsDanger")
        self.btn_restore.setToolTip(
            "Überschreibt das lebende Buchprojekt mit dem archivierten Quellstand dieses "
            "Renders. Der aktuelle Stand wird davor automatisch gesichert."
        )
        self.btn_restore.clicked.connect(self._restore_source_selected)
        actions.addWidget(self.btn_restore)
        self.btn_delete = QPushButton("Löschen…")
        self.btn_delete.setObjectName("finishedPdfsDanger")
        self.btn_delete.clicked.connect(self._delete_selected)
        actions.addWidget(self.btn_delete)
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.accept)
        actions.addWidget(self.btn_close)
        # Platz rechts unten fuer den Resize-Griff in der Fenster-Ecke
        actions.addSpacing(26)

        # Sichtbarer Resize-Griff (diagonale Punkte) unten rechts
        self._size_grip = attach_resize_grip(self)
        layout.addLayout(actions)

        tip = QLabel(
            "Buch oben wählen (PDFs gehören immer zu einem Buch). "
            "Anzeigename = optionaler Merknamen — nicht Layout/BoD."
        )
        tip.setStyleSheet("color:#5b6573; font-size:12px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self._reload_snapshots()

    def _book(self) -> Path:
        data = self.book_combo.currentData() if hasattr(self, "book_combo") else None
        if data is not None:
            return Path(data)
        cur = getattr(self.studio, "current_book", None)
        if cur is not None:
            return Path(cur)
        raise RuntimeError("Kein Buch gewählt")

    def _fill_book_combo(self) -> None:
        from ui_qt.book_workspace import discover_books
        from ui_qt.qt_session import is_ephemeral_book_path

        books = [b for b in discover_books() if not is_ephemeral_book_path(b)]

        def sort_key(b: Path) -> tuple[int, str]:
            has = 0
            if (b / "bookconfig" / "publish_map.json").is_file():
                has = 0
            elif (b / "export" / "publish_renders").is_dir():
                has = 0
            else:
                has = 1
            return (has, b.name.casefold())

        books.sort(key=sort_key)
        current = None
        try:
            if getattr(self.studio, "current_book", None):
                current = Path(self.studio.current_book).resolve()
                if is_ephemeral_book_path(current):
                    current = None
        except OSError:
            current = None

        self.book_combo.blockSignals(True)
        self.book_combo.clear()
        select = 0
        for idx, book in enumerate(books):
            label = read_display_name(book)
            text = f"{label}  ·  {book.name}" if label else book.name
            # Bücher mit PDFs markieren
            if (book / "bookconfig" / "publish_map.json").is_file() or (
                book / "export" / "publish_renders"
            ).is_dir():
                text = f"📄 {text}"
            self.book_combo.addItem(text, book)
            self.book_combo.setItemData(idx, str(book), Qt.ItemDataRole.ToolTipRole)
            try:
                if current is not None and book.resolve() == current:
                    select = idx
            except OSError:
                pass
        self.book_combo.setCurrentIndex(select if books else -1)
        self.book_combo.blockSignals(False)
        if books:
            chosen = Path(self.book_combo.currentData())
            self.studio.current_book = chosen
            self._sync_host_book(chosen)

    def _sync_host_book(self, book: Path) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "_try_select_book"):
            try:
                parent._try_select_book(book)
            except (OSError, RuntimeError, TypeError, ValueError):
                pass

    def _on_book_combo_changed(self, _index: int = -1) -> None:
        data = self.book_combo.currentData()
        if data is None:
            return
        book = Path(data)
        self.studio.current_book = book
        self._sync_host_book(book)
        self._reload_snapshots()

    def _preferred_snapshot_index(self) -> int:
        if not self._snapshots:
            return 0
        try:
            data = read_map(self._book()) or {}
            active = str(data.get("active_snapshot_id") or "")
        except (OSError, TypeError, ValueError):
            active = ""
        if active:
            for idx, snap in enumerate(self._snapshots):
                if snap.id == active:
                    return idx
        return len(self._snapshots) - 1

    def _reload_snapshots(self) -> None:
        try:
            book = self._book()
        except RuntimeError:
            self._snapshots = []
            self._all_renders = []
            self._renders = []
            self.table.setRowCount(0)
            self.empty_label.setText("Kein Buch gewählt.")
            return
        previous_id = self.snapshot_combo.currentData()
        self._snapshots = load_snapshots(book)
        self.snapshot_combo.blockSignals(True)
        self.snapshot_combo.clear()
        for snap in self._snapshots:
            count = f" ({snap.render_count})" if snap.render_count else ""
            self.snapshot_combo.addItem(f"{snap.label}{count}", snap.id)
        try:
            data = read_map(book) or {}
            active = str(data.get("active_snapshot_id") or "")
        except (OSError, TypeError, ValueError):
            active = ""
        if active:
            for i in range(self.snapshot_combo.count()):
                if self.snapshot_combo.itemData(i) == active:
                    text = self.snapshot_combo.itemText(i)
                    if not text.startswith("★ "):
                        self.snapshot_combo.setItemText(i, f"★ {text}")
                    break
        self.snapshot_combo.blockSignals(False)
        if not self._snapshots:
            self._all_renders = []
            self._renders = []
            self.table.setRowCount(0)
            self.empty_label.setText("Keine El Pitugrafo Quelle — zuerst rendern (F5).")
            return
        target = 0
        if previous_id:
            for i, snap in enumerate(self._snapshots):
                if snap.id == previous_id:
                    target = i
                    break
            else:
                target = self._preferred_snapshot_index()
        else:
            target = self._preferred_snapshot_index()
        self.snapshot_combo.setCurrentIndex(target)
        self._on_snapshot_changed(target)

    def _on_snapshot_changed(self, _index: int = -1) -> None:
        snap_id = self.snapshot_combo.currentData()
        if not snap_id:
            self._all_renders = []
            self._renders = []
            self.table.setRowCount(0)
            self.empty_label.setText("")
            return
        self._all_renders = load_renders(self._book(), str(snap_id))
        self._apply_filter()

    def _current_snapshot(self) -> Optional[SnapshotView]:
        snap_id = self.snapshot_combo.currentData()
        if not snap_id:
            return None
        for snap in self._snapshots:
            if snap.id == snap_id:
                return snap
        return None

    def _open_production_folder(self) -> None:
        """Öffnet den GrammarGraph-Export-Ordner der gewählten
        Produktionslinie im Explorer (`SnapshotView.production_folder`,
        aus `snapshot["provenance"]["import_path"]` -- der tatsächliche
        Quellordner, jede Produktionslinie entsteht in der Praxis aus
        genau so einem GrammarGraph-Export)."""
        snap = self._current_snapshot()
        if snap is None:
            QMessageBox.information(self, "PDF Manager", "Bitte eine El Pitugrafo Quelle wählen.")
            return
        if not snap.production_folder:
            QMessageBox.information(
                self,
                "PDF Manager",
                "Für diese El Pitugrafo Quelle ist kein GrammarGraph-Quellordner hinterlegt.",
            )
            return
        folder = Path(snap.production_folder)
        if not folder.is_dir():
            box = QMessageBox(self)
            box.setWindowTitle("PDF Manager")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(f"Ordner nicht gefunden:\n{folder}")
            btn_ok = box.addButton(QMessageBox.StandardButton.Ok)
            btn_copy = box.addButton("copy folder to clipboard", QMessageBox.ButtonRole.ActionRole)
            box.setDefaultButton(btn_ok)
            box.exec()
            if box.clickedButton() is btn_copy:
                QApplication.clipboard().setText(str(folder))
            return
        try:
            reveal_in_explorer(folder)
        except OSError as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))

    def _apply_filter(self, _text: str = "") -> None:
        needle = self.filter_edit.text().strip().lower()
        if not needle:
            self._renders = list(self._all_renders)
        else:
            self._renders = []
            for r in self._all_renders:
                blob = " ".join(
                    [
                        r.notes,
                        r.pdf_name,
                        layout_profile_label(r.layout_profile),
                        r.format,
                        r.template,
                        r.at_display,
                    ]
                ).lower()
                if needle in blob:
                    self._renders.append(r)
        self._fill_table()

    def _fill_table(self) -> None:
        # Sortierung waehrend des Befuellens aus: sonst sortiert Qt bei jedem
        # einzelnen setItem()-Aufruf innerhalb der Schleife live mit, wodurch
        # Zeilen unter der Schleife durcheinanderrutschen (Spalte X von Zeile
        # A landet neben Spalte Y von Zeile B). Nach dem Befuellen wieder an.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._renders))
        total = len(self._all_renders)
        shown = len(self._renders)
        if total == 0:
            name = self._book().name
            self.empty_label.setText(
                f"Keine PDFs für „{name}“. "
                "Anderes Buch oben wählen — Einträge mit 📄 haben bereits Renders."
            )
            self.path_label.setText(
                "Tipp: Publish_IFJN_Brustkrebs_Gemma4_… wählen, wenn dort gerendert wurde."
            )
        elif shown == total:
            self.empty_label.setText(f"{total} Render — neueste zuerst")
        else:
            self.empty_label.setText(f"{shown} von {total} Render (Filter)")

        for row, render in enumerate(self._renders):
            layout_txt = layout_profile_label(render.layout_profile)
            # Anzeigename = nur vom Nutzer gesetzter Merknamen (notes), nie Layout
            name = render.notes.strip()
            name_display = name if name else ""
            source_available = (
                render.source_archive_path is not None and render.source_archive_path.is_dir()
            )
            vals = [
                render.at_display,
                layout_txt,
                render.pdf_name or "—",
                name_display,
                render.format or "—",
                "OK" if render.exists else "fehlt",
                "●",
            ]
            tip_parts = [
                f"Datei: {render.pdf_name}" if render.pdf_name else "",
                str(render.pdf_path) if render.pdf_path else "",
            ]
            if name:
                tip_parts.insert(0, f"Anzeigename: {name}")
            else:
                tip_parts.insert(0, "Kein Anzeigename — über „Anzeigename…“ setzen")
            tip = "\n".join(p for p in tip_parts if p)
            source_tip = (
                "Archivierter Quellstand vorhanden — Quelle im Explorer ansehen "
                "oder wiederherstellen möglich."
                if source_available
                else "Kein archivierter Quellstand (Render von vor Einführung dieses Felds) "
                "— nicht wiederherstellbar."
            )
            for col, text in enumerate(vals):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, render.id)
                item.setToolTip(source_tip if col == _COL_SOURCE else tip)
                if col == _COL_NAME and not name:
                    item.setForeground(Qt.GlobalColor.gray)
                    item.setText("(kein Merknamen)")
                if col == _COL_LAYOUT and layout_txt in ("", "—"):
                    item.setForeground(Qt.GlobalColor.gray)
                if col == _COL_STATUS and not render.exists:
                    item.setForeground(Qt.GlobalColor.darkRed)
                if col == _COL_SOURCE:
                    item.setForeground(
                        QColor(_SOURCE_DOT_AVAILABLE if source_available else _SOURCE_DOT_MISSING)
                    )
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        # Explizit statt nur auf die automatische ResizeToContents-Neuberechnung
        # zu vertrauen — stellt sicher, dass Breiten sofort nach dem Neu-Füllen
        # (z. B. nach Filterwechsel) zum aktuellen Inhalt passen.
        self.table.resizeColumnsToContents()
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        renders = self._selected_renders()
        if not renders:
            self.path_label.setText(
                "Doppelklick oder „Öffnen“: PDF anzeigen. Pfad erscheint hier."
            )
            return
        if len(renders) == 1:
            render = renders[0]
            status = "vorhanden" if render.exists else "Datei fehlt"
            self.path_label.setText(f"{render.pdf_path}  ({status})")
            return
        existing = sum(1 for r in renders if r.exists)
        self.path_label.setText(f"{len(renders)} PDFs ausgewählt ({existing} vorhanden).")

    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._renders):
            self.table.selectRow(row)
            self._open_selected()

    def _selected_renders(self) -> list[RenderView]:
        """Ausgewaehlte Renders — per ID aus dem Item-Data aufgeloest, NICHT
        per Zeilenindex in ``self._renders``: seit Spaltensortierung aktiv
        ist, weicht die sichtbare Zeilenreihenfolge von der Erzeugungs-
        reihenfolge ab (Qt sortiert nur die Anzeige, nicht die Liste)."""
        by_id = {r.id: r for r in self._renders}
        rows = sorted(idx.row() for idx in self.table.selectionModel().selectedRows())
        result: list[RenderView] = []
        for row in rows:
            item = self.table.item(row, _COL_DATE)
            if item is None:
                continue
            render = by_id.get(item.data(Qt.ItemDataRole.UserRole))
            if render is not None:
                result.append(render)
        return result

    def _selected_render(self) -> Optional[RenderView]:
        renders = self._selected_renders()
        return renders[0] if renders else None

    def _activate_book_in_main_window(self, book: Path) -> bool:
        """Aktiviert `book` IN SITU im Hauptfenster (`parent._try_select_book`,
        löst dort ein volles Neuladen der Struktur aus Disk aus) und holt das
        Fenster nach vorne. Zeigt bei fehlendem Hauptfenster (z. B. Dialog
        ohne Parent, headless) selbst eine Info an und liefert `False` --
        Aufrufer entscheiden dann, ob/was zusätzlich noch angezeigt werden
        muss. Gemeinsame Basis für `_open_source_selected` (lebender Stand)
        und `_restore_source_selected` (gerade wiederhergestellter Stand)."""
        parent = self.parent()
        if parent is None or not hasattr(parent, "_try_select_book"):
            QMessageBox.information(
                self,
                "PDF Manager",
                "Kein Hauptfenster verfügbar, um das Buchprojekt zu aktivieren.\n"
                f"Projektordner: {book}",
            )
            return False
        try:
            parent._try_select_book(book)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))
            return False
        parent.raise_()
        parent.activateWindow()
        return True

    def _open_source_selected(self) -> None:
        """Aktiviert das LEBENDE Buchprojekt dieses Renders IN SITU im
        Hauptfenster (keine Kopie) -- zum Weiterbearbeiten des aktuellen
        Standes. Für den eingefrorenen Quellstand ZUM RENDER-ZEITPUNKT siehe
        stattdessen `_reveal_source_selected`/`_restore_source_selected`
        (archiviert via `render_artifact_store.archive_render_source`).
        Schließt diesen Dialog, damit der Nutzer direkt im Kapitelbaum
        weiterarbeiten und danach neu rendern (F5) kann."""
        render = self._selected_render()
        if render is None:
            QMessageBox.information(self, "PDF Manager", "Bitte eine Zeile wählen.")
            return
        book = self._book()
        if not self._activate_book_in_main_window(book):
            return
        log = getattr(self.studio, "log", None)
        if callable(log):
            try:
                log(
                    f"Quelle geöffnet → {book.name} (Änderungen vornehmen, dann neu rendern).",
                    "info",
                )
            except (TypeError, RuntimeError, AttributeError):
                pass
        self.accept()

    def _reveal_source_selected(self) -> None:
        """Read-only: öffnet den archivierten Quellstand (zum Zeitpunkt
        dieses Renders) im Explorer -- ändert nichts am lebenden
        Buchprojekt. Für Renders von vor Einführung dieses Felds gibt es
        keinen archivierten Stand (nachträglich nicht rekonstruierbar)."""
        render = self._selected_render()
        if render is None:
            QMessageBox.information(self, "PDF Manager", "Bitte eine Zeile wählen.")
            return
        if render.source_archive_path is None or not render.source_archive_path.is_dir():
            QMessageBox.information(
                self,
                "PDF Manager",
                "Für diesen Render ist kein archivierter Quellstand vorhanden "
                "(Renders von vor Einführung dieses Felds können nachträglich "
                "nicht rekonstruiert werden).",
            )
            return
        try:
            reveal_in_explorer(render.source_archive_path)
        except OSError as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))

    def _restore_source_selected(self) -> None:
        """Überschreibt das lebende Buchprojekt mit dem archivierten
        Quellstand dieses Renders (`tools.mapping_manager.actions.
        restore_source`) -- sichert den aktuellen Stand davor automatisch,
        damit auch das Wiederherstellen selbst rückgängig gemacht werden
        kann. Erfordert explizite Bestätigung, da destruktiv.

        Bei Erfolg: aktiviert das (jetzt wiederhergestellte) Buchprojekt IN
        SITU im Hauptfenster (Kapitelbaum zeigt sofort den wiederhergestellten
        Stand), setzt dort einen bleibenden Hinweis-Banner ("dies ist ein
        wiederhergestellter Stand, nicht der zuletzt bearbeitete") und
        schließt diesen Dialog."""
        render = self._selected_render()
        if render is None:
            QMessageBox.information(self, "PDF Manager", "Bitte eine Zeile wählen.")
            return
        if render.source_archive_path is None or not render.source_archive_path.is_dir():
            QMessageBox.information(
                self,
                "PDF Manager",
                "Für diesen Render ist kein archivierter Quellstand vorhanden "
                "(Renders von vor Einführung dieses Felds können nachträglich "
                "nicht rekonstruiert werden).",
            )
            return
        book = self._book()
        confirm = QMessageBox.question(
            self,
            "Quelle wiederherstellen",
            f"Aktuelles Buchprojekt „{book.name}“ mit dem Quellstand von "
            f"{render.at_display} überschreiben?\n\n"
            "Der jetzige Stand wird davor automatisch gesichert "
            "(export/pre_restore_backups/…), geht also nicht verloren.\n\n"
            "Betroffen sind u. a. content/, _quarto.yml, bookconfig/.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            backup_dir, restored = restore_source(render.source_archive_path, book)
        except OSError as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))
            return
        log = getattr(self.studio, "log", None)
        if callable(log):
            try:
                log(
                    f"Quelle wiederhergestellt ← {render.at_display} "
                    f"(Sicherung des vorigen Standes: {backup_dir}).",
                    "warning",
                )
            except (TypeError, RuntimeError, AttributeError):
                pass

        pdf_label = render.pdf_name if render.pdf_name and render.pdf_name != "(kein Pfad)" else render.id
        banner_text = (
            f"🔁 Wiederhergestellte Quelle — Stand vom Render {render.at_display} "
            f"(PDF: {pdf_label}). Voriger Stand gesichert unter: {backup_dir}"
        )
        if not self._activate_book_in_main_window(book):
            QMessageBox.information(
                self,
                "PDF Manager",
                f"Wiederhergestellt: {', '.join(restored)}\n\n"
                f"Sicherung des vorigen Standes:\n{backup_dir}",
            )
            return
        show_banner = getattr(self.parent(), "show_restored_source_banner", None)
        if callable(show_banner):
            try:
                show_banner(banner_text)
            except (TypeError, RuntimeError, AttributeError):
                pass
        self.accept()

    def _open_selected(self) -> None:
        renders = [r for r in self._selected_renders() if r.exists]
        if not renders:
            QMessageBox.information(
                self, "PDF Manager", "Bitte mindestens eine vorhandene PDF-Zeile wählen."
            )
            return
        errors = []
        for render in renders:
            try:
                open_path(render.pdf_path)
            except OSError as exc:
                errors.append(f"{render.pdf_name}: {exc}")
        if errors:
            QMessageBox.critical(self, "PDF Manager", "\n".join(errors))

    def _edit_display_name(self) -> None:
        renders = self._selected_renders()
        if len(renders) > 1:
            QMessageBox.information(
                self, "Anzeigename", "Bitte genau eine Zeile für „Anzeigename…“ wählen."
            )
            return
        render = renders[0] if renders else None
        if render is None:
            QMessageBox.information(self, "Anzeigename", "Bitte eine Zeile wählen.")
            return
        text, ok = QInputDialog.getText(
            self,
            "Anzeigename",
            "Freier Merknamen für diesen Render (nicht Layout/BoD):\n"
            "z. B. „rev.5 Probe“ oder „Korrektur Lektorat“\n\n"
            "(leer + OK = Anzeigename entfernen)",
            text=render.notes,
        )
        if not ok:
            return
        try:
            update_render_fields(
                self._book(),
                render.snapshot_id,
                render.id,
                {"notes": text.strip()},
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))
            return
        self._on_snapshot_changed(self.snapshot_combo.currentIndex())

    def _reveal_selected(self) -> None:
        renders = self._selected_renders()
        if len(renders) > 1:
            QMessageBox.information(
                self, "PDF Manager", "Bitte genau eine Zeile für „PDF im Explorer“ wählen."
            )
            return
        render = renders[0] if renders else None
        book = self._book()
        try:
            if render and render.exists:
                reveal_in_explorer(render.pdf_path)
            elif render and render.pdf_path:
                reveal_in_explorer(render.pdf_path.parent)
            else:
                reveal_in_explorer(book / "export")
        except OSError as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))

    def _copy_selected_path(self) -> None:
        renders = [r for r in self._selected_renders() if r.pdf_path]
        if not renders:
            QMessageBox.information(self, "Pfad kopieren", "Bitte eine Zeile wählen.")
            return
        QApplication.clipboard().setText("\n".join(str(r.pdf_path) for r in renders))
        log = getattr(self.studio, "log", None)
        if callable(log):
            try:
                if len(renders) == 1:
                    log(f"Pfad kopiert → {renders[0].pdf_path}", "success")
                else:
                    log(f"{len(renders)} Pfade kopiert", "success")
            except (TypeError, RuntimeError, AttributeError):
                pass

    def _rename_selected(self) -> None:
        renders = self._selected_renders()
        if len(renders) > 1:
            QMessageBox.information(
                self, "PDF Manager", "Bitte genau eine Zeile für „Dateiname…“ wählen."
            )
            return
        render = renders[0] if renders else None
        if not render or not render.exists:
            QMessageBox.information(
                self, "PDF Manager", "Bitte eine vorhandene PDF-Zeile wählen."
            )
            return
        new_name, ok = QInputDialog.getText(
            self, "Dateiname", "Neuer Dateiname:", text=render.pdf_name
        )
        if not ok or not new_name.strip():
            return
        try:
            new_path = rename_pdf(render.pdf_path, new_name.strip())
            update_render_fields(
                self._book(),
                render.snapshot_id,
                render.id,
                {"artifact_path": str(new_path)},
            )
            self._on_snapshot_changed(self.snapshot_combo.currentIndex())
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "PDF Manager", str(exc))

    def _configured_deploy_folder(self) -> str:
        import app_config as _app_config
        from ui_qt.book_workspace import repo_root

        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
        except (OSError, TypeError, ValueError):
            return ""
        return str(cfg.get("pdf_deploy_folder") or "").strip()

    def _deploy_selected(self) -> None:
        renders = [r for r in self._selected_renders() if r.exists]
        if not renders:
            QMessageBox.information(
                self, "Deploy", "Bitte mindestens eine vorhandene PDF-Zeile wählen."
            )
            return
        configured = self._configured_deploy_folder()
        dest_dir = resolve_pdf_deploy_folder(configured)
        if dest_dir is None:
            QMessageBox.warning(
                self,
                "Deploy",
                "Kein Deploy-Ziel gefunden.\n\n"
                "Bitte unter Tools → Studio-Konfiguration den Schlüssel "
                "„pdf_deploy_folder“ setzen "
                "(z. B. WEB.DE Online-Speicher\\…\\__Projekte\\IFJN\\PDF).",
            )
            return
        conflicts = [r.pdf_path.name for r in renders if (dest_dir / r.pdf_path.name).exists()]
        if conflicts:
            listing = "\n".join(conflicts)
            if (
                QMessageBox.question(
                    self,
                    "Deploy",
                    f"{len(conflicts)} Datei(en) existieren bereits und werden "
                    f"überschrieben:\n\n{listing}\n\nZiel:\n{dest_dir}",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return

        deployed: list = []
        errors = []
        for render in renders:
            try:
                deployed.append(deploy_pdf(render.pdf_path, dest_dir, overwrite=True))
            except (OSError, FileNotFoundError, FileExistsError) as exc:
                errors.append(f"{render.pdf_name}: {exc}")

        if deployed:
            self.path_label.setText(
                f"Deployed → {deployed[0]}"
                if len(deployed) == 1
                else f"{len(deployed)} PDFs deployed nach {dest_dir}"
            )
            log = getattr(self.studio, "log", None)
            if callable(log):
                for path in deployed:
                    try:
                        log(f"PDF deployed → {path}", "success")
                    except (TypeError, RuntimeError, AttributeError):
                        pass

        if errors:
            QMessageBox.critical(self, "Deploy", "\n".join(errors))
            if not deployed:
                return

        box = QMessageBox(self)
        box.setWindowTitle("Deploy")
        box.setIcon(QMessageBox.Icon.Information)
        reveal_target = deployed[0] if len(deployed) == 1 else dest_dir
        box.setText(
            f"PDF kopiert nach:\n\n{deployed[0]}"
            if len(deployed) == 1
            else f"{len(deployed)} PDFs kopiert nach:\n\n{dest_dir}"
        )
        btn_ok = box.addButton(QMessageBox.StandardButton.Ok)
        reveal_label = "Im Explorer zeigen" if len(deployed) == 1 else "Ordner im Explorer zeigen"
        btn_reveal = box.addButton(reveal_label, QMessageBox.ButtonRole.ActionRole)
        box.setDefaultButton(btn_ok)
        box.exec()
        if box.clickedButton() is btn_reveal:
            try:
                reveal_in_explorer(reveal_target)
            except OSError as exc:
                QMessageBox.critical(self, "Deploy", str(exc))

    def _delete_selected(self) -> None:
        renders = self._selected_renders()
        if not renders:
            return
        if len(renders) == 1:
            label = renders[0].notes.strip() or renders[0].pdf_name or renders[0].id
            message = f"PDF und Listeneintrag löschen?\n\n{label}"
        else:
            labels = "\n".join(r.notes.strip() or r.pdf_name or r.id for r in renders)
            message = f"{len(renders)} PDFs und Listeneinträge löschen?\n\n{labels}"
        if (
            QMessageBox.question(self, "Löschen", message)
            != QMessageBox.StandardButton.Yes
        ):
            return

        # Zusätzliche, separate Abfrage NUR wenn mindestens einer der
        # markierten Renders einen archivierten Quellstand hat -- Löschen
        # der PDF und Löschen der (reproduzierbaren!) Quelle sind zwei
        # unabhängige Entscheidungen, Default ist deshalb "Nein" (sicherer).
        renders_with_source = [
            r for r in renders
            if r.source_archive_path is not None and r.source_archive_path.is_dir()
        ]
        delete_sources = False
        if renders_with_source:
            count = len(renders_with_source)
            prompt = (
                (
                    "Auch den archivierten Quellstand dieser PDF löschen?"
                    if count == 1
                    else f"Auch die archivierten Quellstände dieser {count} PDFs löschen?"
                )
                + "\n\nDanach ist der exakte Quellstand nicht mehr wiederherstellbar."
            )
            delete_sources = (
                QMessageBox.question(
                    self,
                    "Quelle mitlöschen?",
                    prompt,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )

        errors = []
        for render in renders:
            try:
                if render.exists:
                    delete_pdf(render.pdf_path)
                if (
                    delete_sources
                    and render.source_archive_path is not None
                    and render.source_archive_path.is_dir()
                ):
                    delete_source_archive(render.source_archive_path)
                remove_render(self._book(), render.snapshot_id, render.id)
            except (OSError, ValueError) as exc:
                errors.append(f"{render.pdf_name or render.id}: {exc}")
        self._on_snapshot_changed(self.snapshot_combo.currentIndex())
        if errors:
            QMessageBox.critical(self, "PDF Manager", "\n".join(errors))


def open_mapping_manager_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    # Dialog erlaubt Buchwechsel intern — current_book darf initial fehlen,
    # solange Discovery Bücher findet.
    MappingManagerQtDialog(parent, studio).exec()
