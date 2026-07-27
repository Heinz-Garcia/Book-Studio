"""Verwaiste Skeleton-Dateien: physisch im Profilordner vorhanden, aber in
keinem Manifest-Eintrag referenziert (z. B. nach „Nur aus Profil entfernen“
oder manuell im Ordner abgelegt)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OrphanFilesDialog(QDialog):
    """Listet verwaiste Dateien und bietet an, sie zurück ins Profil aufzunehmen
    oder endgültig zu löschen."""

    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        profile_root: Path,
        orphans: list[str],
        on_add: Callable[[str], bool],
        on_delete: Callable[[list[str]], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Verwaiste Dateien")
        self.setModal(True)
        self.resize(640, 420)
        self._profile_root = Path(profile_root)
        self._on_add = on_add
        self._on_delete = on_delete

        root = QVBoxLayout(self)
        info = QLabel(
            "Diese Dateien liegen physisch im Profilordner, sind aber in keinem "
            "Vorlagen-Eintrag referenziert — z. B. weil sie über „Nur aus Profil "
            "entfernen“ entfernt oder manuell im Ordner abgelegt wurden."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        root.addWidget(self._list, stretch=1)

        btns = QHBoxLayout()
        self._btn_add = QPushButton("➕ Zum Profil hinzufügen…")
        self._btn_add.setToolTip("Legt für die ausgewählte Datei einen neuen Vorlagen-Eintrag an.")
        self._btn_add.clicked.connect(self._add_selected)
        btns.addWidget(self._btn_add)
        self._btn_delete = QPushButton("🗑️ Löschen…")
        self._btn_delete.setToolTip("Löscht die ausgewählten Dateien unwiderruflich von der Platte.")
        self._btn_delete.clicked.connect(self._delete_selected)
        btns.addWidget(self._btn_delete)
        btns.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        root.addLayout(btns)

        self._reload(orphans)

    def _reload(self, orphans: list[str]) -> None:
        self._list.clear()
        self._list.addItems(orphans)
        has_items = bool(orphans)
        self._btn_add.setEnabled(has_items)
        self._btn_delete.setEnabled(has_items)

    def _selected_paths(self) -> list[str]:
        return [item.text() for item in self._list.selectedItems()]

    def _remove_from_list(self, rel_path: str) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).text() == rel_path:
                self._list.takeItem(i)
                break
        if self._list.count() == 0:
            self._btn_add.setEnabled(False)
            self._btn_delete.setEnabled(False)

    def _add_selected(self) -> None:
        selected = self._selected_paths()
        if len(selected) != 1:
            QMessageBox.information(
                self,
                "Verwaiste Dateien",
                "Bitte genau eine Datei zum Hinzufügen auswählen.",
            )
            return
        rel_path = selected[0]
        if self._on_add(rel_path):
            self._remove_from_list(rel_path)

    def _delete_selected(self) -> None:
        selected = self._selected_paths()
        if not selected:
            return
        joined = "\n".join(selected)
        if (
            QMessageBox.question(
                self,
                "Dateien löschen",
                f"{len(selected)} Datei(en) unwiderruflich von der Platte löschen?\n\n{joined}",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._on_delete(selected)
        for rel_path in selected:
            self._remove_from_list(rel_path)
