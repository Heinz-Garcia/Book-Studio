"""Qt-Dialog: GrammarGraph-Nutzinhalt aktualisieren (Body-Swap)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.gg_content_swap.bundle import (
    apply_gg_export_bundle,
    find_newest_publish_run,
    format_bundle_summary,
    resolve_export_root_from_path,
    select_main_payload,
)
from tools.gg_content_swap.export_sort import (
    ExportSortMode,
    parse_export_path_datetime,
    sort_export_paths,
)
from tools.gg_content_swap.source_guard import check_source_folder
from tools.gg_content_swap.swap import (
    body_diff_summary,
    enrich_plan_with_diffs,
    prepare_swap_scan,
    run_swap,
)
from tools.gg_content_swap.types import SwapPlanLine
from ui_qt.widgets.help_bar import HelpBar

_FG = QColor("#1a1d23")
_STATUS_LABEL = {
    "ok": "bereit",
    "missing": "keine Zuordnung",
    "ambiguous": "mehrdeutig",
    "unchanged": "schon aktuell",
    "error": "Fehler",
    "skipped_not_gg": "kein GG",
}

_STATUS_BG = {
    "ok": QColor("#d4edda"),
    "missing": QColor("#f8d7da"),
    "ambiguous": QColor("#fff3cd"),
    "unchanged": QColor("#e2e3e5"),
    "error": QColor("#f5c6cb"),
}

_READABLE_LIST_STYLE = """
QListWidget, QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #eef2f6;
    color: #1a1d23;
    border: 1px solid #c5cad3;
}
QListWidget::item, QTableWidget::item {
    color: #1a1d23;
}
QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #d6e6f5;
    color: #1a1d23;
}
"""


def _default_source_dir(studio: Any) -> Path:
    """Startordner für den Dateidialog — inbox/ oder neuester Publish_*-Lauf."""
    book = getattr(studio, "current_book", None)
    if book:
        parent = Path(book).resolve().parent
        if parent.is_dir():
            return parent
    try:
        import app_config as _app_config
        from tools.production_paths.config import resolve_grammargraph_inbox_roots
        from ui_qt.book_workspace import repo_root

        cfg = _app_config.read_config(repo_root() / "app_config.json")
        for entry in resolve_grammargraph_inbox_roots(cfg, repo_root()):
            if not entry.is_dir():
                continue
            if check_source_folder(entry).is_publish_hub:
                run = find_newest_publish_run(entry)
                if run and run.is_dir():
                    return run
                continue
            return entry
        for entry in cfg.get("content_root_path") or []:
            p = Path(str(entry))
            if not p.is_absolute():
                p = (repo_root() / p).resolve()
            if p.is_dir():
                return p
    except (OSError, TypeError, ValueError, ImportError):
        pass
    return Path.home()


def _initial_source_field(studio: Any) -> str:
    """Leer lassen, wenn der Default eine Sammelmappe wäre — erzwingt Dateiwahl."""
    start = _default_source_dir(studio)
    if check_source_folder(start).is_publish_hub:
        return ""
    return str(start)


class GgContentSwapQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self._studio = studio
        self._plan: list[SwapPlanLine] = []
        self._export_files: list[str] = []
        self._export_combos: list[Optional[QComboBox]] = []
        # Manuelle/übernommene Zuordnung behalten (sonst gewinnt wieder Basename-Match).
        self._pinned_sources: dict[str, str] = {}
        self.setObjectName("ggContentSwapDialog")
        self.setWindowTitle("GrammarGraph-Inhalt aktualisieren")
        self.resize(1100, 720)
        self.setMinimumSize(860, 560)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "gg_content_swap")

        steps = QLabel(
            "<b>Automatisch:</b> Einen <b>Publish_*-Export-Ordner</b> wählen "
            "(nicht die Sammelmappe). Book Studio übernimmt dann allein: "
            "Haupt-Payload, Anzeigename, Erstellungsprotokoll, publish_meta, "
            "Provenance und Bilder. "
            "Optional: einzelne .md wählen, wenn mehrere Nutzdateien liegen."
        )
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(steps)

        pick_row = QHBoxLayout()
        self._pick_btn = QPushButton("Export übernehmen…")
        self._pick_btn.setDefault(True)
        self._pick_btn.setMinimumHeight(40)
        self._pick_btn.setStyleSheet(
            "QPushButton { background-color: #2f5d9f; color: white; font-weight: 600; "
            "padding: 8px 16px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #264a80; }"
        )
        self._pick_btn.setToolTip(
            "Publish_*-Ordner wählen → Payload + Metadaten automatisch ins Buch."
        )
        self._pick_btn.clicked.connect(self._import_export_bundle)
        pick_row.addWidget(self._pick_btn)
        pick_md = QPushButton("Nur .md wählen…")
        pick_md.setToolTip("Falls mehrere Nutzdateien: konkrete Payload-.md wählen")
        pick_md.clicked.connect(self._pick_source_file)
        pick_row.addWidget(pick_md)
        self._picked_label = QLabel("Noch kein Export gewählt.")
        self._picked_label.setWordWrap(True)
        self._picked_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pick_row.addWidget(self._picked_label, stretch=1)
        layout.addLayout(pick_row)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Export-Ordner:"))
        self._source = QLineEdit(_initial_source_field(studio))
        self._source.setPlaceholderText("Wird gesetzt, sobald Sie eine Quell-.md wählen")
        self._source.setClearButtonEnabled(True)
        self._source.setToolTip(
            "Nur ein einzelner Publish_*-Lauf oder dessen Ordner — "
            "nie die Sammelmappe „Publish“ mit vielen Exporten."
        )
        path_row.addWidget(self._source, stretch=1)
        browse = QPushButton("Ordner…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        scan = QPushButton("Zuordnung prüfen")
        scan.clicked.connect(self._scan)
        path_row.addWidget(scan)
        layout.addLayout(path_row)

        self._hub_banner = QLabel("")
        self._hub_banner.setWordWrap(True)
        self._hub_banner.setVisible(False)
        self._hub_banner.setStyleSheet(
            "QLabel { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; "
            "border-radius: 4px; padding: 8px 10px; }"
        )
        layout.addWidget(self._hub_banner)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._summary)

        splitter = QSplitter(Qt.Orientation.Vertical)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(
            QLabel("Zuordnung: aktuelle Buchdatei (Ziel) ← neuer Payload (Quelle)")
        )

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("ggSwapTable")
        self.table.setStyleSheet(_READABLE_LIST_STYLE)
        self.table.setHorizontalHeaderLabels(
            ["Aktuelle Buchdatei (Ziel)", "Neuer Payload (Quelle)", "Status", "Hinweis"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(100)
        self.table.setColumnWidth(2, 130)
        self.table.itemSelectionChanged.connect(self._show_diff)
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.table.setToolTip("Doppelklick auf Buchdatei → Markdown-Editor öffnen")
        top_layout.addWidget(self.table)

        export_header = QHBoxLayout()
        export_header.addWidget(
            QLabel("Im Export gefunden — Doppelklick öffnet Markdown:")
        )
        export_header.addStretch(1)
        export_header.addWidget(QLabel("Sortierung:"))
        self._export_sort = QComboBox()
        self._export_sort.addItem("Neueste zuerst", "date_desc")
        self._export_sort.addItem("Älteste zuerst", "date_asc")
        self._export_sort.addItem("Name A–Z", "name_asc")
        self._export_sort.addItem("Name Z–A", "name_desc")
        self._export_sort.setToolTip(
            "Datum aus Publish-Ordnernamen (z. B. …_25.07.2026_22.09), sonst Name."
        )
        self._export_sort.currentIndexChanged.connect(self._refresh_unmatched_list)
        export_header.addWidget(self._export_sort)
        top_layout.addLayout(export_header)
        self._export_list = QListWidget()
        self._export_list.setObjectName("ggSwapExportList")
        self._export_list.setStyleSheet(_READABLE_LIST_STYLE)
        self._export_list.setAlternatingRowColors(True)
        self._export_list.setMinimumHeight(140)
        self._export_list.setMaximumHeight(220)
        self._export_list.setToolTip(
            "Doppelklick: Export-Markdown öffnen.\n"
            "Schaltfläche „Zuordnen“: der Buchzeile zuweisen."
        )
        self._export_list.itemDoubleClicked.connect(self._on_export_double_clicked)
        top_layout.addWidget(self._export_list)

        export_actions = QHBoxLayout()
        assign_btn = QPushButton("Auswahl der Buchzeile zuordnen")
        assign_btn.setToolTip(
            "Gewählte Export-Datei der Buchzeile zuordnen (bei einer Buchdatei automatisch)."
        )
        assign_btn.clicked.connect(self._assign_selected_export)
        export_actions.addWidget(assign_btn)
        title_btn = QPushButton("Anzeigename an Payload anpassen")
        title_btn.setToolTip(
            "Frontmatter-Titel der aktuellen Buchdatei auf den Payload-Namen setzen "
            "(sichtbar in der Buchstruktur rechts)."
        )
        title_btn.clicked.connect(self._sync_titles_only)
        export_actions.addWidget(title_btn)
        open_book_btn = QPushButton("Buchdatei öffnen…")
        open_book_btn.setToolTip("Übernommene Buch-Markdown-Datei im Editor öffnen")
        open_book_btn.clicked.connect(self._open_selected_book_file)
        export_actions.addWidget(open_book_btn)
        export_actions.addStretch(1)
        top_layout.addLayout(export_actions)
        splitter.addWidget(top)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(QLabel("Vorschau / Diff:"))
        self._diff = QTextEdit()
        self._diff.setReadOnly(True)
        self._diff.setPlaceholderText("Zeile in der Tabelle wählen…")
        bottom_layout.addWidget(self._diff)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        btns = QHBoxLayout()
        apply_btn = QPushButton("Übernehmen (wie gewählt)")
        apply_btn.setMinimumHeight(34)
        apply_btn.setStyleSheet(
            "QPushButton { background-color: #1f7a3f; color: white; font-weight: 600; "
            "padding: 8px 16px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #176433; }"
        )
        apply_btn.setToolTip(
            "Führt die komplette Export-Übernahme für den eingestellten Ordner aus "
            "(Payload + Meta + Protokoll + Provenance)."
        )
        apply_btn.clicked.connect(self._apply_bundle_from_field)
        btns.addWidget(apply_btn)
        open_btn = QPushButton("Buchdatei öffnen…")
        open_btn.clicked.connect(self._open_selected_book_file)
        btns.addWidget(open_btn)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        btns.addStretch(1)
        layout.addLayout(btns)

        self._scan(quiet_if_empty=True)

    def _book_path(self) -> Optional[Path]:
        book = getattr(self._studio, "current_book", None)
        if not book:
            return None
        return Path(book)

    def _show_hub_banner(self, reason: str) -> None:
        self._hub_banner.setText(f"⛔ {reason}")
        self._hub_banner.setVisible(True)

    def _clear_hub_banner(self) -> None:
        self._hub_banner.clear()
        self._hub_banner.setVisible(False)

    def _clear_plan_ui(self, message: str) -> None:
        self._plan = []
        self._export_files = []
        self._export_combos = []
        self.table.setRowCount(0)
        self._export_list.clear()
        self._summary.setText(message)
        self._diff.setPlainText(message)

    def _reject_publish_hub(self, reason: str, *, offer_file_pick: bool = True) -> None:
        self._show_hub_banner(reason)
        self._clear_plan_ui("Publish-Sammelmappe abgelehnt — bitte konkrete Quell-.md wählen.")
        self._picked_label.setText("Bitte „1. Quell-Markdown wählen…“ nutzen.")
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(f"GG-Swap: Publish-Sammelmappe abgelehnt — {reason}", "warning")
        if offer_file_pick:
            reply = QMessageBox.warning(
                self,
                "Publish-Sammelmappe — nicht erlaubt",
                reason + "\n\nJetzt eine konkrete Markdown-Datei wählen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._pick_source_file()

    def _resolve_export_root(self, md_path: Path) -> tuple[Path, str]:
        """Nächsten Publish_*-Vorfahren als Export-Wurzel nutzen."""
        resolved = md_path.resolve()
        for parent in (resolved.parent, *resolved.parents):
            if parent.name.lower().startswith("publish_"):
                try:
                    return parent, resolved.relative_to(parent).as_posix()
                except ValueError:
                    break
        return resolved.parent, resolved.name

    def _run_bundle(
        self,
        source_root: Path,
        *,
        payload_rel: Optional[str] = None,
    ) -> None:
        book = self._book_path()
        if book is None:
            QMessageBox.information(self, "GG-Swap", "Bitte zuerst ein Buch laden.")
            return
        hub = check_source_folder(source_root)
        if hub.is_publish_hub:
            self._reject_publish_hub(hub.reason)
            return

        payload = payload_rel or select_main_payload(source_root)
        preview = (
            f"Export-Ordner:\n{source_root}\n\n"
            f"Automatisch erkannt:\n"
            f"• Payload: {payload or '—'}\n"
            f"• + Anzeigename (title)\n"
            f"• + Erstellungsprotokoll.md\n"
            f"• + publish_meta.json\n"
            f"• + Provenance (grammargraph_export.json)\n"
            f"• + images/img (falls vorhanden)\n\n"
            "Jetzt übernehmen?"
        )
        if QMessageBox.question(self, "Export automatisch übernehmen?", preview) != (
            QMessageBox.StandardButton.Yes
        ):
            return

        result = apply_gg_export_bundle(
            book,
            source_root,
            payload_rel=payload,
            dry_run=False,
            sync_title=True,
        )
        self._source.setText(str(source_root))
        if result.payload_rel and result.book_gg_rel:
            self._pinned_sources[result.book_gg_rel] = result.payload_rel
        self._picked_label.setText(
            f"Zuletzt: {result.payload_rel or '—'} aus {Path(result.source_root).name}"
        )

        log = getattr(self._studio, "log", None)
        summary = format_bundle_summary(result)
        if callable(log):
            log(summary.replace("\n", " | "), "success" if result.ok else "error")

        if result.ok:
            QMessageBox.information(self, "✅ Export übernommen", summary)
            self._refresh_studio_structure()
        else:
            QMessageBox.warning(self, "Übernahme mit Fehlern", summary)

        self._clear_hub_banner()
        self._scan()

    def _import_export_bundle(self) -> None:
        """Hauptaktion: Publish_*-Ordner wählen und alles automatisch übernehmen."""
        book = self._book_path()
        if book is None:
            QMessageBox.information(self, "GG-Swap", "Bitte zuerst ein Buch laden.")
            return
        start = self._source.text().strip() or str(_default_source_dir(self._studio))
        start_path = Path(start)
        # Wenn Start die Sammelmappe ist: neuesten passenden Lauf vorschlagen
        if start_path.is_dir() and check_source_folder(start_path).is_publish_hub:
            newest = find_newest_publish_run(start_path, name_hint=book.name)
            if newest is not None:
                use = QMessageBox.question(
                    self,
                    "Neuester Export?",
                    f"Sammelmappe erkannt.\n\n"
                    f"Neuester passender Lauf:\n{newest.name}\n\n"
                    f"Diesen Ordner übernehmen?\n"
                    f"(Nein = anderen Publish_*-Ordner manuell wählen)",
                )
                if use == QMessageBox.StandardButton.Yes:
                    self._run_bundle(newest)
                    return
                start = str(newest.parent)

        chosen = QFileDialog.getExistingDirectory(
            self,
            "Publish_*-Export-Ordner wählen (ein Lauf, nicht die Sammelmappe)",
            start,
        )
        if not chosen:
            return
        chosen_path = Path(chosen)
        hub = check_source_folder(chosen_path)
        if hub.is_publish_hub:
            newest = find_newest_publish_run(chosen_path, name_hint=book.name)
            if newest is not None:
                use = QMessageBox.question(
                    self,
                    "Sammelmappe — automatischer Vorschlag",
                    hub.reason
                    + f"\n\nVorschlag (neuester passender Lauf):\n{newest}\n\nÜbernehmen?",
                )
                if use == QMessageBox.StandardButton.Yes:
                    self._run_bundle(newest)
                return
            self._reject_publish_hub(hub.reason, offer_file_pick=False)
            return
        self._run_bundle(chosen_path)

    def _apply_bundle_from_field(self) -> None:
        raw = self._source.text().strip()
        if not raw:
            self._import_export_bundle()
            return
        source = Path(raw)
        if not source.is_dir():
            QMessageBox.warning(self, "GG-Swap", f"Ordner nicht gefunden:\n{source}")
            return
        # Falls in der Tabelle schon eine Payload gewählt ist, diese nutzen
        payload = None
        plan = self._effective_plan()
        for line in plan:
            if line.source_rel:
                payload = line.source_rel
                break
        self._run_bundle(source, payload_rel=payload)

    def _pick_source_file(self) -> None:
        """Einzelne Payload-.md wählen und sofort den Bundle-Lauf starten."""
        book = self._book_path()
        if book is None:
            QMessageBox.information(self, "GG-Swap", "Bitte zuerst ein Buch laden.")
            return
        start = self._source.text().strip() or str(_default_source_dir(self._studio))
        chosen = QFileDialog.getOpenFileName(
            self,
            "Payload-.md aus einem Publish_*-Export",
            start,
            "Markdown (*.md);;Alle Dateien (*.*)",
        )[0]
        if not chosen:
            return
        md_path = Path(chosen)
        if not md_path.is_file():
            QMessageBox.warning(self, "GG-Swap", f"Datei nicht gefunden:\n{md_path}")
            return
        source_root, source_rel = resolve_export_root_from_path(md_path)
        hub = check_source_folder(source_root)
        if hub.is_publish_hub:
            self._reject_publish_hub(hub.reason or "Ungültige Export-Wurzel.", offer_file_pick=False)
            return
        self._run_bundle(source_root, payload_rel=source_rel)

    def _browse(self) -> None:
        start = self._source.text().strip() or str(_default_source_dir(self._studio))
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Einzelnen Publish_*-Export-Ordner wählen (nicht die Sammelmappe)",
            start,
        )
        if not chosen:
            return
        hub = check_source_folder(chosen)
        if hub.is_publish_hub:
            self._source.setText(chosen)
            self._reject_publish_hub(hub.reason)
            return
        self._clear_hub_banner()
        self._source.setText(chosen)
        self._picked_label.setText(
            "Ordner ok — empfohlen bleibt „1. Quell-Markdown wählen…“ für die genaue Datei."
        )
        self._scan()

    def _open_markdown(self, path: Path, *, title: str) -> None:
        if not path.is_file():
            QMessageBox.warning(self, "GG-Swap", f"Datei nicht gefunden:\n{path}")
            return
        from ui_qt.dialogs.text_dialogs import TextEditorDialog

        book = self._book_path()

        def _after_save() -> None:
            # Nach Edit der Buchdatei Diff/Status neu berechnen
            if book is None:
                return
            try:
                path.resolve().relative_to(Path(book).resolve())
            except ValueError:
                return
            self._scan()

        TextEditorDialog(
            self,
            path,
            title=title,
            book_path=book,
            on_save=_after_save if book else None,
        ).exec()

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._plan):
            return
        book = self._book_path()
        if book is None:
            return
        self._open_markdown(book / self._plan[row].book_rel, title="Buchdatei")

    def _open_selected_book_file(self) -> None:
        row = self._target_book_row()
        if row is None:
            QMessageBox.information(self, "GG-Swap", "Keine Buchdatei in der Tabelle.")
            return
        book = self._book_path()
        if book is None:
            return
        self._open_markdown(book / self._plan[row].book_rel, title="Buchdatei")

    def _set_cell(self, row: int, col: int, text: str, *, tip: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QBrush(_FG))
        item.setToolTip(tip or text)
        self.table.setItem(row, col, item)
        return item

    def _on_manual_export(self, row: int, combo: QComboBox) -> None:
        data = combo.currentData()
        self._assign_source(row, str(data) if data else None, origin="combo")

    def _on_export_double_clicked(self, item: QListWidgetItem) -> None:
        source_rel = item.data(Qt.ItemDataRole.UserRole)
        if not source_rel:
            return
        source_root = Path(self._source.text().strip())
        self._open_markdown(source_root / str(source_rel), title="Export-Markdown")

    def _assign_selected_export(self) -> None:
        item = self._export_list.currentItem()
        if item is None:
            QMessageBox.information(self, "GG-Swap", "Bitte zuerst einen Export-Eintrag wählen.")
            return
        source_rel = item.data(Qt.ItemDataRole.UserRole)
        if not source_rel:
            return
        row = self._target_book_row()
        if row is None:
            QMessageBox.information(
                self,
                "GG-Swap",
                "Bitte zuerst eine Buchzeile in der Tabelle oben auswählen.",
            )
            return
        self._assign_source(row, str(source_rel), origin="button")
        self.table.selectRow(row)
        self._show_diff()

    def _target_book_row(self) -> Optional[int]:
        if not self._plan:
            return None
        if len(self._plan) == 1:
            return 0
        rows = self.table.selectionModel().selectedRows()
        if rows:
            idx = rows[0].row()
            if 0 <= idx < len(self._plan):
                return idx
        return None

    def _apply_pinned_sources(self) -> None:
        if not self._pinned_sources or not self._plan:
            return
        source_root = Path(self._source.text().strip())
        for i, line in enumerate(self._plan):
            pinned = self._pinned_sources.get(line.book_rel)
            if not pinned:
                continue
            if not (source_root / pinned).is_file():
                continue
            self._assign_source(i, pinned, origin="pin")

    def _assign_source(
        self,
        row: int,
        source_rel: Optional[str],
        *,
        origin: str,
    ) -> None:
        if row < 0 or row >= len(self._plan):
            return
        line = self._plan[row]
        book = self._book_path()
        source_root = Path(self._source.text().strip())
        if not source_rel:
            self._pinned_sources.pop(line.book_rel, None)
            self._plan[row] = SwapPlanLine(
                book_rel=line.book_rel,
                source_rel=None,
                status="missing",
                title=line.title,
                message="Manuell: keine Export-Datei gewählt",
            )
        elif book is None or not source_root.is_dir():
            self._pinned_sources[line.book_rel] = source_rel
            self._plan[row] = SwapPlanLine(
                book_rel=line.book_rel,
                source_rel=source_rel,
                status="ok",
                title=line.title,
                message="Manuelle Zuordnung",
            )
        else:
            if origin != "pin":
                self._pinned_sources[line.book_rel] = source_rel
            draft = SwapPlanLine(
                book_rel=line.book_rel,
                source_rel=source_rel,
                status="ok",
                title=line.title,
                message="Übernommene Zuordnung" if origin == "pin" else "Manuelle Zuordnung",
            )
            enriched = enrich_plan_with_diffs([draft], book, source_root)
            self._plan[row] = enriched[0] if enriched else draft

        # Bei pin: Combos existieren schon — sync; bei scan-Neubau kommt sync danach
        if origin != "pin" or self._export_combos:
            self._sync_export_combo(row)
            self._refresh_status_cell(row)
            self._refresh_summary()
            self._refresh_unmatched_list()
            if self.table.currentRow() == row:
                self._show_diff()

        log = getattr(self._studio, "log", None)
        if callable(log) and source_rel and origin != "pin":
            log(
                f"GG-Swap: {line.book_rel} ← {source_rel} "
                f"({_STATUS_LABEL.get(self._plan[row].status, self._plan[row].status)})",
                "info",
            )

    def _sync_export_combo(self, row: int) -> None:
        if row < 0 or row >= len(self._export_combos):
            return
        combo = self._export_combos[row]
        if combo is None:
            return
        line = self._plan[row]
        combo.blockSignals(True)
        try:
            if line.source_rel:
                idx = combo.findData(line.source_rel)
                if idx < 0:
                    combo.addItem(line.source_rel, line.source_rel)
                    idx = combo.findData(line.source_rel)
                combo.setCurrentIndex(max(0, idx))
            else:
                combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(False)

    def _make_export_combo(self, row: int, selected: Optional[str]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(False)
        combo.setMaxVisibleItems(20)
        combo.addItem("— manuell wählen —", None)
        # Aktuelle Zuordnung + unzugeordnete + alle (damit Wechsel möglich)
        seen: set[str] = set()
        ordered: list[str] = []
        if selected:
            ordered.append(selected)
            seen.add(selected)
        for export_rel in sort_export_paths(list(self._export_files), self._export_sort_mode()):
            if export_rel not in seen:
                ordered.append(export_rel)
                seen.add(export_rel)
        for export_rel in ordered:
            combo.addItem(export_rel, export_rel)
        if selected:
            idx = combo.findData(selected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.setToolTip("Export-Datei wählen oder unten per Doppelklick zuordnen")
        combo.currentIndexChanged.connect(
            lambda _idx, r=row, c=combo: self._on_manual_export(r, c)
        )
        return combo

    def _refresh_status_cell(self, row: int) -> None:
        if row < 0 or row >= len(self._plan):
            return
        line = self._plan[row]
        label = _STATUS_LABEL.get(line.status, line.status)
        item = self._set_cell(row, 2, label, tip=line.status)
        bg = _STATUS_BG.get(line.status)
        if bg is not None:
            item.setBackground(bg)
        self._set_cell(row, 3, line.message)

    def _effective_plan(self) -> list[SwapPlanLine]:
        return list(self._plan)

    def _refresh_summary(self) -> None:
        plan = self._effective_plan()
        counts: dict[str, int] = {}
        for line in plan:
            counts[line.status] = counts.get(line.status, 0) + 1
        parts = [
            f"Export: {len(self._export_files)} Markdown-Datei(en)",
            f"Buch-GG: {len(plan)}",
        ]
        for key in ("ok", "missing", "ambiguous", "unchanged", "error"):
            if counts.get(key):
                parts.append(f"{_STATUS_LABEL.get(key, key)}: {counts[key]}")
        self._summary.setText(" · ".join(parts))

    def _add_export_list_item(
        self,
        text: str,
        *,
        tip: str = "",
        source_rel: Optional[str] = None,
    ) -> None:
        item = QListWidgetItem(text)
        item.setForeground(QBrush(_FG))
        item.setToolTip(tip or text)
        if source_rel:
            item.setData(Qt.ItemDataRole.UserRole, source_rel)
        self._export_list.addItem(item)

    def _export_sort_mode(self) -> ExportSortMode:
        data = self._export_sort.currentData()
        if data in ("date_desc", "date_asc", "name_asc", "name_desc"):
            return data  # type: ignore[return-value]
        return "date_desc"

    def _refresh_unmatched_list(self) -> None:
        used = {line.source_rel for line in self._effective_plan() if line.source_rel}
        self._export_list.clear()
        unmatched = [rel for rel in self._export_files if rel not in used]
        if not self._export_files:
            self._add_export_list_item("(keine .md im Export-Ordner)")
            return
        if not unmatched:
            self._add_export_list_item("(alle Export-Dateien sind zugeordnet)")
            return
        for rel in sort_export_paths(unmatched, self._export_sort_mode()):
            dt = parse_export_path_datetime(rel)
            if dt:
                tip = (
                    f"{rel}\nDatum: {dt.strftime('%d.%m.%Y %H:%M')}\n"
                    "Doppelklick = öffnen · Button „Zuordnen“ = Buchzeile"
                )
            else:
                tip = f"{rel}\nDoppelklick = öffnen · Button „Zuordnen“ = Buchzeile"
            self._add_export_list_item(rel, tip=tip, source_rel=rel)

    def _scan(self, *, quiet_if_empty: bool = False) -> None:
        book = self._book_path()
        if book is None:
            if not quiet_if_empty:
                QMessageBox.information(self, "GG-Swap", "Bitte zuerst ein Buch laden.")
            return
        raw = self._source.text().strip()
        if not raw:
            self._clear_hub_banner()
            self._clear_plan_ui(
                "Noch kein Export gewählt. Pflichtschritt: „1. Quell-Markdown wählen…“."
            )
            return
        source = Path(raw)
        if not source.is_dir():
            if quiet_if_empty:
                self._clear_plan_ui(f"Ordner nicht gefunden:\n{source}")
                return
            QMessageBox.warning(self, "GG-Swap", f"Ordner nicht gefunden:\n{source}")
            return

        hub = check_source_folder(source)
        if hub.is_publish_hub:
            self._reject_publish_hub(hub.reason, offer_file_pick=not quiet_if_empty)
            return

        self._clear_hub_banner()
        try:
            scan = prepare_swap_scan(book, source)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "GG-Swap", str(exc))
            return

        self._plan = list(scan.plan)
        self._export_files = list(scan.export_files)
        self._export_combos = []
        self.table.setRowCount(len(self._plan))

        for i, line in enumerate(self._plan):
            book_tip = line.book_rel
            if line.title:
                book_tip = f"{line.book_rel}\nTitel: {line.title}"
            self._set_cell(i, 0, line.book_rel, tip=book_tip)

            if self._export_files:
                combo = self._make_export_combo(i, line.source_rel)
                self.table.setCellWidget(i, 1, combo)
                self._export_combos.append(combo)
            else:
                self.table.setCellWidget(i, 1, None)
                self._set_cell(i, 1, line.source_rel or "—", tip=line.source_rel or "")
                self._export_combos.append(None)

            self._refresh_status_cell(i)

        self._apply_pinned_sources()
        self._refresh_summary()
        self._refresh_unmatched_list()

        if not self._plan and not self._export_files:
            self._diff.setPlainText(
                "Weder im Buch noch im Export wurden passende Markdown-Dateien gefunden.\n"
                "Prüfe den Export-Ordner und ob das richtige Buch aktiv ist."
            )
        elif not self._plan:
            self._diff.setPlainText(
                f"Im Export liegen {len(self._export_files)} Markdown-Datei(en), "
                "aber im Buch keine GG-Nutzinhalt-Kandidaten.\n"
                "Required-/Skeleton-Seiten und Root-index.md werden ausgelassen."
            )
        elif not self._export_files:
            self._diff.setPlainText(
                "Im gewählten Ordner wurden keine .md-Dateien gefunden.\n"
                "Bitte „1. Quell-Markdown wählen…“ nutzen."
            )
        else:
            self._diff.clear()

        log = getattr(self._studio, "log", None)
        if callable(log):
            log(
                f"GG-Swap: {len(self._plan)} Buch-Datei(en), "
                f"{len(self._export_files)} Export-Datei(en) geprüft.",
                "info",
            )

    def _show_diff(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        plan = self._effective_plan()
        if idx < 0 or idx >= len(plan):
            return
        line = plan[idx]
        book = self._book_path()
        source = Path(self._source.text().strip())
        parts = [
            f"Buch:   {line.book_rel}",
            f"Export: {line.source_rel or '—'}",
            f"Status: {_STATUS_LABEL.get(line.status, line.status)} — {line.message}",
        ]
        if line.title:
            parts.append(f"Titel:  {line.title}")
        parts.append("")
        if line.status in ("ok", "unchanged") and line.source_rel and book and source.is_dir():
            try:
                book_text = (book / line.book_rel).read_text(encoding="utf-8")
                source_text = (source / line.source_rel).read_text(encoding="utf-8")
                parts.append(body_diff_summary(book_text, source_text, limit=1200))
            except OSError as exc:
                parts.append(str(exc))
        elif line.diff_summary:
            parts.append(line.diff_summary)
        self._diff.setPlainText("\n".join(parts))

    def _refresh_studio_structure(self) -> None:
        """Buchstruktur neu laden, damit geänderte Titel sichtbar werden."""
        studio = self._studio
        root = getattr(studio, "root", None)
        session = None
        if root is not None:
            session = getattr(root, "_session", None)
        if session is None and hasattr(studio, "_session"):
            session = getattr(studio, "_session", None)
        if session is None:
            # Plugin-Studio: parent window
            parent = self.parent()
            while parent is not None and session is None:
                session = getattr(parent, "_session", None)
                parent = parent.parent() if hasattr(parent, "parent") else None
        if session is not None and hasattr(session, "load"):
            try:
                session.load()
            except (OSError, TypeError, ValueError, RuntimeError):
                pass
            structure = None
            win = self.window()
            if win is not None:
                structure = getattr(win, "structure", None)
            if structure is not None and hasattr(structure, "reload_from_session"):
                structure.reload_from_session()

    def _sync_titles_only(self) -> None:
        book = self._book_path()
        raw = self._source.text().strip()
        if book is None or not raw:
            QMessageBox.information(
                self,
                "GG-Swap",
                "Bitte zuerst Quell-Markdown wählen und Zuordnung prüfen.",
            )
            return
        source = Path(raw)
        if not source.is_dir():
            return
        plan = [line for line in self._effective_plan() if line.source_rel]
        if not plan:
            QMessageBox.information(self, "GG-Swap", "Keine zugeordnete Payload-Datei.")
            return
        _plan, result = run_swap(
            book,
            source,
            dry_run=False,
            plan=plan,
            sync_title=True,
            allow_title_only=True,
        )
        self._plan = _plan
        if result.errors:
            QMessageBox.warning(self, "GG-Swap", "\n".join(result.errors[:5]))
            return
        if not result.titles_updated:
            QMessageBox.information(
                self,
                "GG-Swap",
                "Anzeigename war bereits am Payload ausgerichtet.",
            )
            self._scan()
            return
        lines = "\n".join(f"• {t}" for t in result.titles_updated)
        QMessageBox.information(
            self,
            "✅ Anzeigename angepasst",
            "Der Name in der Buchstruktur wurde aktualisiert:\n\n"
            f"{lines}\n\n"
            "Die Datei auf der Festplatte heißt weiterhin wie zuvor "
            "(nur Frontmatter-Titel / Anzeige).",
        )
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(f"GG-Swap Titel angepasst: {'; '.join(result.titles_updated)}", "success")
        self._refresh_studio_structure()
        self._scan()

    def _apply(self) -> None:
        book = self._book_path()
        if book is None:
            return
        raw = self._source.text().strip()
        if not raw:
            QMessageBox.information(
                self,
                "GG-Swap",
                "Keine Quelle gewählt.\nBitte zuerst „1. Quell-Markdown wählen…“.",
            )
            return
        source = Path(raw)
        if not source.is_dir():
            QMessageBox.warning(self, "GG-Swap", f"Ordner nicht gefunden:\n{source}")
            return
        hub = check_source_folder(source)
        if hub.is_publish_hub:
            self._reject_publish_hub(hub.reason)
            return
        plan = self._effective_plan()
        ok_count = sum(1 for line in plan if line.status == "ok")
        unchanged = [line for line in plan if line.status == "unchanged"]
        if ok_count == 0:
            if unchanged:
                reply = QMessageBox.question(
                    self,
                    "Body schon übernommen",
                    "Der Nutzinhalt-Body ist bereits gleich dem Payload "
                    "(Swap war erfolgreich).\n\n"
                    "Der Anzeigename in der Buchstruktur kann noch der alte sein "
                    "(z. B. …Gemma4).\n\n"
                    "Jetzt den Anzeigenamen an den Payload anpassen?",
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._sync_titles_only()
                return
            QMessageBox.information(
                self,
                "GG-Swap",
                "Nichts zum Übernehmen (kein Status „bereit“).\n\n"
                "Pflicht: „1. Quell-Markdown wählen…“ — eine konkrete .md aus einem Publish_*-Lauf.",
            )
            return
        reply = QMessageBox.question(
            self,
            "GG-Inhalt übernehmen?",
            f"{ok_count} Datei(en):\n"
            "• Nutzinhalt-Body aus dem Payload übernehmen\n"
            "• Anzeigename (title) in der Buchstruktur an den Payload anpassen\n\n"
            "YAML-Frontmatter der Buchdatei bleibt erhalten (außer title/description).\n"
            "Backup unter bookconfig/.backups/gg-content-swap/.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        _plan, result = run_swap(
            book,
            source,
            dry_run=False,
            plan=plan,
            sync_title=True,
            allow_title_only=False,
        )
        self._plan = _plan
        for line in plan:
            if line.source_rel and (
                line.book_rel in result.written
                or any(line.book_rel in t for t in result.titles_updated)
            ):
                self._pinned_sources[line.book_rel] = line.source_rel

        log = getattr(self._studio, "log", None)
        if callable(log):
            log(
                f"GG-Swap fertig — geschrieben={len(result.written)} "
                f"titel={len(result.titles_updated)} fehler={len(result.errors)}",
                "success" if not result.errors else "warning",
            )
            for err in result.errors:
                log(f"GG-Swap Fehler: {err}", "error")

        if result.errors:
            QMessageBox.warning(
                self,
                "GG-Swap mit Fehlern",
                "Es gab Fehler:\n\n" + "\n".join(result.errors[:8]),
            )
            self._scan()
            return

        success_lines = ["✅ Swap erfolgreich!", ""]
        if result.written:
            success_lines.append("Body übernommen:")
            success_lines.extend(f"  • {p}" for p in result.written)
            success_lines.append("")
        if result.titles_updated:
            success_lines.append("Anzeigename in der Buchstruktur:")
            success_lines.extend(f"  • {t}" for t in result.titles_updated)
            success_lines.append("")
        success_lines.append(
            "Die Buchstruktur rechts sollte den neuen Namen zeigen "
            "(ggf. Projekt kurz neu laden)."
        )
        open_now = QMessageBox.question(
            self,
            "✅ GrammarGraph-Inhalt übernommen",
            "\n".join(success_lines) + "\n\nBuchdatei jetzt öffnen?",
        )
        self._refresh_studio_structure()
        self._scan()
        if open_now == QMessageBox.StandardButton.Yes:
            targets = result.written or [
                t.split(" → ", 1)[0] for t in result.titles_updated
            ]
            if targets:
                self._open_markdown(book / targets[0], title="Buchdatei (übernommen)")


def open_gg_content_swap_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    if not getattr(studio, "current_book", None):
        QMessageBox.information(parent, "GG-Swap", "Bitte zuerst ein Buch laden.")
        return
    GgContentSwapQtDialog(parent, studio).exec()
