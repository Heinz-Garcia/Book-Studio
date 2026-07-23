"""Fehlende Bildreferenzen (Qt) + Explorer-Hilfe."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from markdown_asset_scanner import find_missing_image_refs
from ui_qt.dialogs.text_dialogs import TextEditorDialog


def reveal_path_in_explorer(path: Path) -> None:
    path = Path(path).resolve()
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(["explorer", f"/select,{path}"])  # noqa: S603
    elif system == "Darwin":
        subprocess.Popen(["open", "-R", str(path)])  # noqa: S603
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603


def open_book_file_in_explorer(parent: Optional[QWidget], book: Path, rel_path: str) -> None:
    f_path = Path(book) / rel_path
    if not f_path.exists():
        QMessageBox.warning(parent, "Geister-Datei", "Die Datei existiert nicht mehr auf der Festplatte.")
        return
    try:
        reveal_path_in_explorer(f_path)
    except (OSError, subprocess.SubprocessError) as exc:
        QMessageBox.critical(parent, "Fehler", f"Explorer konnte nicht geöffnet werden:\n{exc}")


class MissingImagesDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        file_path: str,
        abs_path: Path,
        missing_refs: Sequence[tuple[int, str]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fehlende Bilder")
        self.resize(720, 420)
        self._abs_path = abs_path
        self._refs = list(missing_refs)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Datei: {file_path}"))
        layout.addWidget(QLabel(f"Nicht gefundene Bildreferenzen: {len(self._refs)}"))
        layout.addWidget(
            QLabel("Doppelklick öffnet den Editor (Zeile als Hinweis im Dateinamen-Kontext).")
        )
        self._list = QListWidget()
        for line_no, target in self._refs:
            self._list.addItem(f"Z. {line_no}: {target}")
        self._list.itemDoubleClicked.connect(lambda *_: self._open_editor())
        layout.addWidget(self._list, stretch=1)

        buttons = QHBoxLayout()
        open_btn = QPushButton("Im Editor öffnen")
        open_btn.clicked.connect(self._open_editor)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(open_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _open_editor(self) -> None:
        if not self._abs_path.is_file():
            QMessageBox.warning(self, "Fehlende Bilder", f"Datei nicht gefunden:\n{self._abs_path}")
            return
        TextEditorDialog(self, self._abs_path, title=f"Editor — {self._abs_path.name}").exec()


def show_missing_images_for_path(parent: Optional[QWidget], book: Path, rel_path: str) -> None:
    if not str(rel_path).lower().endswith(".md"):
        QMessageBox.information(parent, "Fehlende Bilder", "Die Auswahl ist keine Markdown-Datei.")
        return
    abs_path = Path(book) / rel_path
    if not abs_path.is_file():
        QMessageBox.warning(parent, "Fehlende Bilder", f"Datei nicht gefunden:\n{abs_path}")
        return
    try:
        text = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        QMessageBox.critical(parent, "Fehlende Bilder", str(exc))
        return
    missing = find_missing_image_refs(text, abs_path, book)
    if not missing:
        QMessageBox.information(parent, "Fehlende Bilder", "Keine fehlenden Bildreferenzen gefunden.")
        return
    MissingImagesDialog(
        parent,
        file_path=rel_path,
        abs_path=abs_path,
        missing_refs=missing,
    ).exec()
