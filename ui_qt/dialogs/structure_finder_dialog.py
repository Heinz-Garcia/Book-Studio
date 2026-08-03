"""Buchstruktur-Finder: Snapshots über aktuelles Buch und Geschwister-Projekte."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# bookconfig-Dateien, die keine Kapitelstruktur sind
_SKIP_BOOKCONFIG_NAMES = {
    ".gui_state.json",  # separately listed with a clearer label
    "publish_map.json",
    "publish_record.json",
    "layout_profile.json",
    "distribution.json",
    "grammargraph_export.json",
}


@dataclass(frozen=True)
class StructureSnapshot:
    path: Path
    kind: str  # backup | export | gui_state
    project_name: str
    mtime: float
    node_count: int

    @property
    def label(self) -> str:
        return _snapshot_row_label(self.path, self.project_name, self.kind)


def _count_nodes(data: Any) -> int:
    if not isinstance(data, list):
        return 0

    def walk(items: list) -> int:
        n = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            n += 1
            kids = item.get("children") or item.get("chapters") or []
            if isinstance(kids, list):
                n += walk(kids)
        return n

    return walk(data)


def _try_load_tree(path: Path) -> Any | None:
    try:
        from ui_qt.structure_snapshot import load_snapshot_file

        tree, _meta = load_snapshot_file(path)
        return tree
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
        return None


def _snapshot_row_label(path: Path, project_name: str, kind: str) -> str:
    try:
        from ui_qt.structure_snapshot import format_snapshot_list_label, load_snapshot_file

        _tree, meta = load_snapshot_file(path)
        base = format_snapshot_list_label(path, meta)
        kind_de = {
            "backup": "Time-Machine",
            "export": "JSON-Export",
            "gui_state": "GUI-Cache",
        }.get(kind, kind)
        return f"{base}  ·  {project_name}  ·  {kind_de}"
    except (OSError, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return f"{project_name}  ·  {path.name}"


def book_project_roots(active_book: Path, *, extra_roots: Optional[list[Path]] = None) -> list[Path]:
    """Aktives Buch + Geschwister unter demselben Parent (+ optionale Roots)."""
    active = Path(active_book).resolve()
    roots: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        rp = p.resolve()
        if rp in seen or not rp.is_dir():
            return
        if not (rp / "_quarto.yml").is_file():
            return
        seen.add(rp)
        roots.append(rp)

    add(active)
    parent = active.parent
    if parent.is_dir():
        for child in sorted(parent.iterdir()):
            add(child)
    for extra in extra_roots or []:
        add(Path(extra))
    return roots


def _book_project_roots(active_book: Path, *, extra_roots: Optional[list[Path]] = None) -> list[Path]:
    """Alias (älterer Name)."""
    return book_project_roots(active_book, extra_roots=extra_roots)

def discover_structure_snapshots(
    active_book: Path,
    *,
    extra_roots: Optional[list[Path]] = None,
    limit: int = 200,
) -> list[StructureSnapshot]:
    """Finde Struktur-JSONs im aktiven Buch und in Geschwister-Projekten."""
    found: list[StructureSnapshot] = []
    for project in _book_project_roots(active_book, extra_roots=extra_roots):
        name = project.name
        backups = project / ".backups"
        if backups.is_dir():
            for path in backups.glob("struct_*.json"):
                tree = _try_load_tree(path)
                if tree is None:
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                found.append(
                    StructureSnapshot(
                        path=path,
                        kind="backup",
                        project_name=name,
                        mtime=mtime,
                        node_count=_count_nodes(tree),
                    )
                )
        bookconfig = project / "bookconfig"
        if bookconfig.is_dir():
            gui = bookconfig / ".gui_state.json"
            if gui.is_file():
                tree = _try_load_tree(gui)
                if tree is not None:
                    try:
                        mtime = gui.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    found.append(
                        StructureSnapshot(
                            path=gui,
                            kind="gui_state",
                            project_name=name,
                            mtime=mtime,
                            node_count=_count_nodes(tree),
                        )
                    )
            for path in bookconfig.glob("*.json"):
                if path.name in _SKIP_BOOKCONFIG_NAMES:
                    continue
                if path.name.startswith("publish_"):
                    continue
                tree = _try_load_tree(path)
                if tree is None:
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                found.append(
                    StructureSnapshot(
                        path=path,
                        kind="export",
                        project_name=name,
                        mtime=mtime,
                        node_count=_count_nodes(tree),
                    )
                )
    found.sort(key=lambda s: s.mtime, reverse=True)
    return found[: max(1, int(limit))]


class StructureFinderDialog(QDialog):
    """Liste gefundener Strukturen; Auswahl laden in die aktuelle Session."""

    def __init__(
        self,
        parent: Optional[QWidget],
        snapshots: list[StructureSnapshot],
        *,
        on_load: Callable[[list], bool],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Buchstruktur suchen & laden")
        self.resize(720, 480)
        self._snapshots = snapshots
        self._on_load = on_load

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Gefundene Struktur-Sicherungen im aktuellen Buch und in "
                "Geschwister-Projekten (Publish_*/Band_* …). "
                "Hinweis: „rev.5“ in Dateinamen ist oft ein Render-/Export-Name, "
                "keine automatische Struktur-Revision — hier siehst du echte JSON-Bäume."
            )
        )
        self._list = QListWidget()
        for snap in snapshots:
            item = QListWidgetItem(snap.label)
            item.setData(Qt.ItemDataRole.UserRole, str(snap.path))
            item.setToolTip(str(snap.path))
            self._list.addItem(item)
        layout.addWidget(self._list, stretch=1)

        buttons = QHBoxLayout()
        btn_load = QPushButton("Diese Struktur laden")
        btn_load.clicked.connect(self._load_selected)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_load)
        buttons.addStretch(1)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        if not snapshots:
            self._list.addItem("(Keine Struktur-JSONs gefunden)")

    def _load_selected(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._snapshots):
            QMessageBox.information(self, "Struktur", "Bitte einen Eintrag wählen.")
            return
        snap = self._snapshots[row]
        tree = _try_load_tree(snap.path)
        if tree is None:
            QMessageBox.warning(
                self,
                "Struktur",
                f"Datei ist keine gültige Kapitel-Liste:\n{snap.path}",
            )
            return
        if self._on_load(tree):
            self.accept()


def open_structure_finder_qt(
    parent: QWidget,
    active_book: Path,
    *,
    on_load: Callable[[list], bool],
    extra_roots: Optional[list[Path]] = None,
) -> int:
    snaps = discover_structure_snapshots(active_book, extra_roots=extra_roots)
    dlg = StructureFinderDialog(parent, snaps, on_load=on_load)
    return int(dlg.exec())
