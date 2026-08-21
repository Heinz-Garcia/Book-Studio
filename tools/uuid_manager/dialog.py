"""Qt-Dialog für den UUID-Manager."""

# pylint: disable=no-name-in-module, not-callable

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

import app_config as _app_config
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.book_projects.catalog import list_content_roots
from tools.kdp_cover.cover_registry import CoverRegistryEntry, load_registry
from tools.kdp_cover.uuid_choices import format_cover_link_detail, format_cover_link_summary
from tools.production_paths.paths import legacy_publish_hubs_from_content_roots, target_inbox_dir
from tools.production_uuid import normalize_uuid
from tools.uuid_manager.model import UuidRecord, UuidStatus, uuid_status_label
from tools.uuid_manager.service import collect_uuid_records

_FILTER_NONE = "__none__"
_FILTER_ALL = ""
_FILTER_COVER_YES = "__cover_yes__"
_FILTER_COVER_NO = "__cover_no__"


def _status_color(status: UuidStatus) -> QColor:
    colors = {
        UuidStatus.delivery_only: QColor("#f59e0b"),
        UuidStatus.imported_no_render: QColor("#f59e0b"),
        UuidStatus.rendered_pdf_present: QColor("#60a5fa"),
        UuidStatus.pdf_uuid_match: QColor("#16a34a"),
        UuidStatus.pdf_uuid_mismatch: QColor("#dc2626"),
        UuidStatus.orphan_book: QColor("#ef4444"),
        UuidStatus.orphan_pdf: QColor("#ef4444"),
    }
    return colors[status]


