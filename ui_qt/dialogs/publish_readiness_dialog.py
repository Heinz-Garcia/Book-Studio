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
from tools.publish_readiness.navigation import jump_to_issue
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.widgets.help_bar import HelpBar

_SIZE_KEY = "publish_readiness_size"
_DEFAULT_SIZE = (980, 520)
_MIN_SIZE = (640, 360)
_active: list[PublishReadinessQtDialog] = []


class PublishReadinessQtDialog(QDialog):
    def __init__(
        self,
        host: Optional[QWidget],
        studio: Any,
        *,
        analysis: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> None:
        super().__init__(None)
        self.studio = studio
        self._issues = issues
        self.setWindowTitle("Publish Readiness")
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )

        healthy = bool(analysis.get("is_healthy"))
        status = "Bereit" if healthy else "Nicht bereit"
        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "publish_readiness")
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
        self.table.setToolTip("Doppelklick oder „Zur Stelle…“: Datei im Editor öffnen.")
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
        self.table.itemDoubleClicked.connect(self._zur_stelle)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(row, tool_key="publish_readiness", host=self)
        jump = QPushButton("Zur Stelle…")
        jump.setToolTip("Öffnet die Datei des ausgewählten Befunds im Editor.")
        jump.clicked.connect(self._zur_stelle)
        row.addWidget(jump)
        row.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
        prepare_autonomous_window(self, host)

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)

    def _ausgewaehlter_befund(self) -> Optional[dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._issues):
            return None
        return self._issues[row]

    def _zur_stelle(self, *_args: Any) -> None:
        issue = self._ausgewaehlter_befund()
        if issue is None:
            QMessageBox.information(
                self, "Publish Readiness", "Bitte zuerst einen Befund auswählen."
            )
            return
        jump_to_issue(self.studio, issue, parent=self)


def open_publish_readiness_qt(studio: Any, parent: Optional[QWidget] = None, **kwargs) -> None:
    if not getattr(studio, "current_book", None):
        from ui_qt.work_path_guidance import warn_need_book

        warn_need_book(parent, title="Publish Readiness", studio=studio)
        return
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
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
    dlg = PublishReadinessQtDialog(parent, studio, analysis=analysis, issues=issues)
    show_autonomous_window(dlg, _active)
