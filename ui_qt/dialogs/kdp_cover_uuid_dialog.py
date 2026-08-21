"""Qt-Dialog: Production-UUID für KDP-Cover wählen (GG ∪ Book Studio).

Filterbare, spaltensortierbare Tabelle. Vor dem Öffnen: Fortschrittsdialog
während die UUID-Liste geladen wird. Fenstergröße in ``last_session.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.cover_registry import CoverRole
from tools.kdp_cover.settings import (
    load_settings,
    resolve_uuid_picker_column_widths,
    resolve_uuid_picker_window_size,
    save_settings,
)
from tools.kdp_cover.uuid_choices import (
    UuidChoice,
    list_production_uuid_choices,
    resolve_grammargraph_repo,
    resolve_studio_repo,
)
from tools.production_uuid import normalize_uuid, read_book_uuid

_COLUMNS = (
    ("uuid", "UUID"),
    ("title", "Titel"),
    ("batch_display", "Batch/Output"),
    ("cover_link_display", "Cover"),
    ("origin_label", "Herkunft"),
    ("content_label", "Inhalt"),
    ("status_label", "Status"),
    ("market_display", "Markt"),
    ("output_created_display", "Erstellt (Output)"),
    ("production_created_display", "Erstellt (Produktion)"),
)

_COLUMN_TOOLTIPS = {
    "Batch/Output": (
        "GrammarGraph-Batch-Ordnername (z. B. …_Katalonien_complete) "
        "bzw. batch_id aus der Publikation."
    ),
    "Cover": (
        "Bereits in der Cover↔UUID-Registry verknüpfte Layouts "
        "(Primary / Alternativen). Tooltip zeigt Pfade und Labels."
    ),
    "Markt": (
        "Marktvariante der GrammarGraph-Lieferung / des Buchs "
        "(z. B. DE, AT, CH). Leer = keine Variante hinterlegt."
    ),
    "Erstellt (Output)": (
        "Zeitpunkt des letzten Book-Studio-Renders (PDF/Output) "
        "bzw. Export-/Batch-Zeit."
    ),
    "Erstellt (Produktion)": (
        "Zeitpunkt der GrammarGraph-Lieferung (publish_meta.created_at) "
        "bzw. Batch-Zeit bei unpubliziertem Output."
    ),
}


class CoverUuidPickDialog(QDialog):
    """Modal picker: production UUID + cover label/role (table UI)."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        studio: Any = None,
        book_root: Path | None = None,
        preselect_uuid: str = "",
        initial_label: str = "",
        initial_role: CoverRole = "primary",
        choices: list[UuidChoice] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cover mit Production-UUID verknüpfen")
        self.setObjectName("kdpCoverUuidPickDialog")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(640, 420)
        self._choices: list[UuidChoice] = []
        self._result: dict[str, Any] | None = None
        self._row_choices: list[UuidChoice] = []
        self._choices_provided = choices is not None
        self._geometry_applied = False
        self._geometry_restore_scheduled = False
        self._suppress_geometry_persist = True
        if choices is not None:
            self._choices = list(choices)

        try:
            settings = load_settings()
            ww, wh = resolve_uuid_picker_window_size(settings)
            self._restore_maximized = bool(
                settings.get("uuid_picker_window_maximized")
            )
            self._restore_column_widths = resolve_uuid_picker_column_widths(
                settings, column_count=len(_COLUMNS)
            )
        except OSError:
            ww, wh = 900, 560
            self._restore_maximized = False
            self._restore_column_widths = None
        self._restore_width = max(640, int(ww))
        self._restore_height = max(420, int(wh))

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(250)
        self._geometry_save_timer.timeout.connect(self._persist_geometry)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        # Kein automatisches Aufblasen auf Table-sizeHint (zerstört Persistenz).
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)

        hint = QLabel(
            "Wähle die GrammarGraph-/Buch-UUID, zu der dieses Cover gehört.\n"
            "Alternativen: später erneut speichern unter derselben UUID "
            "mit Rolle „Alternative“ und anderem Label."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#1c2740; font-size:13px;")
        root.addWidget(hint)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet("color:#5b6573;")
        filter_row.addWidget(filter_lbl)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Titel, UUID, Cover, Herkunft…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit, stretch=1)
        self.filter_count = QLabel("")
        self.filter_count.setStyleSheet("color:#64748b; font-size:12px;")
        filter_row.addWidget(self.filter_count)
        root.addLayout(filter_row)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("kdpCoverUuidTable")
        self.table.setHorizontalHeaderLabels([label for _, label in _COLUMNS])
        for col, (_, label) in enumerate(_COLUMNS):
            tip = _COLUMN_TOOLTIPS.get(label)
            if tip:
                item = self.table.horizontalHeaderItem(col)
                if item is not None:
                    item.setToolTip(tip)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        # Alle Spalten per Drag verstellbar; Breiten werden mitpersistiert.
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(len(_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSortIndicatorShown(True)
        header.sectionResized.connect(self._on_column_resized)
        self.table.setStyleSheet(
            """
            QTableWidget#kdpCoverUuidTable {
                border: 1px solid #c8d3ec;
                border-radius: 6px;
                gridline-color: #e2e8f0;
                background: #ffffff;
                alternate-background-color: #f7f9fd;
            }
            QHeaderView::section {
                background: #eef1f8;
                color: #1c2740;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #c8d3ec;
                border-bottom: 1px solid #c8d3ec;
                font-weight: 600;
            }
            """
        )
        root.addWidget(self.table, stretch=1)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        meta.addWidget(QLabel("Cover-Label:"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("z. B. Variante A / Hauptcover")
        self.label_edit.setText(str(initial_label or "").strip())
        meta.addWidget(self.label_edit, stretch=1)
        meta.addWidget(QLabel("Rolle:"))
        self.role_combo = QComboBox()
        self.role_combo.addItem("Primary (Hauptcover)", "primary")
        self.role_combo.addItem("Alternative", "alternative")
        role = "alternative" if initial_role == "alternative" else "primary"
        idx = self.role_combo.findData(role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)
        meta.addWidget(self.role_combo)
        root.addLayout(meta)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Cover zuordnen")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Back-compat alias for older tests that looked at ``self.list``.
        self.list = self.table

        if not self._choices_provided:
            self._choices = load_uuid_choices_with_progress(self, studio=studio)

        preferred = (
            normalize_uuid(preselect_uuid)
            or (read_book_uuid(book_root) if book_root else None)
            or ""
        )
        self._preferred_uuid = preferred
        self._fill_table(self._choices)
        self._apply_filter(self.filter_edit.text())
        self._select_preferred()
        self._apply_column_widths(self._restore_column_widths)
        # Gespeicherte Größe als Startgröße (sizeHint folgt dem).
        self.resize(self._restore_width, self._restore_height)
        self._suppress_geometry_persist = False
        self.finished.connect(self._on_finished_persist)

    @staticmethod
    def _load_choices(*, studio: Any = None) -> list[UuidChoice]:
        return load_uuid_choices(studio=studio)

    def _fill_table(self, choices: list[UuidChoice]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self._row_choices = []
        for choice in choices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_choices.append(choice)
            values = [
                choice.uuid,
                choice.title.strip() or "(ohne Titel)",
                choice.batch_display,
                choice.cover_link_display_safe,
                choice.origin_label,
                choice.content_label,
                choice.status_label,
                choice.market_display,
                choice.output_created_display,
                choice.production_created_display,
            ]
            tip = (
                f"UUID: {choice.uuid}\n"
                f"Batch/Output: {choice.batch_display}\n"
                f"Cover-Zuordnung:\n{choice.cover_link_detail or '—'}\n"
                f"Herkunft: {choice.origin_label}\n"
                f"Status: {choice.status_label} ({choice.content_label})\n"
                f"Marktvariante: {choice.market_display}\n"
                f"Erstellt (Output): {choice.output_created_display}\n"
                f"Erstellt (Produktion): {choice.production_created_display}\n"
                f"Buch: {choice.book_path or '—'}\n"
                f"Pfad: {choice.publish_dir or '—'}"
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                item.setToolTip(tip)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, choice)
                    # Kurzanzeige in der Zelle, voller UUID im Tooltip/Sort.
                    short = (
                        choice.uuid
                        if len(choice.uuid) <= 13
                        else f"{choice.uuid[:8]}…"
                    )
                    item.setText(short)
                    item.setData(Qt.ItemDataRole.UserRole + 1, choice.uuid)
                elif col in {8, 9}:
                    # Sort by raw ISO when present (empty → sort last).
                    raw = (
                        choice.output_created_at
                        if col == 8
                        else choice.production_created_at
                    )
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        raw.strip() if raw.strip() else "0000",
                    )
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    def _apply_filter(self, text: str = "") -> None:
        needle = (text or self.filter_edit.text() or "").casefold().strip()
        visible = 0
        total = self.table.rowCount()
        for row in range(total):
            if not needle:
                show = True
            else:
                parts: list[str] = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item is None:
                        continue
                    parts.append(item.text())
                    full = item.data(Qt.ItemDataRole.UserRole + 1)
                    if full:
                        parts.append(str(full))
                    choice = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(choice, UuidChoice):
                        parts.extend(
                            [
                                choice.uuid,
                                choice.title,
                                choice.batch_id,
                                choice.batch_display,
                                choice.cover_link_display,
                                choice.cover_link_detail,
                                choice.origin_label,
                                choice.content_label,
                                choice.status_label,
                                choice.market_variant,
                                choice.market_display,
                                choice.output_created_at,
                                choice.production_created_at,
                                choice.output_created_display,
                                choice.production_created_display,
                                choice.publish_dir,
                            ]
                        )
                        break
                show = needle in " ".join(parts).casefold()
            self.table.setRowHidden(row, not show)
            if show:
                visible += 1
        self.filter_count.setText(f"{visible} / {total}")

    def _refilter(self) -> None:
        """Back-compat name used by older call sites."""
        self._apply_filter(self.filter_edit.text())

    def _select_preferred(self) -> None:
        if not self._preferred_uuid:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
            return
        target = self._preferred_uuid.casefold()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            choice = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(choice, UuidChoice) and choice.uuid.casefold() == target:
                if not self.table.isRowHidden(row):
                    self.table.selectRow(row)
                    return
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.selectRow(row)
                return

    def _current_choice(self) -> UuidChoice | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        choice = item.data(Qt.ItemDataRole.UserRole)
        return choice if isinstance(choice, UuidChoice) else None

    def _accept_if_valid(self) -> None:
        choice = self._current_choice()
        if choice is None:
            QMessageBox.warning(
                self,
                "UUID wählen",
                "Bitte eine Production-UUID in der Tabelle auswählen.",
            )
            return
        role_data = self.role_combo.currentData()
        role: CoverRole = (
            "alternative" if role_data == "alternative" else "primary"
        )
        self._result = {
            "uuid": choice.uuid,
            "cover_label": self.label_edit.text().strip(),
            "cover_role": role,
            "title_hint": choice.title,
            "source_kinds": list(choice.origins),
            "origin_label": choice.origin_label,
            "content_label": choice.content_label,
        }
        self.accept()

    def selected(self) -> dict[str, Any] | None:
        return self._result

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        """Gespeicherte Größe — sonst bläht die Tabelle den Dialog auf."""
        return QSize(
            int(getattr(self, "_restore_width", 900)),
            int(getattr(self, "_restore_height", 560)),
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(640, 420)

    def _current_column_widths(self) -> list[int]:
        return [
            max(24, int(self.table.columnWidth(col)))
            for col in range(self.table.columnCount())
        ]

    def _apply_column_widths(self, widths: list[int] | None) -> None:
        if not widths or len(widths) != self.table.columnCount():
            return
        was_suppress = getattr(self, "_suppress_geometry_persist", False)
        self._suppress_geometry_persist = True
        try:
            header = self.table.horizontalHeader()
            for col, width in enumerate(widths):
                header.resizeSection(col, max(24, int(width)))
        finally:
            self._suppress_geometry_persist = was_suppress

    def _on_column_resized(self, _index: int, _old: int, _new: int) -> None:
        if getattr(self, "_suppress_geometry_persist", False):
            return
        if not self.isVisible():
            return
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.start()

    def _apply_restored_geometry(self) -> None:
        """Fenstergröße + Spaltenbreiten nach Show erzwingen."""
        if getattr(self, "_geometry_applied", False):
            return
        self._suppress_geometry_persist = True
        try:
            self._apply_column_widths(
                getattr(self, "_restore_column_widths", None)
            )
            if getattr(self, "_restore_maximized", False):
                self.showMaximized()
                self._geometry_applied = True
                self._suppress_geometry_persist = False
                return
            w = int(getattr(self, "_restore_width", 900))
            h = int(getattr(self, "_restore_height", 560))
            self.resize(w, h)
            QTimer.singleShot(0, lambda ww=w, hh=h: self._force_resize(ww, hh))
        except Exception:
            self._geometry_applied = True
            self._suppress_geometry_persist = False
            raise

    def _force_resize(self, width: int, height: int) -> None:
        try:
            if getattr(self, "_restore_maximized", False):
                return
            if self.isVisible():
                self.resize(int(width), int(height))
                self._apply_column_widths(
                    getattr(self, "_restore_column_widths", None)
                )
        finally:
            self._suppress_geometry_persist = False
            self._geometry_applied = True

    def _persist_geometry(self) -> None:
        if getattr(self, "_suppress_geometry_persist", False):
            return
        try:
            maximized = bool(self.isMaximized())
            if maximized:
                geo = self.normalGeometry()
                width, height = int(geo.width()), int(geo.height())
            else:
                width, height = int(self.width()), int(self.height())
            if width < 640 or height < 420:
                return
            self._restore_width = width
            self._restore_height = height
            self._restore_maximized = maximized
            col_widths = self._current_column_widths()
            self._restore_column_widths = col_widths
            save_settings(
                {
                    "uuid_picker_window_width": width,
                    "uuid_picker_window_height": height,
                    "uuid_picker_window_maximized": maximized,
                    "uuid_picker_column_widths": col_widths,
                }
            )
        except OSError:
            pass

    def _on_finished_persist(self, _result: int = 0) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._persist_geometry()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if getattr(self, "_geometry_applied", False):
            return
        if getattr(self, "_geometry_restore_scheduled", False):
            return
        self._geometry_restore_scheduled = True
        QTimer.singleShot(0, self._apply_restored_geometry)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._persist_geometry()
        super().closeEvent(event)

    def accept(self) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._persist_geometry()
        super().accept()

    def reject(self) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._persist_geometry()
        super().reject()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if getattr(self, "_suppress_geometry_persist", False):
            return
        if not self.isVisible():
            return
        if not getattr(self, "_geometry_applied", False):
            return
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.start()


def load_uuid_choices(*, studio: Any = None) -> list[UuidChoice]:
    """Load UUID choices (no UI)."""
    repo = resolve_studio_repo(studio)
    gg = resolve_grammargraph_repo(studio)
    try:
        return list_production_uuid_choices(
            book_studio_repo=repo,
            grammargraph_repo=gg,
        )
    except OSError:
        return []


def load_uuid_choices_with_progress(
    parent: Optional[QWidget],
    *,
    studio: Any = None,
) -> list[UuidChoice]:
    """Show a blocking progress dialog while scanning GG/BS for UUIDs."""
    progress = QProgressDialog(
        "Production-UUIDs werden geladen\n"
        "(GrammarGraph-Lieferungen und Book-Studio-Bücher)…",
        None,
        0,
        0,
        parent,
    )
    progress.setWindowTitle("UUID-Liste laden")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setCancelButton(None)
    progress.setMinimumWidth(420)
    progress.setValue(0)
    progress.show()
    QApplication.processEvents()
    try:
        return load_uuid_choices(studio=studio)
    finally:
        progress.close()
        progress.deleteLater()
        QApplication.processEvents()


def pick_cover_uuid(
    parent: Optional[QWidget] = None,
    *,
    studio: Any = None,
    book_root: Path | None = None,
    preselect_uuid: str = "",
    initial_label: str = "",
    initial_role: CoverRole = "primary",
    choices: list[UuidChoice] | None = None,
) -> dict[str, Any] | None:
    """Run picker; return selection dict or None if cancelled.

    If ``choices`` is not provided, shows a progress dialog *before* the
    picker window appears while the UUID list is scanned.
    """
    loaded = choices
    if loaded is None:
        loaded = load_uuid_choices_with_progress(parent, studio=studio)

    dlg = CoverUuidPickDialog(
        parent,
        studio=studio,
        book_root=book_root,
        preselect_uuid=preselect_uuid,
        initial_label=initial_label,
        initial_role=initial_role,
        choices=loaded,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.selected()


__all__ = [
    "CoverUuidPickDialog",
    "load_uuid_choices",
    "load_uuid_choices_with_progress",
    "pick_cover_uuid",
]
