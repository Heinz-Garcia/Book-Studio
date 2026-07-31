"""Datei aus Geschwister-Buchprojekt holen und im aktiven Buch ersetzen."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.dialogs.structure_finder_dialog import book_project_roots

_COMMON_RELS = (
    "content/Deckblatt.md",
    "content/Schmutztitel.md",
    "content/Haupttitel.md",
    "content/Impressum.md",
    "content/IVZ.md",
    "content/Widmung.md",
    "content/Einleitung.md",
    "content/Vorwort.md",
    "content/UeberAutor.md",
    "content/Rueckseite.md",
    "typst-show.typ",
    "page.typ",
)


@dataclass(frozen=True)
class FileCandidate:
    source_path: Path
    project_name: str
    rel_path: str
    mtime: float
    size: int

    @property
    def label(self) -> str:
        try:
            stamp = datetime.fromtimestamp(self.mtime).strftime("%d.%m.%Y %H:%M")
        except (OSError, OverflowError, ValueError):
            stamp = "?"
        return f"{stamp}  ·  {self.project_name}  ·  {self.size} Bytes  ·  {self.rel_path}"


def normalize_book_rel(rel: str) -> str:
    return str(rel or "").replace("\\", "/").lstrip("./").strip()


def discover_file_candidates(
    active_book: Path,
    rel_path: str,
    *,
    extra_roots: Optional[list[Path]] = None,
    include_active: bool = False,
) -> list[FileCandidate]:
    """Finde dieselbe relative Datei in Geschwister-Projekten (neueste zuerst)."""
    rel = normalize_book_rel(rel_path)
    if not rel:
        return []
    active = Path(active_book).resolve()
    found: list[FileCandidate] = []
    for project in book_project_roots(active, extra_roots=extra_roots):
        if not include_active and project.resolve() == active:
            continue
        candidate = project / rel
        if not candidate.is_file():
            continue
        try:
            st = candidate.stat()
        except OSError:
            continue
        found.append(
            FileCandidate(
                source_path=candidate,
                project_name=project.name,
                rel_path=rel,
                mtime=st.st_mtime,
                size=int(st.st_size),
            )
        )
    found.sort(key=lambda c: c.mtime, reverse=True)
    return found


def backup_then_copy(source: Path, dest: Path, *, backup_root: Path) -> Path | None:
    """Kopiert *source* nach *dest*; vorhandenes Ziel vorher unter backup_root sichern."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if dest.is_file():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_name = dest.name
        backup_dir = backup_root / "file-fetch"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{dest.stem}.bak-{stamp}{dest.suffix}"
        shutil.copy2(dest, backup_path)
    shutil.copy2(source, dest)
    return backup_path


class FileFetchDialog(QDialog):
    """Suche Datei-Versionen in Publish-Geschwistern und ersetze im aktiven Buch."""

    def __init__(
        self,
        parent: Optional[QWidget],
        active_book: Path,
        *,
        initial_rel: str = "content/Deckblatt.md",
        suggested_rels: Optional[list[str]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Datei aus anderem Projekt holen")
        self.resize(760, 560)
        self._book = Path(active_book)
        self._candidates: list[FileCandidate] = []
        self.replaced_rel: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Sucht dieselbe relative Datei in Geschwister-Buchprojekten "
                "(Publish_*/Band_*) und ersetzt die Datei im aktiven Buch "
                "(vorher Backup unter .backups/file-fetch/)."
            )
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("Datei:"))
        self._rel_combo = QComboBox()
        self._rel_combo.setEditable(True)
        suggestions = list(dict.fromkeys([*(suggested_rels or []), *_COMMON_RELS]))
        for rel in suggestions:
            self._rel_combo.addItem(rel)
        initial = normalize_book_rel(initial_rel) or "content/Deckblatt.md"
        idx = self._rel_combo.findText(initial)
        if idx >= 0:
            self._rel_combo.setCurrentIndex(idx)
        else:
            self._rel_combo.setEditText(initial)
        row.addWidget(self._rel_combo, stretch=1)
        btn_scan = QPushButton("Suchen")
        btn_scan.clicked.connect(self._rescan)
        row.addWidget(btn_scan)
        layout.addLayout(row)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._preview_row)
        layout.addWidget(self._list, stretch=1)

        layout.addWidget(QLabel("Vorschau (Anfang der Quelldatei):"))
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(160)
        layout.addWidget(self._preview)

        buttons = QHBoxLayout()
        btn_apply = QPushButton("Diese Version ins aktuelle Buch übernehmen")
        btn_apply.clicked.connect(self._apply)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_apply)
        buttons.addStretch(1)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        self._rescan()

    def _current_rel(self) -> str:
        return normalize_book_rel(self._rel_combo.currentText())

    def _rescan(self) -> None:
        rel = self._current_rel()
        self._candidates = discover_file_candidates(self._book, rel)
        self._list.clear()
        self._preview.clear()
        if not rel:
            self._list.addItem("(Bitte einen relativen Pfad angeben, z. B. content/Deckblatt.md)")
            return
        if not self._candidates:
            self._list.addItem(f"(Keine Treffer für „{rel}“ in Geschwister-Projekten)")
            return
        for cand in self._candidates:
            item = QListWidgetItem(cand.label)
            item.setData(Qt.ItemDataRole.UserRole, str(cand.source_path))
            item.setToolTip(str(cand.source_path))
            self._list.addItem(item)
        self._list.setCurrentRow(0)

    def _preview_row(self, row: int) -> None:
        self._preview.clear()
        if row < 0 or row >= len(self._candidates):
            return
        path = self._candidates[row].source_path
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._preview.setPlainText(f"(Lesen fehlgeschlagen: {exc})")
            return
        self._preview.setPlainText(text[:4000] + ("\n…" if len(text) > 4000 else ""))

    def _apply(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._candidates):
            QMessageBox.information(self, "Datei holen", "Bitte eine Quellversion wählen.")
            return
        cand = self._candidates[row]
        dest = self._book / cand.rel_path
        if dest.resolve() == cand.source_path.resolve():
            QMessageBox.information(self, "Datei holen", "Quelle und Ziel sind identisch.")
            return
        msg = (
            f"Ersetzen?\n\n"
            f"Ziel:  {dest}\n"
            f"Quelle: {cand.source_path}\n\n"
            f"Vorhandene Zieldatei wird unter .backups/file-fetch/ gesichert."
        )
        if (
            QMessageBox.question(self, "Datei übernehmen", msg)
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            backup = backup_then_copy(
                cand.source_path,
                dest,
                backup_root=self._book / ".backups",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Datei holen", str(exc))
            return
        self.replaced_rel = cand.rel_path
        extra = f"\nBackup: {backup}" if backup else ""
        QMessageBox.information(
            self,
            "Datei übernommen",
            f"„{cand.rel_path}“ wurde ersetzt.{extra}",
        )
        self.accept()


def open_file_fetch_qt(
    parent: QWidget,
    active_book: Path,
    *,
    initial_rel: str = "content/Deckblatt.md",
    suggested_rels: Optional[list[str]] = None,
) -> Optional[str]:
    """Öffnet den Dialog; liefert den ersetzten Rel-Pfad oder None."""
    dlg = FileFetchDialog(
        parent,
        active_book,
        initial_rel=initial_rel,
        suggested_rels=suggested_rels,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.replaced_rel
