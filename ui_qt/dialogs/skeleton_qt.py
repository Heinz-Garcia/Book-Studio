"""Qt-Skeleton: Profil wählen + Populate (ohne Tk-Dialoge)."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from tools.skeleton.config import read_skeleton_settings
from tools.skeleton.manifest import list_profiles, load_manifest, resolve_library_root
from ui_qt.book_workspace import repo_root
from ui_qt.widgets.help_bar import HelpBar


class SkeletonPopulateQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], profiles: list[str], labels: dict[str, str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Skeleton-Rahmen übernehmen")
        self.resize(460, 240)
        self.selected_profile: Optional[str] = None

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "skeleton_populate")
        layout.addWidget(QLabel("Profil aus der Skeleton-Bibliothek wählen:"))
        form = QFormLayout()
        self.combo = QComboBox()
        for name in profiles:
            self.combo.addItem(labels.get(name, name), name)
        form.addRow("Profil:", self.combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ok(self) -> None:
        self.selected_profile = self.combo.currentData()
        self.accept()


def open_skeleton_populate_qt(studio: Any, parent: Optional[QWidget] = None, **kwargs) -> int:
    if not getattr(studio, "current_book", None):
        QMessageBox.warning(parent, "Skeleton", "Kein Buchprojekt aktiv.")
        return 1
    root = repo_root()
    settings = read_skeleton_settings(root)
    library_root = resolve_library_root(root, str(settings.get("library_path") or "tools/skeleton/library"))
    profiles = list_profiles(library_root)
    if not profiles:
        QMessageBox.warning(parent, "Skeleton", "Keine Profile in der Bibliothek gefunden.")
        return 1
    labels = {}
    for name in profiles:
        try:
            labels[name] = load_manifest(library_root / name).label
        except (OSError, ValueError):
            labels[name] = name

    profile = kwargs.get("profile")
    if not profile:
        dlg = SkeletonPopulateQtDialog(parent, profiles, labels)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_profile:
            return 1
        profile = dlg.selected_profile

    from tools.skeleton.populate import run as populate_run

    old_root = getattr(studio, "root", None)
    try:
        studio.root = None
        code = populate_run(
            studio=studio,
            profile=profile,
            skip_dialog=True,
            yes=True,
            conflict_mode="skip",
        )
    finally:
        studio.root = old_root

    QMessageBox.information(
        parent,
        "Skeleton",
        f"Populate für Profil „{profile}“ beendet (Exit {code}).\n"
        "Details siehe Log; Kapitel ggf. links im Pool einhängen.",
    )
    return int(code or 0)


def open_skeleton_editor_qt(studio: Any, parent: Optional[QWidget] = None, **kwargs) -> int:
    """Delegiert an den vollständigen Qt-Editor (Feature-Parität zum Tk-Editor)."""
    from ui_qt.dialogs.skeleton_editor_dialog import open_skeleton_editor_qt as _full

    return _full(studio=studio, parent=parent, **kwargs)
