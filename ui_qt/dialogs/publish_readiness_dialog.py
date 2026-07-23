"""Qt Publish-Readiness-Dialog."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.publish_readiness.analysis import enrich_analysis


class PublishReadinessQtDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        studio: Any,
        *,
        analysis: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> None:
        super().__init__(parent)
        self.studio = studio
        self._issues = issues
        self.setWindowTitle("Publish Readiness")
        self.resize(980, 520)

        healthy = bool(analysis.get("is_healthy"))
        status = "Bereit" if healthy else "Nicht bereit"
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Status: {status}"))

        blockers = sum(1 for i in issues if i.get("severity") == "blocker")
        warnings = sum(1 for i in issues if i.get("severity") == "warning")
        layout.addWidget(
            QLabel(f"{len(issues)} Befunde · {blockers} Blocker · {warnings} Warnungen")
        )

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Schwere", "Owner", "Pfad", "Kurztext", "Fix-Spur"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            vals = [
                str(issue.get("severity") or ""),
                str(issue.get("owner_label") or issue.get("owner") or ""),
                str(issue.get("path") or ""),
                str(issue.get("message") or "")[:120],
                str(issue.get("fix_lane_label") or issue.get("fix_lane") or "")[:80],
            ]
            for col, text in enumerate(vals):
                self.table.setItem(row, col, QTableWidgetItem(text))
        layout.addWidget(self.table)

        row = QHBoxLayout()
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)


def open_publish_readiness_qt(studio: Any, parent: Optional[QWidget] = None, **kwargs) -> None:
    if not getattr(studio, "current_book", None):
        QMessageBox.warning(parent, "Publish Readiness", "Kein Buchprojekt aktiv.")
        return
    analysis = kwargs.get("analysis")
    if analysis is None:
        runner = getattr(studio, "run_doctor_preflight", None) or getattr(
            studio, "_run_doctor_check", None
        )
        if callable(runner):
            _, analysis = runner("Publish Readiness", emit_success_log=False)
    if not analysis:
        QMessageBox.warning(parent, "Publish Readiness", "Buch-Doktor-Analyse nicht verfügbar.")
        return
    issues = enrich_analysis(analysis, studio=studio)
    PublishReadinessQtDialog(parent, studio, analysis=analysis, issues=issues).exec()
