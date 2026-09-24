"""Dialog: geplante Cover-UUID an Buch binden (wenn nicht eindeutig)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.bind_book import (
    BindCandidate,
    BindResult,
    bind_cover_to_book,
    resolve_cover_book_binding,
)

_COLUMNS = ("Arbeitstitel", "Serie", "UUID")


class CoverBindPickDialog(QDialog):
    """Auswahl unter mehreren passenden geplanten UUIDs."""

    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        book_root: Path,
        candidates: list[BindCandidate],
        message: str = "",
    ) -> None:
        super().__init__(parent)
        self._book = Path(book_root)
        self._candidates = list(candidates)
        self._chosen: BindCandidate | None = None
        self.setWindowTitle(f"Cover an Buch binden — {self._book.name}")
        self.setMinimumSize(640, 320)

        lay = QVBoxLayout(self)
        intro = QLabel(
            message
            or (
                "Mehrere geplante Covers passen. Welche Production-UUID "
                "soll an dieses Buch gebunden werden?"
            )
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().hide()
        self._table.itemDoubleClicked.connect(lambda _i: self._accept_choice())
        lay.addWidget(self._table, 1)

        self._table.setRowCount(len(self._candidates))
        for i, cand in enumerate(self._candidates):
            values = (
                cand.title_hint or "(ohne Titel)",
                cand.series_id or "—",
                cand.production_uuid,
            )
            for j, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, i)
                self._table.setItem(i, j, item)
        self._table.resizeColumnsToContents()
        if self._candidates:
            self._table.selectRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText("Binden")
        buttons.accepted.connect(self._accept_choice)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(buttons)
        lay.addLayout(row)

    def _accept_choice(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        self._chosen = self._candidates[rows[0].row()]
        self.accept()

    @property
    def chosen(self) -> BindCandidate | None:
        return self._chosen


def prompt_bind_cover_to_book(
    parent: Optional[QWidget],
    book_root: Path,
    *,
    registry_file: Path | None = None,
) -> BindResult:
    """Auto bei genau einer passenden UUID, sonst Auswahl-Dialog.

    Abbrechen bei ``needs_choice`` → Status ``skipped``.
    """
    book = Path(book_root)
    result = resolve_cover_book_binding(book, registry_file=registry_file)
    if result.status != "needs_choice":
        return result
    if not result.candidates:
        return result

    dlg = CoverBindPickDialog(
        parent,
        book_root=book,
        candidates=result.candidates,
        message=result.message,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted or dlg.chosen is None:
        return BindResult(
            status="skipped",
            book_path=str(book.resolve()),
            candidates=list(result.candidates),
            message="Cover-Bindung übersprungen.",
        )
    bound = bind_cover_to_book(
        book,
        dlg.chosen.production_uuid,
        registry_file=registry_file,
    )
    bound.status = "chosen"
    bound.candidates = list(result.candidates)
    return bound


__all__ = [
    "CoverBindPickDialog",
    "prompt_bind_cover_to_book",
]
