"""Qt-Skeleton: Profil wählen + optionale Snippets + Populate (ohne Tk-Dialoge)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from tools.skeleton.config import read_skeleton_settings
from tools.skeleton.manifest import (
    SkeletonFileEntry,
    list_profiles,
    load_manifest,
    resolve_library_root,
)
from ui_qt.book_workspace import repo_root
from ui_qt.widgets.help_bar import HelpBar


def list_optional_manifest_entries(
    library_root: Path,
    profile_name: str,
) -> list[SkeletonFileEntry]:
    """Nicht-required (optionale) Manifest-Einträge des Profils, Manifest-Reihenfolge."""
    manifest = load_manifest(Path(library_root) / profile_name)
    return [entry for entry in manifest.files if not entry.required]


def file_overrides_for_selected_optionals(
    selected_rel_paths: list[str],
) -> dict[str, bool]:
    """Override-Map: nur angewählte optionale Pfade → True (Rest bleibt Default-Skip)."""
    return {str(path): True for path in selected_rel_paths if path}


class SkeletonPopulateQtDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        profiles: list[str],
        labels: dict[str, str],
        library_root: Path,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Skeleton-Rahmen übernehmen")
        self.resize(560, 520)
        self.setMinimumSize(480, 420)
        self._library_root = Path(library_root)
        self.selected_profile: Optional[str] = None
        self.selected_file_overrides: dict[str, bool] = {}
        self._optional_checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "skeleton_populate")
        layout.addWidget(
            QLabel(
                "Kopiert Standard-Vorlagen aus der Skeleton-Bibliothek links in den "
                "Pool des aktiven Buchprojekts. Die Reihenfolge im Buchbaum stellst "
                "du danach selbst per Drag-and-Drop her."
            )
        )
        layout.addWidget(QLabel("Profil aus der Skeleton-Bibliothek wählen:"))
        form = QFormLayout()
        self.combo = QComboBox()
        for name in profiles:
            self.combo.addItem(labels.get(name, name), name)
        form.addRow("Profil:", self.combo)
        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Optionale Snippets</b> (einzeln zuschalten):"))
        self._optional_hint = QLabel()
        self._optional_hint.setWordWrap(True)
        layout.addWidget(self._optional_hint)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("Alle optionalen")
        btn_none = QPushButton("Keine")
        btn_all.clicked.connect(self._select_all_optionals)
        btn_none.clicked.connect(self._select_no_optionals)
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._optional_scroll = QScrollArea()
        self._optional_scroll.setWidgetResizable(True)
        self._optional_scroll.setMinimumHeight(180)
        self._optional_container = QWidget()
        self._optional_layout = QVBoxLayout(self._optional_container)
        self._optional_layout.setContentsMargins(4, 4, 4, 4)
        self._optional_layout.setSpacing(4)
        self._optional_scroll.setWidget(self._optional_container)
        layout.addWidget(self._optional_scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.combo.currentIndexChanged.connect(self._reload_optional_list)
        self._reload_optional_list()

    def _clear_optional_list(self) -> None:
        while self._optional_layout.count():
            item = self._optional_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._optional_checks.clear()

    def _reload_optional_list(self) -> None:
        self._clear_optional_list()
        profile = self.combo.currentData()
        if not profile:
            self._optional_hint.setText("Kein Profil gewählt.")
            return
        try:
            optionals = list_optional_manifest_entries(self._library_root, str(profile))
        except (OSError, ValueError) as exc:
            self._optional_hint.setText(f"Manifest konnte nicht geladen werden: {exc}")
            return

        if not optionals:
            self._optional_hint.setText(
                "In diesem Profil sind keine optionalen Snippets hinterlegt "
                "(alles Pflicht oder leer)."
            )
            return

        self._optional_hint.setText(
            f"{len(optionals)} optional(e) Eintrag/Einträge – Pflicht-Rahmen "
            "wird immer übernommen; Häkchen nur für Zusätze:"
        )
        for entry in optionals:
            label = entry.title.strip() or Path(entry.path).name
            cb = QCheckBox(f"{label}  [{entry.path}]")
            cb.setChecked(False)
            tip_parts = [entry.path]
            if entry.description:
                tip_parts.append(entry.description)
            cb.setToolTip("\n".join(tip_parts))
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            self._optional_checks[entry.path] = cb
            self._optional_layout.addWidget(cb)
        self._optional_layout.addStretch(1)

    def _select_all_optionals(self) -> None:
        for cb in self._optional_checks.values():
            cb.setChecked(True)

    def _select_no_optionals(self) -> None:
        for cb in self._optional_checks.values():
            cb.setChecked(False)

    def _ok(self) -> None:
        self.selected_profile = self.combo.currentData()
        selected = [path for path, cb in self._optional_checks.items() if cb.isChecked()]
        self.selected_file_overrides = file_overrides_for_selected_optionals(selected)
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
    file_overrides = kwargs.get("file_overrides")
    if not profile:
        dlg = SkeletonPopulateQtDialog(parent, profiles, labels, library_root)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_profile:
            return 1
        profile = dlg.selected_profile
        file_overrides = dlg.selected_file_overrides or None

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
            file_overrides=file_overrides,
        )
    finally:
        studio.root = old_root

    opt_n = len(file_overrides) if isinstance(file_overrides, dict) else 0
    extra = (
        f"\nZusätzlich {opt_n} optionale(s) Snippet(s) angewählt."
        if opt_n
        else "\nKeine optionalen Snippets angewählt."
    )
    QMessageBox.information(
        parent,
        "Skeleton",
        f"Populate für Profil „{profile}“ beendet (Exit {code}).{extra}\n"
        "Details siehe Log; Kapitel ggf. links im Pool einhängen.",
    )
    return int(code or 0)


def open_skeleton_editor_qt(studio: Any, parent: Optional[QWidget] = None, **kwargs) -> int:
    """Delegiert an den vollständigen Qt-Editor (Feature-Parität zum Tk-Editor)."""
    from ui_qt.dialogs.skeleton_editor_dialog import open_skeleton_editor_qt as _full

    return _full(studio=studio, parent=parent, **kwargs)
