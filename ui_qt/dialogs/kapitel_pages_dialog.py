"""Kapitel/Buchstruktur — Übersicht, Kontrolle und Bearbeitung."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

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

from services.kapitel_structure import (
    KapitelPageKind,
    assess_kapitel_pages,
)
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)

_SIZE_KEY = "kapitel_pages_size"
_DEFAULT_SIZE = (760, 480)
_MIN_SIZE = (520, 320)
_active: list["KapitelPagesDialog"] = []

_KIND_LABEL = {
    KapitelPageKind.OK: "OK",
    KapitelPageKind.WARN: "Warnung",
    KapitelPageKind.ERROR: "Fehler",
}
_KIND_COLOR = {
    KapitelPageKind.OK: QColor("#166534"),
    KapitelPageKind.WARN: QColor("#b45309"),
    KapitelPageKind.ERROR: QColor("#b91c1c"),
}


class KapitelPagesDialog(QDialog):
    """Strukturierte Kapitel inkl. fehlender Required; Bearbeiten = Markdown-Editor."""

    def __init__(
        self,
        book_path: Path,
        *,
        host: Optional[QWidget] = None,
        structure_paths: Optional[list[str]] = None,
        on_content_swap: Optional[Callable[[], None]] = None,
        on_add_required: Optional[Callable[[], None]] = None,
        on_changed: Optional[Callable[[], None]] = None,
        get_structure_paths: Optional[Callable[[], Optional[list[str]]]] = None,
    ) -> None:
        super().__init__(None)
        self._book = Path(book_path)
        self._structure_paths = structure_paths
        self._get_structure_paths = get_structure_paths
        self._on_content_swap = on_content_swap
        self._on_add_required = on_add_required
        self._on_changed = on_changed
        self.setWindowTitle(f"Kapitel / Buchstruktur — {self._book.name}")
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )
        prepare_autonomous_window(self, host)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Unterschied zu Rahmen: Rahmen = Pflicht-Dateien existieren; "
            "Kapitel = sie stehen in der Buchstruktur und Nutzkapitel haben Inhalt. "
            "Fehlende Required: „Required einfügen…“ oder Strukturpanel."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._summary = QLabel("")
        self._summary.setStyleSheet("color: #475569;")
        layout.addWidget(self._summary)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Status", "Titel", "Wörter", "Pfad"])
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.itemDoubleClicked.connect(self._edit_current)
        layout.addWidget(self._tree, stretch=1)

        row = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(row, tool_key="kapitel_pages", host=self)
        self._btn_edit = QPushButton("Bearbeiten…")
        self._btn_edit.clicked.connect(self._edit_current)
        row.addWidget(self._btn_edit)
        self._btn_refresh = QPushButton("Aktualisieren")
        self._btn_refresh.clicked.connect(self.reload)
        row.addWidget(self._btn_refresh)
        self._btn_add_req = QPushButton("Required einfügen…")
        self._btn_add_req.setToolTip(
            "Alle Pflichtseiten aus dem Pool in die Buchstruktur übernehmen "
            "(wie „Hinzufügen (all required)“)."
        )
        self._btn_add_req.clicked.connect(self._run_add_required)
        row.addWidget(self._btn_add_req)
        self._btn_swap = QPushButton("Inhalt tauschen…")
        self._btn_swap.setToolTip("GrammarGraph-Inhalt in Kapitel übernehmen.")
        self._btn_swap.clicked.connect(self._run_content_swap)
        row.addWidget(self._btn_swap)
        self._btn_skip = QPushButton("Buchstruktur so belassen — Skip")
        self._btn_skip.setMinimumHeight(36)
        self._btn_skip.setStyleSheet(
            "QPushButton { background-color: #0f766e; color: white; font-weight: 700; "
            "padding: 8px 14px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0d9488; }"
        )
        self._btn_skip.setToolTip(
            "Rechte Buchstruktur akzeptieren — ohne GrammarGraph-Tausch."
        )
        self._btn_skip.clicked.connect(self._accept_as_is)
        row.addWidget(self._btn_skip)
        row.addStretch(1)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Schließen")
        layout.addWidget(buttons)

        self.reload()

    def _resolved_structure_paths(self) -> Optional[list[str]]:
        if self._get_structure_paths is not None:
            try:
                return self._get_structure_paths()
            except Exception:  # noqa: BLE001
                return self._structure_paths
        return self._structure_paths

    def reload(self) -> None:
        self._tree.clear()
        paths = self._resolved_structure_paths()
        pages = assess_kapitel_pages(self._book, structure_paths=paths)
        errors = sum(1 for p in pages if p.kind == KapitelPageKind.ERROR)
        missing = sum(1 for p in pages if not p.in_structure)
        if not pages:
            self._summary.setText(
                "Keine Kapitel in der Struktur — Required einfügen oder "
                "Seiten rechts zuordnen."
            )
        else:
            parts = [f"{len(pages)} Eintrag/Einträge"]
            if missing:
                parts.append(f"{missing} Required fehlt in Struktur")
            if errors:
                parts.append(f"{errors} Fehler")
            if not errors:
                parts.append("alle ok")
            self._summary.setText(" · ".join(parts))

        for page in pages:
            words_txt = "—" if not page.in_structure else str(page.words)
            item = QTreeWidgetItem(
                [
                    _KIND_LABEL.get(page.kind, "?"),
                    page.title or "—",
                    words_txt,
                    page.rel_path,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, page.rel_path)
            item.setData(1, Qt.ItemDataRole.UserRole, page.in_structure)
            tip = page.detail
            if page.is_required:
                tip = f"[required] {tip}"
            for col in range(4):
                item.setToolTip(col, tip)
            color = _KIND_COLOR.get(page.kind)
            if color is not None:
                item.setForeground(0, color)
            self._tree.addTopLevelItem(item)
        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)
        self._tree.resizeColumnToContents(2)
        has_file = any(
            (self._book / p.rel_path).is_file()
            for p in pages
            if p.rel_path
        )
        self._btn_edit.setEnabled(has_file)
        self._btn_add_req.setEnabled(self._on_add_required is not None)
        self._btn_swap.setEnabled(self._on_content_swap is not None)

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
                self, "Kapitel", "Bitte einen Eintrag in der Liste wählen."
            )
            return
        abs_path = self._book / rel
        if not abs_path.is_file():
            QMessageBox.warning(
                self,
                "Kapitel",
                f"Datei fehlt:\n{abs_path}\n\nZuerst anlegen oder Required einfügen.",
            )
            return
        from ui_qt.dialogs.text_dialogs import open_text_editor

        def _after_save() -> None:
            self.reload()
            self._emit_changed()

        def _after_close() -> None:
            self.reload()
            self._emit_changed()

        open_text_editor(
            self,
            abs_path,
            title="Kapitel bearbeiten",
            book_path=self._book,
            on_save=_after_save,
            on_finished=_after_close,
        )

    def _run_add_required(self) -> None:
        if self._on_add_required is None:
            QMessageBox.information(
                self,
                "Struktur",
                "Required-Einfügen ist hier nicht angebunden — "
                "bitte im Strukturpanel „Hinzufügen (all required)“.",
            )
            return
        try:
            self._on_add_required()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Struktur", str(exc))
        self.reload()
        self._emit_changed()

    def _run_content_swap(self) -> None:
        if self._on_content_swap is None:
            QMessageBox.information(
                self,
                "Inhalt",
                "Inhaltstausch ist hier nicht angebunden — Menü: Kapitelinhalt.",
            )
            return
        try:
            self._on_content_swap()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Inhalt", str(exc))
        self.reload()
        self._emit_changed()

    def _accept_as_is(self) -> None:
        from services.work_path import accept_kapitel_structure_as_is

        ok, message = accept_kapitel_structure_as_is(
            self._book, structure_paths=self._resolved_structure_paths()
        )
        if not ok:
            QMessageBox.warning(self, "Buchstruktur so belassen", message)
            return
        self._emit_changed()
        self.accept()

    def _emit_changed(self) -> None:
        if self._on_changed is not None:
            try:
                self._on_changed()
            except Exception:  # noqa: BLE001
                pass

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)


def open_kapitel_pages_dialog(
    book_path: Path,
    *,
    host: Optional[QWidget] = None,
    structure_paths: Optional[list[str]] = None,
    on_content_swap: Optional[Callable[[], None]] = None,
    on_add_required: Optional[Callable[[], None]] = None,
    on_changed: Optional[Callable[[], None]] = None,
    get_structure_paths: Optional[Callable[[], Optional[list[str]]]] = None,
) -> KapitelPagesDialog:
    book = Path(book_path).resolve()
    found = raise_if_open(_active, lambda d: Path(d._book).resolve() == book)
    if found is not None:
        found._structure_paths = structure_paths
        found._get_structure_paths = get_structure_paths
        found.reload()
        return found
    dlg = KapitelPagesDialog(
        book,
        host=host,
        structure_paths=structure_paths,
        on_content_swap=on_content_swap,
        on_add_required=on_add_required,
        on_changed=on_changed,
        get_structure_paths=get_structure_paths,
    )
    return show_autonomous_window(dlg, _active)


__all__ = [
    "KapitelPagesDialog",
    "open_kapitel_pages_dialog",
]
