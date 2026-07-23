"""Buch-Doktor-Ergebnisdialog."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)


class DoctorDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        context_label: str,
        analysis: dict[str, Any],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Buch-Doktor — {context_label}")
        self.resize(640, 420)

        layout = QVBoxLayout(self)
        errors = int(analysis.get("error_count") or 0)
        warnings = int(analysis.get("warning_count") or 0)
        healthy = bool(analysis.get("is_healthy", errors == 0))
        summary = (
            "✅ Keine kritischen Befunde."
            if healthy
            else f"⚠️ {errors} Fehler, {warnings} Warnung(en)."
        )
        layout.addWidget(QLabel(summary))

        report = str(analysis.get("report") or "")
        self.list = QListWidget()
        if report.strip():
            for line in report.splitlines():
                if line.strip():
                    self.list.addItem(line.strip())
        else:
            issues = analysis.get("errors") or []
            for item in issues:
                self.list.addItem(str(item))
            for path, details in (analysis.get("issue_details_by_path") or {}).items():
                self.list.addItem(f"{path}: {details}")
        layout.addWidget(self.list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
