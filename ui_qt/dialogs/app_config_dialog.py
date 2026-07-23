"""Minimaler Studio-Config-Dialog (Kernfelder)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import app_config as _app_config
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


class AppConfigDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], config_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Studio-Konfiguration")
        self.resize(560, 320)
        self.config_path = Path(config_path)
        try:
            self.data: dict[str, Any] = _app_config.read_config(self.config_path)
        except (OSError, TypeError, ValueError):
            self.data = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        root_val = self.data.get("content_root_path", ".")
        if isinstance(root_val, list):
            root_val = ", ".join(str(x) for x in root_val)
        self.content_root = QLineEdit(str(root_val))
        form.addRow("content_root_path:", self.content_root)

        self.export_format = QComboBox()
        self.export_format.addItems(["typst", "docx", "html", "pdf"])
        self.export_format.setCurrentText(
            str(self.data.get("default_export_format") or "typst")
        )
        form.addRow("default_export_format:", self.export_format)

        self.export_template = QLineEdit(
            str(self.data.get("default_export_template") or "Standard")
        )
        form.addRow("default_export_template:", self.export_template)

        self.abort_preflight = QCheckBox("abort_on_first_preflight_error")
        self.abort_preflight.setChecked(
            bool(self.data.get("abort_on_first_preflight_error", True))
        )
        form.addRow(self.abort_preflight)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        raw_root = self.content_root.text().strip() or "."
        if "," in raw_root:
            self.data["content_root_path"] = [p.strip() for p in raw_root.split(",") if p.strip()]
        else:
            self.data["content_root_path"] = raw_root
        self.data["default_export_format"] = self.export_format.currentText()
        self.data["default_export_template"] = self.export_template.text().strip() or "Standard"
        self.data["abort_on_first_preflight_error"] = self.abort_preflight.isChecked()
        try:
            _app_config.write_config(self.config_path, self.data)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self.accept()