def _open_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _reveal_in_explorer(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603


class UuidManagerDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        studio: Any = None,
        book_studio_repo: Path,
        grammargraph_repo: Path | None = None,
        window_title: str = "UUID-Manager",
    ) -> None:
        super().__init__(parent)
        self._studio = studio
        self._book_studio_repo = Path(book_studio_repo).resolve()
        self._grammargraph_repo = (
            Path(grammargraph_repo).resolve() if grammargraph_repo is not None else None
        )
        self._records: list[UuidRecord] = []
        self._filtered: list[UuidRecord] = []
        self._covers_by_uuid: dict[str, list[CoverRegistryEntry]] = {}
        self._help_texts = self._read_help_texts()

        self.setWindowTitle(window_title)
        self.setMinimumSize(1260, 720)
        self.resize(1420, 820)

        layout = QVBoxLayout(self)
        title = QLabel(window_title)
        f = QFont(title.font())
        f.setPointSize(16)
        f.setWeight(QFont.Weight.DemiBold)
        title.setFont(f)
        layout.addWidget(title)

        top = QHBoxLayout()
        top.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        # Default "Keine": Fenster öffnet ohne teuren Vollscan.
        self.status_combo.addItem("Keine", _FILTER_NONE)
        self.status_combo.addItem("Alle", _FILTER_ALL)
        self.status_combo.addItem("Mit Cover-Zuordnung", _FILTER_COVER_YES)
        self.status_combo.addItem("Ohne Cover-Zuordnung", _FILTER_COVER_NO)
        for status in UuidStatus:
            self.status_combo.addItem(uuid_status_label(status), status.value)
        self.status_combo.setCurrentIndex(0)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        top.addWidget(self.status_combo)
        self.help_banner = QLabel("")
        self.help_banner.setWordWrap(True)
        self.help_banner.setMinimumWidth(420)
        self.help_banner.setStyleSheet(
            "QLabel { background-color: #eaf4ff; color: #26415f; "
            "border: 1px solid #c7dcf6; border-radius: 6px; padding: 8px 10px; }"
        )
        top.addWidget(self.help_banner, stretch=1)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(
            "Filtern: UUID, Buch, Variante, Cover, Publish, Batch, PDF …"
        )
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMinimumWidth(340)
        top.addWidget(self.filter_edit)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(lambda: self.reload(force_scan=True))
        top.addWidget(refresh)
        layout.addLayout(top)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color:#5b6573;")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Status",
                "UUID",
                "Buch",
                "Variante",
                "Cover",
                "Lieferung",
                "PDF",
                "Batch",
                "Hinweise",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._sync_detail)
        self.table.cellDoubleClicked.connect(self._open_selected_pdf)
        header = self.table.horizontalHeader()
        for col in range(9):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Detailansicht der ausgewählten UUID …")
        self.detail.setMinimumHeight(170)
        layout.addWidget(self.detail)

        actions = QHBoxLayout()
        self.btn_open_publish = QPushButton("Lieferordner öffnen")
        self.btn_open_publish.clicked.connect(self._open_selected_publish)
        actions.addWidget(self.btn_open_publish)
        self.btn_open_book = QPushButton("Buchordner öffnen")
        self.btn_open_book.clicked.connect(self._open_selected_book)
        actions.addWidget(self.btn_open_book)
        self.btn_open_pdf = QPushButton("PDF öffnen")
        self.btn_open_pdf.clicked.connect(self._open_selected_pdf)
        actions.addWidget(self.btn_open_pdf)
        self.btn_reveal_pdf = QPushButton("PDF im Explorer")
        self.btn_reveal_pdf.clicked.connect(self._reveal_selected_pdf)
        actions.addWidget(self.btn_reveal_pdf)
        self.btn_copy = QPushButton("Pfad kopieren")
        self.btn_copy.clicked.connect(self._copy_selected_path)
        actions.addWidget(self.btn_copy)
        actions.addStretch(1)
        export_csv = QPushButton("CSV exportieren…")
        export_csv.clicked.connect(self._export_csv)
        actions.addWidget(export_csv)
        export_json = QPushButton("JSON exportieren…")
        export_json.clicked.connect(self._export_json)
        actions.addWidget(export_json)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)

        self.reload(force_scan=False)

    def _log(self, message: str, level: str = "info") -> None:
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(message, level)

    def _read_help_texts(self) -> dict[str, str]:
        try:
            cfg = _app_config.read_config(self._book_studio_repo / "app_config.json")
        except (OSError, TypeError, ValueError):
            cfg = {}
        merged = _app_config.with_defaults(cfg)
        fallback = str(merged.get("uuid_manager_help_text") or "").strip()
        raw = merged.get("uuid_manager_help_texts")
        if not isinstance(raw, dict):
            out = {"": fallback}
        else:
            out = {
                str(key): str(value).strip()
                for key, value in raw.items()
                if str(value).strip()
            }
            out.setdefault("", fallback)
        out.setdefault(
            _FILTER_NONE,
            "Kein Scan beim Öffnen. Wähle „Alle“ oder einen Status, "
            "oder klicke „Aktualisieren“, um UUID-Fälle zu laden.",
        )
        out.setdefault(
            _FILTER_COVER_YES,
            "Nur Produktionen mit Eintrag in der Cover↔UUID-Registry "
            "(Primary/Alternative). Spalte „Cover“ zeigt Label/Datei.",
        )
        out.setdefault(
            _FILTER_COVER_NO,
            "Nur Produktionen ohne Cover-Zuordnung in der Registry.",
        )
        return out

    def _help_text_for_selected_status(self) -> str:
        key = str(self.status_combo.currentData() or "")
        return self._help_texts.get(key) or self._help_texts.get("") or ""

    def _status_is_none(self) -> bool:
        return str(self.status_combo.currentData() or "") == _FILTER_NONE

    def _covers_for(self, uid: str) -> list[CoverRegistryEntry]:
        key = (normalize_uuid(uid) or uid).casefold()
        return list(self._covers_by_uuid.get(key, []))

    def _cover_summary(self, uid: str) -> str:
        return format_cover_link_summary(self._covers_for(uid))

    def _load_cover_registry(self) -> dict[str, list[CoverRegistryEntry]]:
        by_uid: dict[str, list[CoverRegistryEntry]] = {}
        try:
            data = load_registry()
        except OSError:
            return by_uid
        for raw in data.get("entries") or []:
            if not isinstance(raw, dict):
                continue
            entry = CoverRegistryEntry.from_dict(raw)
            uid = normalize_uuid(entry.production_uuid) or str(
                entry.production_uuid or ""
            ).strip()
            if not uid:
                continue
            by_uid.setdefault(uid.casefold(), []).append(entry)
        return by_uid

    def _on_status_changed(self) -> None:
        self.help_banner.setText(self._help_text_for_selected_status())
        if self._status_is_none():
            self._records = []
            self._apply_filter()
            return
        # Leaving "Keine" → load once (or refresh if already loaded).
        if not self._records:
            self.reload(force_scan=True)
            return
        self._apply_filter()

    def reload(self, *, force_scan: bool = True) -> None:
        """Load UUID records.

        With Status „Keine“ and ``force_scan=False`` (window open), skip the
        expensive filesystem scan so the dialog appears immediately.
        """
        if self._status_is_none() and not force_scan:
            self._records = []
            self.help_banner.setText(self._help_text_for_selected_status())
            self._apply_filter()
            return
        if self._status_is_none() and force_scan:
            # User clicked Aktualisieren while "Keine" is selected — still
            # load into memory but keep the empty filter until they pick a status.
            self._records = collect_uuid_records(
                book_studio_repo=self._book_studio_repo,
                grammargraph_repo=self._grammargraph_repo,
            )
            self._covers_by_uuid = self._load_cover_registry()
            self.help_banner.setText(self._help_text_for_selected_status())
            self._apply_filter()
            return
        self._records = collect_uuid_records(
            book_studio_repo=self._book_studio_repo,
            grammargraph_repo=self._grammargraph_repo,
        )
        self._covers_by_uuid = self._load_cover_registry()
        self.help_banner.setText(self._help_text_for_selected_status())
        self._apply_filter()

    def _scan_summary(self) -> str:
        roots = [str(path) for path in list_content_roots(repo=self._book_studio_repo)]
        inbox = str(target_inbox_dir(repo=self._book_studio_repo))
        legacy = [
            str(path)
            for path in legacy_publish_hubs_from_content_roots(repo=self._book_studio_repo)
        ]
        roots_text = "; ".join(roots) if roots else "—"
        legacy_text = "; ".join(legacy) if legacy else "—"
        return (
            f"Buch-Roots: {roots_text} | Inbox: {inbox} | Legacy-Publish: {legacy_text}"
        )

    def _apply_filter(self) -> None:
        if self._status_is_none():
            self._filtered = []
            if self._records:
                self.summary_label.setText(
                    f"Status „Keine“ — {len(self._records)} Fälle geladen, "
                    "aber nicht angezeigt. Wähle „Alle“ oder einen Status."
                )
            else:
                self.summary_label.setText(
                    "Status „Keine“ — noch kein Scan. "
                    "Wähle „Alle“/Status oder „Aktualisieren“."
                )
            self._fill_table()
            return
        needle = self.filter_edit.text().strip().casefold()
        wanted = str(self.status_combo.currentData() or "")
        self._filtered = []
        for rec in self._records:
            has_cover = bool(self._covers_for(rec.uuid))
            if wanted == _FILTER_COVER_YES and not has_cover:
                continue
            if wanted == _FILTER_COVER_NO and has_cover:
                continue
            if (
                wanted
                and wanted not in {_FILTER_COVER_YES, _FILTER_COVER_NO}
                and rec.status.value != wanted
            ):
                continue
            cover_summary = self._cover_summary(rec.uuid)
            cover_detail = format_cover_link_detail(self._covers_for(rec.uuid))
            hay = " ".join(
                [
                    rec.uuid,
                    rec.book_title,
                    rec.market_variant,
                    rec.batch_id,
                    cover_summary,
                    cover_detail,
                    str(rec.publish_dir or ""),
                    str(rec.book_path or ""),
                    str(rec.pdf_path or ""),
                    " ".join(rec.notes),
                ]
            ).casefold()
            if needle and needle not in hay:
                continue
            self._filtered.append(rec)
        if self._records:
            self.summary_label.setText(
                f"{len(self._filtered)} von {len(self._records)} UUID-Fällen sichtbar."
            )
        else:
            self.summary_label.setText(
                "Keine UUID-Artefakte gefunden. "
                + self._scan_summary()
            )
        self._fill_table()

    def _fill_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._filtered))
        for row, rec in enumerate(self._filtered):
            status_item = QTableWidgetItem(rec.status_label)
            status_item.setData(Qt.ItemDataRole.UserRole, rec.uuid)
            status_item.setBackground(_status_color(rec.status))
            self.table.setItem(row, 0, status_item)
            self.table.setItem(row, 1, QTableWidgetItem(rec.uuid))
            self.table.setItem(row, 2, QTableWidgetItem(rec.book_title or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(rec.market_variant or "—"))
            cover_item = QTableWidgetItem(self._cover_summary(rec.uuid))
            cover_item.setToolTip(format_cover_link_detail(self._covers_for(rec.uuid)))
            self.table.setItem(row, 4, cover_item)
            self.table.setItem(
                row,
                5,
                QTableWidgetItem(str(rec.publish_dir) if rec.publish_dir else "—"),
            )
            self.table.setItem(
                row,
                6,
                QTableWidgetItem(str(rec.pdf_path) if rec.pdf_path else "—"),
            )
            self.table.setItem(row, 7, QTableWidgetItem(rec.batch_id or "—"))
            self.table.setItem(row, 8, QTableWidgetItem(" | ".join(rec.notes) or "—"))
        self.table.setSortingEnabled(True)
        if self._filtered:
            self.table.selectRow(0)
        else:
            self.detail.clear()

    def _selected_record(self) -> UuidRecord | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            return None
        return self._filtered[row]

    def _sync_detail(self) -> None:
        rec = self._selected_record()
        if rec is None:
            self.detail.clear()
            return
        payload = rec.to_dict()
        covers = self._covers_for(rec.uuid)
        payload["cover_links"] = [entry.to_dict() for entry in covers]
        payload["cover_summary"] = format_cover_link_summary(covers)
        self.detail.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))

    def _guard_path(self, path: Path | None, label: str) -> Path | None:
        if path is None:
            QMessageBox.information(self, "UUID-Manager", f"Kein {label} vorhanden.")
            return None
        if not path.exists():
            QMessageBox.warning(self, "UUID-Manager", f"{label} nicht gefunden:\n{path}")
            return None
        return path

    def _open_selected_publish(self) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        path = self._guard_path(rec.publish_dir, "Lieferordner")
        if path is not None:
            _open_path(path)

    def _open_selected_book(self) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        path = self._guard_path(rec.book_path, "Buchordner")
        if path is not None:
            _open_path(path)

    def _open_selected_pdf(self) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        path = self._guard_path(rec.pdf_path, "PDF")
        if path is not None:
            _open_path(path)

    def _reveal_selected_pdf(self) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        path = self._guard_path(rec.pdf_path, "PDF")
        if path is not None:
            _reveal_in_explorer(path)

    def _copy_selected_path(self) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        text = ""
        if rec.pdf_path is not None:
            text = str(rec.pdf_path)
        elif rec.book_path is not None:
            text = str(rec.book_path)
        elif rec.publish_dir is not None:
            text = str(rec.publish_dir)
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._log(f"UUID-Manager: Pfad kopiert: {text}", "info")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "UUID-Manager CSV speichern",
            str(self._book_studio_repo / "uuid_manager.csv"),
            "CSV (*.csv)",
        )
        if not path:
            return
        with Path(path).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "status",
                    "uuid",
                    "book_title",
                    "market_variant",
                    "cover",
                    "publish_dir",
                    "book_path",
                    "pdf_path",
                    "batch_id",
                    "notes",
                ]
            )
            for rec in self._filtered:
                writer.writerow(
                    [
                        rec.status.value,
                        rec.uuid,
                        rec.book_title,
                        rec.market_variant,
                        self._cover_summary(rec.uuid),
                        str(rec.publish_dir or ""),
                        str(rec.book_path or ""),
                        str(rec.pdf_path or ""),
                        rec.batch_id,
                        " | ".join(rec.notes),
                    ]
                )
        self._log(f"UUID-Manager CSV exportiert: {path}", "success")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "UUID-Manager JSON speichern",
            str(self._book_studio_repo / "uuid_manager.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        payload = [rec.to_dict() for rec in self._filtered]
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._log(f"UUID-Manager JSON exportiert: {path}", "success")


def run_dialog(
    *,
    parent: Optional[QWidget] = None,
    studio: Any = None,
    book_studio_repo: Path,
    grammargraph_repo: Path | None = None,
    window_title: str = "UUID-Manager",
) -> int:
    dlg = UuidManagerDialog(
        parent,
        studio=studio,
        book_studio_repo=book_studio_repo,
        grammargraph_repo=grammargraph_repo,
        window_title=window_title,
    )
    return int(dlg.exec())


__all__ = ["UuidManagerDialog", "run_dialog"]
