"""Rahmen/Pflichtseiten — Übersicht, Kontrolle und Bearbeitung."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.rahmen_pages import (
    RahmenPageKind,
    assess_rahmen_pages,
)
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)

_SIZE_KEY = "rahmen_pages_size"
_DEFAULT_SIZE = (720, 480)
_MIN_SIZE = (480, 320)
_active: list["RahmenPagesDialog"] = []

_KIND_LABEL = {
    RahmenPageKind.OK: "OK",
    RahmenPageKind.WARN: "Warnung",
    RahmenPageKind.ERROR: "Fehler",
}
_KIND_COLOR = {
    RahmenPageKind.OK: QColor("#166534"),
    RahmenPageKind.WARN: QColor("#b45309"),
    RahmenPageKind.ERROR: QColor("#b91c1c"),
}


class RahmenPagesDialog(QDialog):
    """Liste der Pflichtseiten mit Status; Bearbeiten öffnet den Markdown-Editor."""

    def __init__(
        self,
        book_path: Path,
        *,
        host: Optional[QWidget] = None,
        on_populate: Optional[Any] = None,
        on_changed: Optional[Any] = None,
    ) -> None:
        super().__init__(None)
        self._book = Path(book_path)
        self._on_populate = on_populate
        self._on_changed = on_changed
        self.setWindowTitle(f"Rahmen / Pflichtseiten — {self._book.name}")
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )
        prepare_autonomous_window(self, host)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Pflichtseiten (required) im Buch prüfen und bearbeiten. "
            "Fehlende Rahmen: „Skeleton übernehmen…“."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._summary = QLabel("")
        self._summary.setStyleSheet("color: #475569;")
        layout.addWidget(self._summary)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Status", "Titel", "Pfad"])
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.itemDoubleClicked.connect(self._edit_current)
        layout.addWidget(self._tree, stretch=1)

        row = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(row, tool_key="rahmen_pages", host=self)
        self._btn_edit = QPushButton("Bearbeiten…")
        self._btn_edit.clicked.connect(self._edit_current)
        row.addWidget(self._btn_edit)
        self._btn_refresh = QPushButton("Aktualisieren")
        self._btn_refresh.clicked.connect(self.reload)
        row.addWidget(self._btn_refresh)
        self._btn_populate = QPushButton("Skeleton übernehmen…")
        self._btn_populate.setToolTip(
            "Pflicht-Rahmen aus der Skeleton-Bibliothek in den Buch-Pool kopieren."
        )
        self._btn_populate.clicked.connect(self._run_populate)
        row.addWidget(self._btn_populate)
        row.addStretch(1)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Schließen")
        layout.addWidget(buttons)

        self.reload()

    def reload(self) -> None:
        self._tree.clear()
        pages = assess_rahmen_pages(self._book)
        errors = sum(1 for p in pages if p.kind == RahmenPageKind.ERROR)
        warns = sum(1 for p in pages if p.kind == RahmenPageKind.WARN)
        if not pages:
            self._summary.setText(
                "Keine Pflichtseiten gefunden — Skeleton übernehmen oder "
                "Seiten mit required: true anlegen."
            )
        else:
            parts = [f"{len(pages)} Seite(n)"]
            if errors:
                parts.append(f"{errors} Fehler")
            if warns:
                parts.append(f"{warns} Warnung(en)")
            if not errors and not warns:
                parts.append("alle ok")
            self._summary.setText(" · ".join(parts))

        for page in pages:
            item = QTreeWidgetItem(
                [
                    _KIND_LABEL.get(page.kind, "?"),
                    page.title or "—",
                    page.rel_path,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, page.rel_path)
            item.setToolTip(0, page.detail)
            item.setToolTip(1, page.detail)
            item.setToolTip(2, page.detail)
            color = _KIND_COLOR.get(page.kind)
            if color is not None:
                item.setForeground(0, color)
            self._tree.addTopLevelItem(item)
        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)
        self._btn_edit.setEnabled(bool(pages))

    def _current_rel(self) -> Optional[str]:
        item = self._tree.currentItem()
        if item is None:
            return None
        rel = item.data(0, Qt.ItemDataRole.UserRole)
        return str(rel) if rel else None

    def _edit_current(self, *_args: Any) -> None:
        rel = self._current_rel()
        if not rel:
            QMessageBox.information(
                self, "Rahmen", "Bitte eine Seite in der Liste wählen."
            )
            return
        abs_path = self._book / rel
        if not abs_path.is_file():
            QMessageBox.warning(
                self,
                "Rahmen",
                f"Datei fehlt:\n{abs_path}\n\nSkeleton übernehmen oder Datei anlegen.",
            )
            return
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        def _after_save() -> None:
            self.reload()
            if self._on_changed is not None:
                try:
                    self._on_changed()
                except Exception:  # noqa: BLE001 — UI-Refresh darf Editor nicht stören
                    pass

        TextEditorDialog(
            self,
            abs_path,
            title="Rahmen bearbeiten",
            book_path=self._book,
            on_save=_after_save,
        ).exec()
        self.reload()
        if self._on_changed is not None:
            try:
                self._on_changed()
            except Exception:  # noqa: BLE001
                pass

    def _run_populate(self) -> None:
        if self._on_populate is None:
            QMessageBox.information(
                self,
                "Skeleton",
                "Skeleton-Übernahme ist hier nicht angebunden — "
                "Bitte Menü: Skeleton-Rahmen übernehmen.",
            )
            return
        try:
            self._on_populate()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Skeleton", str(exc))
        self.reload()
        if self._on_changed is not None:
            try:
                self._on_changed()
            except Exception:  # noqa: BLE001
                pass

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)


def open_rahmen_pages_dialog(
    book_path: Path,
    *,
    host: Optional[QWidget] = None,
    on_populate: Optional[Any] = None,
    on_changed: Optional[Any] = None,
) -> RahmenPagesDialog:
    """Öffnet (oder hebt) den Rahmen-Kontrolldialog für das Buch."""
    book = Path(book_path).resolve()
    found = raise_if_open(_active, lambda d: Path(d._book).resolve() == book)
    if found is not None:
        found.reload()
        return found
    dlg = RahmenPagesDialog(
        book,
        host=host,
        on_populate=on_populate,
        on_changed=on_changed,
    )
    return show_autonomous_window(dlg, _active)


__all__ = [
    "RahmenPagesDialog",
    "open_rahmen_pages_dialog",
]
