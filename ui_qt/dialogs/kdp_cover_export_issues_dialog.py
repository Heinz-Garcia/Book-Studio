"""KDP Cover — Export-Hinweise als filter-/sortierbare Tabelle.

Ersetzt den alten Text-/MessageBox-Bestätigungsdialog beim PDF-Export.
Fenstergröße: ``tools.kdp_cover.settings`` (confirm_* Keys).
"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.settings import (
    load_settings,
    resolve_confirm_window_size,
    save_settings,
)
from tools.kdp_cover.validate import ValidationIssue

_SEVERITY_LABEL = {"error": "Fehler", "warning": "Warnung"}
_SEVERITY_SORT = {"error": 0, "warning": 1}
_SEVERITY_FG = {
    "error": QColor("#b91c1c"),
    "warning": QColor("#b45309"),
}


class KdpExportIssuesDialog(QDialog):
    """Zeigt Validierungsissues in einer filterbaren, sortierbaren Tabelle."""

    def __init__(
        self,
        parent: Optional[QWidget],
        issues: Iterable[ValidationIssue],
        *,
        title: str,
        intro: str,
        require_ack: bool = False,
        accept_label: str = "Trotzdem exportieren",
        reject_label: str = "Abbrechen",
        display_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("kdpExportIssuesDialog")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(560, 360)
        self._require_ack = bool(require_ack) and not display_only
        self._display_only = bool(display_only)
        self._issues = list(issues)

        try:
            settings = load_settings()
            ww, wh = resolve_confirm_window_size(settings)
            self._restore_maximized = bool(settings.get("confirm_window_maximized"))
        except OSError:
            ww, wh = 720, 480
            self._restore_maximized = False
        self.resize(ww, wh)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        intro_lbl = QLabel(intro)
        intro_lbl.setWordWrap(True)
        intro_lbl.setStyleSheet("color:#1c2740; font-size:13px;")
        root.addWidget(intro_lbl)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet("color:#5b6573;")
        filter_row.addWidget(filter_lbl)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Text in Stufe, Code oder Meldung…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit, stretch=1)
        self.filter_count = QLabel("")
        self.filter_count.setStyleSheet("color:#64748b; font-size:12px;")
        filter_row.addWidget(self.filter_count)
        root.addLayout(filter_row)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("kdpExportIssuesTable")
        self.table.setHorizontalHeaderLabels(["Stufe", "Code", "Meldung"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSortIndicatorShown(True)
        self.table.setStyleSheet(
            """
            QTableWidget#kdpExportIssuesTable {
                border: 1px solid #c8d3ec;
                border-radius: 6px;
                gridline-color: #e2e8f0;
                background: #ffffff;
                alternate-background-color: #f7f9fd;
            }
            QHeaderView::section {
                background: #eef1f8;
                color: #1c2740;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #c8d3ec;
                border-bottom: 1px solid #c8d3ec;
                font-weight: 600;
            }
            """
        )
        root.addWidget(self.table, stretch=1)
        self._fill_table(self._issues)
        self._apply_filter("")

        self.ack: QCheckBox | None = None
        if self._require_ack:
            self.ack = QCheckBox(
                "Ich habe die Warnungen/Fehler gelesen und übernehme "
                "die Verantwortung für den KDP-Upload."
            )
            self.ack.setStyleSheet("font-weight:600; color:#1c2740;")
            root.addWidget(self.ack)

        if self._display_only:
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
            if close_btn is not None:
                close_btn.setText(reject_label or "Schließen")
            self._yes = close_btn
            buttons.rejected.connect(self.reject)
            buttons.accepted.connect(self.reject)
            root.addWidget(buttons)
        else:
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
            )
            self._yes = buttons.button(QDialogButtonBox.StandardButton.Yes)
            self._yes.setText(accept_label)
            no_btn = buttons.button(QDialogButtonBox.StandardButton.No)
            no_btn.setText(reject_label)
            if self._require_ack:
                self._yes.setEnabled(False)
                assert self.ack is not None
                self.ack.toggled.connect(self._yes.setEnabled)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            root.addWidget(buttons)

    def _fill_table(self, issues: list[ValidationIssue]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for issue in issues:
            row = self.table.rowCount()
            self.table.insertRow(row)
            sev = (issue.severity or "").strip().lower() or "warning"
            sev_item = QTableWidgetItem(_SEVERITY_LABEL.get(sev, sev))
            sev_item.setData(Qt.ItemDataRole.UserRole, _SEVERITY_SORT.get(sev, 9))
            fg = _SEVERITY_FG.get(sev)
            if fg is not None:
                sev_item.setForeground(fg)
            sev_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )

            code_item = QTableWidgetItem(str(issue.code or ""))
            msg_item = QTableWidgetItem(str(issue.message or ""))
            msg_item.setToolTip(str(issue.message or ""))

            self.table.setItem(row, 0, sev_item)
            self.table.setItem(row, 1, code_item)
            self.table.setItem(row, 2, msg_item)
            self.table.setRowHeight(row, max(28, msg_item.sizeHint().height()))
        self.table.setSortingEnabled(True)
        # Fehler zuerst.
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").casefold().strip()
        visible = 0
        total = self.table.rowCount()
        for row in range(total):
            if not needle:
                show = True
            else:
                parts: list[str] = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item is not None:
                        parts.append(item.text())
                show = needle in " ".join(parts).casefold()
            self.table.setRowHidden(row, not show)
            if show:
                visible += 1
        self.filter_count.setText(f"{visible} / {total}")

    def _persist_geometry(self) -> None:
        try:
            maximized = bool(self.isMaximized())
            if maximized:
                geo = self.normalGeometry()
                width, height = int(geo.width()), int(geo.height())
            else:
                width, height = int(self.width()), int(self.height())
            save_settings(
                {
                    "confirm_window_width": width,
                    "confirm_window_height": height,
                    "confirm_window_maximized": maximized,
                }
            )
        except OSError:
            pass

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if getattr(self, "_restore_maximized", False):
            self._restore_maximized = False
            self.showMaximized()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._persist_geometry()
        super().closeEvent(event)

    def accept(self) -> None:
        self._persist_geometry()
        super().accept()

    def reject(self) -> None:
        self._persist_geometry()
        super().reject()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)


__all__ = ["KdpExportIssuesDialog"]
