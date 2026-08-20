"""Qt-Dialog: Cover-Schlagwortwolke Presets verwalten."""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tools.stylecloud.preset_store import (
    delete_preset,
    list_presets,
    load_preset,
    rename_preset,
    save_preset,
)


class StylecloudPresetManagerDialog(QDialog):
    """List / load / rename / delete named stylecloud presets."""

    def __init__(
        self,
        *,
        collect_settings: Callable[[], dict[str, Any]],
        apply_settings: Callable[[dict[str, Any]], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._collect_settings = collect_settings
        self._apply_settings = apply_settings
        self._loaded_name: str | None = None

        self.setWindowTitle("Preset-Manager — Cover-Schlagwortwolke")
        self.setMinimumSize(420, 360)
        self.resize(480, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(
            QLabel(
                "Benannte Einstellungs-Presets (Auflösung, Form, Farben, "
                "Muss-Wort, PNG-Optionen, …)."
            )
        )

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.itemDoubleClicked.connect(self._load_selected)
        layout.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_load = QPushButton("Laden")
        self.btn_load.clicked.connect(self._load_selected)
        btn_row.addWidget(self.btn_load)
        self.btn_save = QPushButton("Aktuell speichern…")
        self.btn_save.clicked.connect(self._save_current)
        btn_row.addWidget(self.btn_save)
        self.btn_rename = QPushButton("Umbenennen…")
        self.btn_rename.clicked.connect(self._rename_selected)
        btn_row.addWidget(self.btn_rename)
        self.btn_delete = QPushButton("Löschen…")
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        layout.addLayout(btn_row)

        self._refresh_list()
        self.list.currentItemChanged.connect(self._update_buttons)
        self._update_buttons()

    @property
    def loaded_preset_name(self) -> str | None:
        return self._loaded_name

    def _selected_name(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            return None
        name = item.data(Qt.ItemDataRole.UserRole)
        return str(name) if name else None

    def _refresh_list(self, select_name: str | None = None) -> None:
        current = select_name or self._selected_name()
        self.list.clear()
        for info in list_presets():
            item = QListWidgetItem(info.name)
            item.setData(Qt.ItemDataRole.UserRole, info.name)
            tip = info.updated_at or str(info.path.name)
            item.setToolTip(tip)
            self.list.addItem(item)
            if current and info.name.casefold() == current.casefold():
                self.list.setCurrentItem(item)
        self._update_buttons()

    def _update_buttons(self, *_args: object) -> None:
        has = self._selected_name() is not None
        self.btn_load.setEnabled(has)
        self.btn_rename.setEnabled(has)
        self.btn_delete.setEnabled(has)

    def _load_selected(self, *_args: object) -> None:
        name = self._selected_name()
        if not name:
            return
        try:
            settings = load_preset(name)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Preset laden", str(exc))
            return
        self._apply_settings(settings)
        self._loaded_name = name
        QMessageBox.information(
            self,
            "Preset geladen",
            f"Preset „{name}“ wurde in den Dialog übernommen.",
        )

    def _save_current(self) -> None:
        suggested = self._selected_name() or ""
        name, ok = QInputDialog.getText(
            self,
            "Preset speichern",
            "Name des Presets:",
            text=suggested,
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Preset speichern", "Bitte einen Namen angeben.")
            return
        existing = {p.name.casefold() for p in list_presets()}
        if name.casefold() in existing:
            answer = QMessageBox.question(
                self,
                "Preset überschreiben?",
                f"Preset „{name}“ existiert bereits. Überschreiben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            save_preset(name, self._collect_settings())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Preset speichern", str(exc))
            return
        self._refresh_list(select_name=name)

    def _rename_selected(self) -> None:
        old = self._selected_name()
        if not old:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Preset umbenennen",
            "Neuer Name:",
            text=old,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old:
            return
        try:
            rename_preset(old, new_name)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Preset umbenennen", str(exc))
            return
        if self._loaded_name == old:
            self._loaded_name = new_name
        self._refresh_list(select_name=new_name)

    def _delete_selected(self) -> None:
        name = self._selected_name()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            "Preset löschen?",
            f"Preset „{name}“ wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not delete_preset(name):
            QMessageBox.warning(
                self,
                "Preset löschen",
                f"Preset „{name}“ konnte nicht gelöscht werden.",
            )
            return
        if self._loaded_name == name:
            self._loaded_name = None
        self._refresh_list()
