"""Struktur-Snapshots: laden, vergleichen, Live-Vorschau im Buchbaum (P3 SSOT)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui_qt.markdown_preview import markdown_to_preview_html
from ui_qt.structure_snapshot import (
    collect_chapter_paths,
    compare_structure_paths,
    delete_structure_backup,
    format_snapshot_list_item_multiline,
    format_structure_diff_summary,
    is_chapter_required_in_book,
    list_structure_backups,
    load_snapshot_file,
    peek_book_file,
)
from ui_qt.widgets.help_bar import HelpBar

# Snapshots + Kapitel; Buchbaum rechts im Hauptfenster sichtbar (Live-Vorschau).
_DIALOG_SIZE = (900, 580)
_SPLIT_SIZES = [340, 520]


class LoadAction(Enum):
    REPLACE = auto()
    MERGE = auto()


@dataclass(frozen=True)
class StructureLoadResult:
    action: LoadAction
    snapshot_path: Path
    tree: list[Any]
    selected_paths: tuple[str, ...]
    persist_immediately: bool = False


def _chapter_row_prefix(*, in_tree: bool, required: bool, merge_mode: bool) -> str:
    parts: list[str] = []
    if required:
        parts.append("📌")
    if merge_mode:
        parts.append("✓" if in_tree else "➕")
    if not parts:
        return ""
    return " ".join(parts) + "  "


class ChapterPeekDialog(QDialog):
    """Modale Leservorschau: aktueller Dateiinhalt im Buch (nicht Snapshot)."""

    def __init__(
        self,
        parent: Optional[QWidget],
        book: Path,
        rel_path: str,
        *,
        chapter_title: str = "",
    ) -> None:
        super().__init__(parent)
        book = Path(book)
        rel = str(rel_path).replace("\\", "/")
        label = (chapter_title or Path(rel).name).strip() or rel
        self.setWindowTitle(f"Leservorschau — {label}")
        self.setModal(True)
        self.resize(820, 600)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend(
            layout,
            "Aktueller Dateiinhalt im Buch — nicht der Inhalt aus dem Snapshot.",
        )
        path_label = QLabel(rel)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(path_label)

        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        target = book / rel
        raw = peek_book_file(book, rel)
        if raw.startswith("("):
            view.setPlainText(raw)
        else:
            view.setHtml(
                markdown_to_preview_html(
                    raw,
                    book_root=book,
                    markdown_file=target,
                )
            )
        layout.addWidget(view, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class StructureLoadDialog(QDialog):
    """Snapshot wählen — Modus Ersetzen oder Ergänzen.

    Bei Live-Vorschau: Dialog links andocken, damit die Buchstruktur im
    Hauptfenster sichtbar bleibt. Leservorschau: modaler Dialog per Doppelklick.
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        book: Path,
        *,
        current_paths: Optional[set[str]] = None,
        current_paths_ordered: Optional[list[str]] = None,
        on_preview: Optional[Callable[[list[Any]], None]] = None,
        on_restore: Optional[Callable[[], None]] = None,
        live_preview_default: bool = False,
        show_save_and_apply: bool = False,
    ) -> None:
        super().__init__(parent)
        self._book = Path(book)
        self._on_preview = on_preview
        self._on_restore = on_restore
        self._show_save_and_apply = show_save_and_apply
        self._committed = False
        self._live_preview_active = False
        self._layout_ready = False
        ordered = current_paths_ordered or []
        self._current_paths_ordered = [
            str(p).replace("\\", "/") for p in ordered if p
        ]
        self._current_paths = {
            str(p).replace("\\", "/") for p in (current_paths or self._current_paths_ordered) if p
        }
        self._backups = list_structure_backups(self._book)
        self.result_data: Optional[StructureLoadResult] = None
        self._current_tree: list[Any] = []

        self.setWindowTitle("📂 Struktur-Snapshots")
        self.resize(*_DIALOG_SIZE)
        self.setModal(True)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend(
            layout,
            "Snapshot wählen. Ersetzen übernimmt die gesamte Struktur in den "
            "rechten Baum; Ergänzen fügt nur ausgewählte, noch fehlende Kapitel "
            "hinzu. Live-Vorschau zeigt Ersetzen sofort im Buchbaum "
            "(Dialog bleibt schmal links; Abbrechen stellt den Stand wieder her). "
            "<b>Doppelklick auf ein Kapitel öffnet die Leservorschau "
            "(aktueller Dateiinhalt im Buch) als eigenen Dialog.</b> "
            "<b>Snapshots löschen: Entf oder Rechtsklick → Löschen.</b> "
            "Ohne „Sofort speichern“ danach „Buchstruktur speichern“ für die _quarto.yml.",
            rich_text=True,
        )

        mode_row = QHBoxLayout()
        self._mode_replace = QRadioButton("↺ Gesamte Struktur ersetzen")
        self._mode_merge = QRadioButton("➕ Kapitel ergänzen")
        self._mode_replace.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_replace, 0)
        self._mode_group.addButton(self._mode_merge, 1)
        self._mode_group.idClicked.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_replace)
        mode_row.addWidget(self._mode_merge)
        mode_row.addStretch(1)
        self._new_only = QCheckBox("Nur neue Kapitel anzeigen (➕)")
        self._new_only.setChecked(True)
        self._new_only.setVisible(False)
        self._new_only.toggled.connect(self._apply_new_only_filter)
        mode_row.addWidget(self._new_only)
        layout.addLayout(mode_row)

        preview_row = QHBoxLayout()
        self._live_preview = QCheckBox("Live-Vorschau im Buchbaum (nur Ersetzen)")
        self._live_preview.setChecked(live_preview_default and on_preview is not None)
        self._live_preview.setVisible(on_preview is not None)
        self._live_preview.setEnabled(on_preview is not None)
        self._live_preview.setToolTip(
            "Zeigt den Snapshot probeweise im rechten Buchbaum. "
            "Dialog wird links gehalten, damit der Baum sichtbar bleibt."
        )
        self._live_preview.toggled.connect(self._on_live_preview_toggled)
        preview_row.addWidget(self._live_preview)
        preview_row.addStretch(1)
        layout.addLayout(preview_row)

        merge_legend = QLabel(
            "Legende Ergänzen: <b>➕</b> neu im Baum · <b>✓</b> bereits vorhanden · "
            "<b>📌</b> Pflichtseite (<code>required: true</code>)"
        )
        merge_legend.setTextFormat(Qt.TextFormat.RichText)
        merge_legend.setStyleSheet("color: #64748b; font-size: 12px;")
        merge_legend.setVisible(False)
        self._merge_legend = merge_legend
        layout.addWidget(merge_legend)

        self._diff_label = QLabel("Vergleich: Snapshot wählen …")
        self._diff_label.setWordWrap(True)
        self._diff_label.setTextFormat(Qt.TextFormat.RichText)
        self._diff_label.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px;"
        )
        self._diff_label.setVisible(False)
        layout.addWidget(self._diff_label)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Snapshots:"))
        self._snapshots = QListWidget()
        self._snapshots.setWordWrap(True)
        self._snapshots.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._snapshots.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._snapshots.customContextMenuRequested.connect(self._snapshots_context_menu)
        self._fill_snapshot_list()
        self._snapshots.currentRowChanged.connect(self._on_snapshot_row)
        left_layout.addWidget(self._snapshots, stretch=1)
        self._splitter.addWidget(left)

        mid = QWidget()
        mid_layout = QVBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        self._chapters_label = QLabel("Kapitel in diesem Snapshot:")
        mid_layout.addWidget(self._chapters_label)
        self._chapters = QListWidget()
        self._chapters.setWordWrap(True)
        self._chapters.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chapters.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._chapters.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._chapters.itemSelectionChanged.connect(self._update_merge_button)
        self._chapters.itemDoubleClicked.connect(self._on_chapter_double_clicked)
        mid_layout.addWidget(self._chapters, stretch=1)
        self._splitter.addWidget(mid)

        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes(list(_SPLIT_SIZES))
        layout.addWidget(self._splitter, stretch=1)

        buttons = QHBoxLayout()
        self._btn_replace = QPushButton("↺ Struktur übernehmen (ersetzen)")
        self._btn_merge = QPushButton("➕ Ausgewählte Kapitel ergänzen")
        self._btn_save_apply = QPushButton("✅ Übernehmen & 💾 Speichern")
        self._btn_save_apply.setToolTip(
            "Ersetzt die Struktur durch den Snapshot und schreibt sofort die _quarto.yml "
            "(frühere Time-Machine-Funktion)."
        )
        self._btn_save_apply.setVisible(show_save_and_apply)
        self._btn_save_apply.clicked.connect(self._save_and_apply)
        cancel_btn = QPushButton("Abbrechen")
        self._btn_replace.clicked.connect(self._replace)
        self._btn_merge.clicked.connect(self._merge)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._btn_replace)
        buttons.addWidget(self._btn_merge)
        buttons.addWidget(self._btn_save_apply)
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        if self._backups:
            self._snapshots.setCurrentRow(0)
        else:
            self._btn_replace.setEnabled(False)
            self._btn_merge.setEnabled(False)

        delete_shortcut = QAction(self)
        delete_shortcut.setShortcut(QKeySequence.StandardKey.Delete)
        delete_shortcut.triggered.connect(self._delete_selected_snapshots)
        self._snapshots.addAction(delete_shortcut)

        self._on_mode_changed(0)

    def _fill_snapshot_list(self) -> None:
        self._backups = list_structure_backups(self._book)
        self._snapshots.blockSignals(True)
        self._snapshots.clear()
        for path in self._backups:
            text, tooltip = format_snapshot_list_item_multiline(path)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(tooltip)
            self._snapshots.addItem(item)
        self._snapshots.blockSignals(False)

    def _selected_snapshot_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self._snapshots.selectedItems():
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw:
                paths.append(Path(str(raw)))
        return paths

    def _snapshots_context_menu(self, pos) -> None:
        item = self._snapshots.itemAt(pos)
        if item is not None and not item.isSelected():
            self._snapshots.setCurrentItem(item)
        if not self._snapshots.selectedItems():
            return
        menu = QMenu(self)
        count = len(self._snapshots.selectedItems())
        label = "Löschen…" if count == 1 else f"{count} Snapshots löschen…"
        action = menu.addAction(label)
        chosen = menu.exec(self._snapshots.mapToGlobal(pos))
        if chosen is action:
            self._delete_selected_snapshots()

    def _delete_selected_snapshots(self) -> None:
        paths = self._selected_snapshot_paths()
        if not paths:
            return
        if len(paths) == 1:
            from ui_qt.structure_snapshot import format_backup_label

            detail = format_backup_label(paths[0])
            question = (
                f"Diesen Struktur-Snapshot unwiderruflich löschen?\n\n{detail}\n"
                f"Datei: {paths[0].name}"
            )
        else:
            names = "\n".join(f"  · {p.name}" for p in paths[:12])
            if len(paths) > 12:
                names += f"\n  · … (+{len(paths) - 12} weitere)"
            question = (
                f"{len(paths)} Struktur-Snapshots unwiderruflich löschen?\n\n{names}"
            )
        if (
            QMessageBox.question(self, "Snapshot löschen", question)
            != QMessageBox.StandardButton.Yes
        ):
            return

        errors: list[str] = []
        deleted = 0
        for path in paths:
            try:
                delete_structure_backup(path)
                deleted += 1
            except (OSError, ValueError, FileNotFoundError) as exc:
                errors.append(f"{path.name}: {exc}")

        previous_row = self._snapshots.currentRow()
        self._fill_snapshot_list()
        if self._backups:
            row = min(max(0, previous_row), len(self._backups) - 1)
            self._snapshots.setCurrentRow(row)
            self._on_snapshot_row(row)
        else:
            self._chapters.clear()
            self._current_tree = []
            self._update_diff_summary()
            self._btn_replace.setEnabled(False)
            self._btn_merge.setEnabled(False)
            if self._live_preview_active:
                self._restore_live_preview()

        if errors:
            QMessageBox.warning(
                self,
                "Snapshot löschen",
                f"{deleted} gelöscht, {len(errors)} fehlgeschlagen:\n\n"
                + "\n".join(errors[:8]),
            )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._layout_ready = True
        if self._live_preview_wants_compact():
            self._dock_beside_book_tree()

    def _live_preview_wants_compact(self) -> bool:
        return (
            self._on_preview is not None
            and self._live_preview.isEnabled()
            and self._live_preview.isChecked()
            and not self._is_merge_mode()
        )

    def _dock_beside_book_tree(self) -> None:
        """Dialog links am Hauptfenster, Buchstruktur rechts bleibt frei."""
        host = self.parentWidget()
        if host is None:
            return
        win = host.window()
        if win is None:
            return
        frame = win.frameGeometry()
        x = frame.x() + 16
        y = frame.y() + max(64, (frame.height() - self.height()) // 10)
        screen = win.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            x = max(avail.x(), min(x, avail.x() + avail.width() - self.width()))
            y = max(avail.y(), min(y, avail.y() + avail.height() - self.height()))
        self.move(x, y)

    def _on_chapter_double_clicked(self, item: QListWidgetItem) -> None:
        """Doppelklick: modale Leservorschau des aktuellen Buch-Dateiinhalt."""
        path = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not path:
            return
        rel = str(path).replace("\\", "/")
        title = ""
        text = item.text() if item is not None else ""
        if text:
            title = text.split("\n", 1)[0].strip()
            for prefix in ("📌", "✓", "➕"):
                title = title.replace(prefix, "").strip()
        ChapterPeekDialog(
            self,
            self._book,
            rel,
            chapter_title=title,
        ).exec()

    def _is_merge_mode(self) -> bool:
        return self._mode_merge.isChecked()

    def _on_mode_changed(self, mode_id: int) -> None:
        merge = mode_id == 1
        if merge and self._live_preview_active:
            self._restore_live_preview()
            self._live_preview.setChecked(False)
        self._live_preview.setEnabled(not merge and self._on_preview is not None)
        self._btn_save_apply.setVisible(self._show_save_and_apply and not merge)
        self._new_only.setVisible(merge)
        self._merge_legend.setVisible(merge)
        self._btn_replace.setVisible(not merge)
        self._btn_merge.setVisible(merge)
        self._chapters_label.setText(
            "Kapitel auswählen (Mehrfachauswahl für Ergänzen):"
            if merge
            else "Kapitel in diesem Snapshot:"
        )
        self._chapters.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
            if merge
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        if self._current_tree:
            self._populate_chapters()
        self._apply_new_only_filter()
        self._update_merge_button()
        self._update_diff_summary()
        if self._layout_ready and self._live_preview_wants_compact():
            self._dock_beside_book_tree()

    def _current_diff(self):
        if not self._current_tree:
            return None
        return compare_structure_paths(self._current_tree, self._current_paths_ordered)

    def _update_diff_summary(self) -> None:
        diff = self._current_diff()
        if diff is None:
            self._diff_label.setVisible(False)
            return
        summary, tooltip = format_structure_diff_summary(
            diff,
            merge_mode=self._is_merge_mode(),
        )
        self._diff_label.setText(summary)
        self._diff_label.setToolTip(tooltip)
        self._diff_label.setVisible(True)
        if not self._is_merge_mode() and diff.only_in_current:
            self._diff_label.setStyleSheet(
                "background: #fff7ed; border: 1px solid #fdba74; border-radius: 6px; "
                "padding: 8px 10px; color: #9a3412;"
            )
        elif diff.order_changed:
            self._diff_label.setStyleSheet(
                "background: #eff6ff; border: 1px solid #93c5fd; border-radius: 6px; "
                "padding: 8px 10px;"
            )
        else:
            self._diff_label.setStyleSheet(
                "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; "
                "padding: 8px 10px;"
            )

    def _replace_confirmation_text(self) -> str:
        diff = self._current_diff()
        body = (
            "Die aktuelle Buchstruktur (rechts) wird vollständig durch "
            "diesen Snapshot ersetzt.\n\n"
        )
        if diff is not None:
            body += (
                f"Snapshot: {len(diff.snapshot_paths)} Kapitel · "
                f"aktueller Baum: {len(diff.current_paths)} Kapitel.\n"
            )
            if diff.only_in_current:
                body += (
                    f"\n⚠ {len(diff.only_in_current)} Pfad(e) nur im aktuellen Baum "
                    f"verschwinden aus der Struktur:\n"
                    + "\n".join(f"  · {p}" for p in diff.only_in_current[:8])
                )
                if len(diff.only_in_current) > 8:
                    body += f"\n  · … (+{len(diff.only_in_current) - 8} weitere)"
                body += "\n"
            if diff.order_changed:
                body += "\nDie Reihenfolge gemeinsamer Kapitel ändert sich.\n"
        body += (
            "\nNoch nicht gespeicherte Änderungen am Baum gehen verloren, "
            "bis du sie vorher per Undo zurücknimmst.\n\nFortfahren?"
        )
        return body

    def _replace_and_save_confirmation_text(self) -> str:
        diff = self._current_diff()
        body = (
            "Die aktuelle Buchstruktur wird durch diesen Snapshot ersetzt und "
            "sofort in die _quarto.yml geschrieben.\n\n"
        )
        if diff is not None:
            body += (
                f"Snapshot: {len(diff.snapshot_paths)} Kapitel · "
                f"aktueller Baum: {len(diff.current_paths)} Kapitel.\n"
            )
            if diff.only_in_current:
                body += (
                    f"\n⚠ {len(diff.only_in_current)} Pfad(e) nur im aktuellen Baum "
                    f"verschwinden aus der Struktur.\n"
                )
        body += "\nFortfahren?"
        return body

    def _snapshot_path(self) -> Optional[Path]:
        item = self._snapshots.currentItem()
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(raw)) if raw else None

    def _load_current_snapshot(self) -> bool:
        path = self._snapshot_path()
        if path is None:
            return False
        try:
            tree, _meta = load_snapshot_file(path)
        except (OSError, ValueError, TypeError, UnicodeDecodeError) as exc:
            QMessageBox.warning(self, "Struktur laden", f"Snapshot konnte nicht gelesen werden:\n{exc}")
            self._current_tree = []
            return False
        self._current_tree = tree if isinstance(tree, list) else []
        return True

    def _populate_chapters(self) -> None:
        self._chapters.clear()
        merge = self._is_merge_mode()
        for path, title in collect_chapter_paths(self._current_tree):
            norm = path.replace("\\", "/")
            in_tree = norm in self._current_paths
            required = is_chapter_required_in_book(self._book, norm)
            prefix = _chapter_row_prefix(
                in_tree=in_tree,
                required=required,
                merge_mode=merge,
            )
            item = QListWidgetItem(f"{prefix}{title}\n{norm}")
            item.setData(Qt.ItemDataRole.UserRole, norm)
            item.setToolTip(norm)
            if merge and in_tree:
                item.setForeground(Qt.GlobalColor.gray)
            self._chapters.addItem(item)
        self._apply_new_only_filter()

    def _on_snapshot_row(self, _row: int) -> None:
        self._chapters.clear()
        self._current_tree = []
        self._update_diff_summary()
        if not self._load_current_snapshot():
            return
        self._populate_chapters()
        self._update_diff_summary()
        self._maybe_live_preview()

    def _on_live_preview_toggled(self, checked: bool) -> None:
        if checked:
            self._maybe_live_preview()
            if self._layout_ready:
                self._dock_beside_book_tree()
        else:
            self._restore_live_preview()

    def _maybe_live_preview(self) -> None:
        if (
            self._on_preview is None
            or not self._live_preview.isChecked()
            or self._is_merge_mode()
            or not self._current_tree
        ):
            return
        self._on_preview(self._current_tree)
        self._live_preview_active = True

    def _restore_live_preview(self) -> None:
        if not self._live_preview_active or self._on_restore is None:
            self._live_preview_active = False
            return
        self._on_restore()
        self._live_preview_active = False

    def _finish_accept(self) -> None:
        self._committed = True
        self._live_preview_active = False
        self.accept()

    def reject(self) -> None:
        if not self._committed:
            self._restore_live_preview()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._committed:
            self._restore_live_preview()
        event.accept()

    def _apply_new_only_filter(self) -> None:
        if not self._is_merge_mode() or not self._new_only.isChecked():
            for row in range(self._chapters.count()):
                item = self._chapters.item(row)
                if item is not None:
                    item.setHidden(False)
            return
        for row in range(self._chapters.count()):
            item = self._chapters.item(row)
            if item is None:
                continue
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            is_new = path not in self._current_paths
            item.setHidden(not is_new)

    def _selected_paths(self) -> list[str]:
        paths: list[str] = []
        for item in self._chapters.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                paths.append(str(path).replace("\\", "/"))
        return paths

    def _update_merge_button(self) -> None:
        if not self._is_merge_mode():
            return
        selected = self._selected_paths()
        new_count = sum(1 for p in selected if p not in self._current_paths)
        if not selected:
            self._btn_merge.setText("➕ Ausgewählte Kapitel ergänzen")
            self._btn_merge.setEnabled(True)
        elif new_count == 0:
            self._btn_merge.setText("➕ Ausgewählte Kapitel ergänzen (alle schon im Baum)")
            self._btn_merge.setEnabled(False)
        else:
            skipped = len(selected) - new_count
            suffix = f" ({new_count} neu"
            if skipped:
                suffix += f", {skipped} übersprungen"
            suffix += ")"
            self._btn_merge.setText(f"➕ Ausgewählte Kapitel ergänzen{suffix}")

    def _prepare_for_commit(self) -> bool:
        """Live-Vorschau zurücksetzen, damit Undo/Snapshot den Dialog-Start erfasst."""
        if self._live_preview_active:
            self._restore_live_preview()
        return self._load_current_snapshot()

    def _replace(self) -> None:
        if not self._prepare_for_commit():
            return
        path = self._snapshot_path()
        if path is None:
            return
        if (
            QMessageBox.question(
                self,
                "Struktur ersetzen",
                self._replace_confirmation_text(),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.result_data = StructureLoadResult(
            action=LoadAction.REPLACE,
            snapshot_path=path,
            tree=self._current_tree,
            selected_paths=(),
        )
        self._finish_accept()

    def _save_and_apply(self) -> None:
        if not self._prepare_for_commit():
            return
        path = self._snapshot_path()
        if path is None:
            return
        if self._is_merge_mode():
            QMessageBox.information(
                self,
                "Struktur-Snapshots",
                "„Übernehmen & Speichern“ ist nur im Modus „Gesamte Struktur ersetzen“ verfügbar.",
            )
            return
        if (
            QMessageBox.question(
                self,
                "Struktur ersetzen & speichern",
                self._replace_and_save_confirmation_text(),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.result_data = StructureLoadResult(
            action=LoadAction.REPLACE,
            snapshot_path=path,
            tree=self._current_tree,
            selected_paths=(),
            persist_immediately=True,
        )
        self._finish_accept()

    def _merge(self) -> None:
        if not self._prepare_for_commit():
            return
        path = self._snapshot_path()
        if path is None:
            return
        selected = self._selected_paths()
        if not selected:
            QMessageBox.information(
                self,
                "Struktur ergänzen",
                "Bitte mindestens ein Kapitel in der Liste auswählen "
                "(Strg+Klick / Umschalt+Klick).",
            )
            return
        new_paths = [p for p in selected if p not in self._current_paths]
        if not new_paths:
            QMessageBox.information(
                self,
                "Struktur ergänzen",
                "Alle ausgewählten Kapitel sind bereits im rechten Baum.",
            )
            return
        self.result_data = StructureLoadResult(
            action=LoadAction.MERGE,
            snapshot_path=path,
            tree=self._current_tree,
            selected_paths=tuple(selected),
        )
        self._finish_accept()


def apply_structure_load_result(session, structure_panel, result: StructureLoadResult) -> None:
    """Wendet ein Dialog-Ergebnis auf die Session an (SSOT für Panel + Time Machine)."""
    if result.action is LoadAction.REPLACE:
        if not session.replace_structure_from_snapshot(result.tree):
            return
        structure_panel.reload_from_session()
        if result.persist_immediately:
            from ui_qt.structure_snapshot import (
                default_structure_snapshot_label,
                prompt_structure_snapshot_label,
            )

            label = prompt_structure_snapshot_label(
                structure_panel,
                default=default_structure_snapshot_label(book_name=session.book_path),
                book_name=session.book_path,
                title="Struktur speichern",
            )
            if label is None:
                QMessageBox.information(
                    structure_panel,
                    "Nicht gespeichert",
                    "Struktur ist im Baum übernommen, aber noch nicht in _quarto.yml "
                    "geschrieben — bitte „Buchstruktur speichern“.",
                )
                return
            if session.save(snapshot_label=label):
                QMessageBox.information(
                    structure_panel,
                    "Erfolg",
                    "Struktur wurde dauerhaft wiederhergestellt und gespeichert.",
                )
            else:
                QMessageBox.warning(
                    structure_panel,
                    "Nicht gespeichert",
                    "Die Struktur wurde im Baum übernommen, aber das Speichern "
                    "ist fehlgeschlagen. Bitte prüfe das Log.",
                )
            return
        session._log(
            "Struktur aus Snapshot ersetzt — „Buchstruktur speichern“ für _quarto.yml.",
            "success",
        )
    elif result.action is LoadAction.MERGE:
        added, skipped = session.merge_paths_from_snapshot(list(result.selected_paths))
        if added:
            structure_panel.reload_from_session()
        if added or skipped:
            parts = []
            if added:
                parts.append(f"{added} Kapitel ergänzt")
            if skipped:
                parts.append(f"{skipped} bereits im Baum (übersprungen)")
            session._log(
                f"Snapshot ergänzt: {', '.join(parts)} — „Buchstruktur speichern“ für _quarto.yml.",
                "success" if added else "info",
            )
        else:
            session._log("Keine neuen Kapitel ergänzt (alle schon im Baum).", "info")


def open_structure_load_dialog(
    parent: Optional[QWidget],
    book: Path,
    *,
    current_paths: Optional[set[str]] = None,
    current_paths_ordered: Optional[list[str]] = None,
    on_preview: Optional[Callable[[list[Any]], None]] = None,
    on_restore: Optional[Callable[[], None]] = None,
    live_preview_default: bool = False,
    show_save_and_apply: bool = False,
) -> Optional[StructureLoadResult]:
    if not list_structure_backups(book):
        QMessageBox.information(
            parent,
            "Struktur-Snapshots",
            "Keine Struktur-Snapshots gefunden.\n\n"
            "Speichere das Buch („Buchstruktur speichern“ → Zeitstempel-Snapshot) oder nutze "
            "Tools → Struktur-Snapshot speichern… mit einem sprechenden Namen.",
        )
        return None
    dlg = StructureLoadDialog(
        parent,
        book,
        current_paths=current_paths,
        current_paths_ordered=current_paths_ordered,
        on_preview=on_preview,
        on_restore=on_restore,
        live_preview_default=live_preview_default,
        show_save_and_apply=show_save_and_apply,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.result_data
