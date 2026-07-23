"""Struktur-Preview und einfache Text-/JSON-Dialoge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class PreviewDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], text: str, *, title: str = "Preview") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


class TextEditorDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], path: Path, *, title: str = "Editor") -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.setWindowTitle(f"{title} — {self.path.name}")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit()
        try:
            self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.editor.setPlainText(f"# Lesefehler\n{exc}")
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        try:
            self.path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self.accept()


def save_json_file(parent: QWidget, data: Any, *, suggested_name: str = "buchstruktur.json") -> bool:
    path, _ = QFileDialog.getSaveFileName(
        parent, "Buchstruktur speichern", suggested_name, "JSON (*.json)"
    )
    if not path:
        return False
    try:
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except (OSError, TypeError, ValueError) as exc:
        QMessageBox.critical(parent, "Speichern fehlgeschlagen", str(exc))
        return False


def load_json_file(parent: QWidget) -> Optional[Any]:
    path, _ = QFileDialog.getOpenFileName(parent, "Buchstruktur laden", "", "JSON (*.json)")
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        QMessageBox.critical(parent, "Laden fehlgeschlagen", str(exc))
        return None
