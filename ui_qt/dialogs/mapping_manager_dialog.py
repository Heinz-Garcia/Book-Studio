"""Qt Mapping Manager — nutzt dieselbe Loader-/Actions-Logik wie das Tk-Tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.mapping_manager.actions import delete_pdf, open_path, rename_pdf, reveal_in_explorer
from tools.mapping_manager.loader import load_renders, load_snapshots
from tools.mapping_manager.models import RenderView, SnapshotView, layout_profile_label
from tools.publish_map.store import remove_render, update_render_fields


class MappingManagerQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self.studio = studio
        self.setWindowTitle("Mapping Manager")
        self.resize(1100, 520)
        self._snapshots: list[SnapshotView] = []
        self._renders: list[RenderView] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Publish-Input → generierte PDFs"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Produktionslinie:"))
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.currentIndexChanged.connect(self._on_snapshot_changed)
        row.addWidget(self.snapshot_combo, stretch=1)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._reload_snapshots)
        row.addWidget(refresh)
        layout.addLayout(row)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["PDF", "Layout", "Template", "Format", "Profil", "Datum", "Status", "Notiz"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        for label, slot in (
            ("Öffnen", self._open_selected),
            ("Explorer", self._reveal_selected),
            ("Umbenennen", self._rename_selected),
            ("Notiz speichern", self._save_note),
            ("Löschen", self._delete_selected),
            ("Schließen", self.accept),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            actions.addWidget(btn)
        layout.addLayout(actions)

        self._reload_snapshots()

    def _book(self) -> Path:
        return Path(self.studio.current_book)

    def _reload_snapshots(self) -> None:
        self._snapshots = load_snapshots(self._book())
        self.snapshot_combo.blockSignals(True)
        self.snapshot_combo.clear()
        for snap in self._snapshots:
            self.snapshot_combo.addItem(snap.label, snap.id)
        self.snapshot_combo.blockSignals(False)
        if self._snapshots:
            self._on_snapshot_changed(0)
        else:
            self.table.setRowCount(0)

    def _on_snapshot_changed(self, _index: int) -> None:
        snap_id = self.snapshot_combo.currentData()
        if not snap_id:
            self._renders = []
            self.table.setRowCount(0)
            return
        self._renders = load_renders(self._book(), str(snap_id))
        self.table.setRowCount(len(self._renders))
        for row, render in enumerate(self._renders):
            vals = [
                render.pdf_name,
                layout_profile_label(render.layout_profile),
                render.template,
                render.format,
                render.profile_name,
                render.at_display,
                "OK" if render.exists else "fehlt",
                render.notes,
            ]
            for col, text in enumerate(vals):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, render.id)
                self.table.setItem(row, col, item)

    def _selected_render(self) -> Optional[RenderView]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._renders):
            return self._renders[idx]
        return None

    def _open_selected(self) -> None:
        render = self._selected_render()
        if not render or not render.exists:
            QMessageBox.information(self, "Mapping Manager", "Bitte eine vorhandene PDF-Zeile wählen.")
            return
        try:
            open_path(render.pdf_path)
        except OSError as exc:
            QMessageBox.critical(self, "Mapping Manager", str(exc))

    def _reveal_selected(self) -> None:
        render = self._selected_render()
        if not render:
            return
        try:
            reveal_in_explorer(render.pdf_path if render.exists else render.pdf_path.parent)
        except OSError as exc:
            QMessageBox.critical(self, "Mapping Manager", str(exc))

    def _rename_selected(self) -> None:
        render = self._selected_render()
        if not render or not render.exists:
            QMessageBox.information(self, "Mapping Manager", "Bitte eine vorhandene PDF-Zeile wählen.")
            return
        new_name, ok = QInputDialog.getText(self, "Umbenennen", "Neuer Dateiname:", text=render.pdf_name)
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
            QMessageBox.critical(self, "Mapping Manager", str(exc))

    def _save_note(self) -> None:
        render = self._selected_render()
        if not render:
            return
        row = self.table.currentRow()
        item = self.table.item(row, 7)
        note = item.text() if item else ""
        try:
            update_render_fields(
                self._book(),
                render.snapshot_id,
                render.id,
                {"notes": note},
            )
            QMessageBox.information(self, "Mapping Manager", "Notiz gespeichert.")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Mapping Manager", str(exc))

    def _delete_selected(self) -> None:
        render = self._selected_render()
        if not render:
            return
        if (
            QMessageBox.question(
                self,
                "Löschen",
                f"PDF und Map-Eintrag löschen?\n{render.pdf_name}",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            if render.exists:
                delete_pdf(render.pdf_path)
            remove_render(self._book(), render.snapshot_id, render.id)
            self._on_snapshot_changed(self.snapshot_combo.currentIndex())
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Mapping Manager", str(exc))


def open_mapping_manager_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    if not getattr(studio, "current_book", None):
        QMessageBox.warning(parent, "Mapping Manager", "Kein Buchprojekt aktiv.")
        return
    MappingManagerQtDialog(parent, studio).exec()
