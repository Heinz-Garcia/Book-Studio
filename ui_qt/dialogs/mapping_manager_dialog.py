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
from tools.publish_map.store import read_map, remove_render, update_render_fields
from ui_qt.widgets.help_bar import HelpBar


class MappingManagerQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self.studio = studio
        self.setWindowTitle("Mapping Manager — Produktionslinien")
        self.resize(1100, 560)
        self._snapshots: list[SnapshotView] = []
        self._renders: list[RenderView] = []

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "mapping_manager")

        row = QHBoxLayout()
        row.addWidget(QLabel("Produktionslinie:"))
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.currentIndexChanged.connect(self._on_snapshot_changed)
        row.addWidget(self.snapshot_combo, stretch=1)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._reload_snapshots)
        row.addWidget(refresh)
        layout.addLayout(row)

        self.empty_label = QLabel("")
        self.empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["PDF", "Layout", "Template", "Format", "Profil", "Datum", "Status", "Notiz"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
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

    def _preferred_snapshot_index(self) -> int:
        """Aktive Produktionslinie, sonst die neueste (wie Tk: labels[-1])."""
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
        previous_id = self.snapshot_combo.currentData()
        self._snapshots = load_snapshots(self._book())
        self.snapshot_combo.blockSignals(True)
        self.snapshot_combo.clear()
        for snap in self._snapshots:
            mark = ""
            self.snapshot_combo.addItem(f"{snap.label}{mark}", snap.id)
        # aktive Linie kennzeichnen
        try:
            data = read_map(self._book()) or {}
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
            self.table.setRowCount(0)
            self.empty_label.setText("Keine Produktionslinie vorhanden.")
            return
        # Auswahl: bisherige behalten, sonst aktiv/neueste
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
            self._renders = []
            self.table.setRowCount(0)
            self.empty_label.setText("")
            return
        self._renders = load_renders(self._book(), str(snap_id))
        self.table.setRowCount(len(self._renders))
        if not self._renders:
            self.empty_label.setText("Noch keine Renders für diese Produktionslinie.")
        else:
            self.empty_label.setText(f"{len(self._renders)} Render(s) in dieser Produktionslinie.")
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
                if col == 0:
                    item.setToolTip(str(render.pdf_path))
                # Nur Notiz editierbar
                if col != 7:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if col == 7:
            return  # Notiz editieren
        if 0 <= row < len(self._renders):
            self.table.selectRow(row)
            self._open_selected()

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
        book = self._book()
        try:
            if render and render.exists:
                reveal_in_explorer(render.pdf_path)
            elif render:
                reveal_in_explorer(render.pdf_path.parent)
            else:
                reveal_in_explorer(book / "export")
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
