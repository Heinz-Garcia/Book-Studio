"""Buch-Banner, KDP-Kanal-Flag und Production-UUID-Verknüpfung.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from tools.distribution.book_store import is_kdp_paperback, set_kdp_paperback
from tools.kdp_cover.binding import (
    binding_status_label,
    resolve_cover_binding,
)
from tools.kdp_cover.model import (
    CoverLayout,
)
from tools.production_uuid import normalize_uuid, read_book_uuid
from ui_qt.dialogs.kdp_cover.common import (
    _qlabel_color_ss,
)
from ui_qt.widgets.collapsible_section import CollapsibleSection


class BindingMixin:
    """Buch-Banner, KDP-Kanal-Flag und Production-UUID-Verknüpfung."""

    def _build_book_banner(self, parent_layout: QVBoxLayout) -> None:
        section = CollapsibleSection("Buch & KDP-Kanal", expanded=True)
        banner_layout = section.body_layout()

        if self._book:
            self.book_name_label = QLabel(f"Buch: {self._book.name}")
            self.book_name_label.setToolTip(str(self._book.resolve()))
            self.book_name_label.setStyleSheet("font-weight:600; color:#334b86;")
            self.book_name_label.setWordWrap(True)
        else:
            self.book_name_label = QLabel("Buch: (kein Buch geladen)")
            self.book_name_label.setStyleSheet("color:#8899bb;")
        banner_layout.addWidget(self.book_name_label)

        # El-Pitugrafo-Stil: Text auf der Checkbox + sichtbarer Indikator (App-Theme).
        self.kdp_channel_check = QCheckBox("KDP-Taschenbuch für dieses Buch")
        self.kdp_channel_check.setToolTip(
            "Schreibt bookconfig/distribution.json (Kanal kdp_paperback). "
            "Aktiviert die 1:1-Bindung an export/kdp_cover/{Buch}_kdp_cover.json — "
            "legt die Datei nicht automatisch an."
        )
        self.kdp_channel_check.setEnabled(bool(self._book))
        if self._book:
            self._kdp_flag_guard = True
            self.kdp_channel_check.setChecked(is_kdp_paperback(self._book))
            self._kdp_flag_guard = False
            self.kdp_channel_check.toggled.connect(self._on_kdp_flag_toggled)
        banner_layout.addWidget(self.kdp_channel_check)

        self.binding_status_label = QLabel("")
        self.binding_status_label.setWordWrap(True)
        self.binding_status_label.setStyleSheet(_qlabel_color_ss("#5b6785", size_px=12))
        banner_layout.addWidget(self.binding_status_label)

        cover_dir_row = QHBoxLayout()
        cover_dir_row.setSpacing(8)
        self.btn_open_cover_dir = QPushButton("Cover-Ordner öffnen…")
        self.btn_open_cover_dir.setToolTip(
            "Öffnet export/kdp_cover/ im Explorer (legt den Ordner bei Bedarf an)."
        )
        self.btn_open_cover_dir.clicked.connect(self._open_cover_export_dir)
        self.btn_open_cover_dir.setEnabled(bool(self._book))
        cover_dir_row.addWidget(self.btn_open_cover_dir, stretch=1)

        self.btn_pipette = QPushButton("Pipette…")
        self.btn_pipette.setToolTip(
            "Referenzbild laden, Farbe per Klick aufnehmen — Hex landet in der "
            "Zwischenablage (Fenster bleibt im Vordergrund). "
            "Für Front-, Rücken- und Layout-Farben."
        )
        self.btn_pipette.clicked.connect(self._open_color_pipette)
        cover_dir_row.addWidget(self.btn_pipette, stretch=1)

        self.btn_change_uuid = QPushButton("UUID ändern…")
        self.btn_change_uuid.setToolTip(
            "Production-UUID für dieses Cover wählen "
            "(GrammarGraph-Lieferung und/oder Book-Studio-Buch)."
        )
        self.btn_change_uuid.clicked.connect(self._change_production_uuid)
        cover_dir_row.addWidget(self.btn_change_uuid, stretch=1)

        self.btn_reset_safe_slots = QPushButton("Zurück auf Safe-Slots")
        self.btn_reset_safe_slots.setObjectName("kdpCoverResetSafeSlots")
        self.btn_reset_safe_slots.setToolTip(
            "Alle Experten-Offsets (Titel/Autor/Rücken) und die Titel-Skalierung "
            "auf die Standard-Safe-Slots zurücksetzen.\n"
            "Nur im Modus „Experte“ sinnvoll — im Sicheren Modus sind Offsets ohnehin 0."
        )
        self.btn_reset_safe_slots.setStyleSheet(
            """
            QPushButton#kdpCoverResetSafeSlots {
                background: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton#kdpCoverResetSafeSlots:hover {
                background: #ef4444;
                border-color: #dc2626;
            }
            QPushButton#kdpCoverResetSafeSlots:pressed {
                background: #b91c1c;
            }
            QPushButton#kdpCoverResetSafeSlots:disabled {
                background: #e5e7eb;
                color: #9ca3af;
                border: 1px solid #d1d5db;
            }
            """
        )
        self.btn_reset_safe_slots.clicked.connect(self._reset_free_offsets)
        self.btn_reset_safe_slots.setEnabled(False)
        cover_dir_row.addWidget(self.btn_reset_safe_slots, stretch=1)
        banner_layout.addLayout(cover_dir_row)

        self.uuid_link_label = QLabel("")
        self.uuid_link_label.setWordWrap(True)
        self.uuid_link_label.setStyleSheet(_qlabel_color_ss("#5b6785", size_px=12))
        banner_layout.addWidget(self.uuid_link_label)

        parent_layout.addWidget(section)
        self._refresh_uuid_link_ui()

    def _refresh_binding_ui(self) -> None:
        if not self._book:
            self.binding_status_label.setText(
                "Ohne Buchprojekt kein kanonisches Cover-Layout."
            )
            self.binding_status_label.setStyleSheet(_qlabel_color_ss("#64748b", size_px=12))
            return
        binding = resolve_cover_binding(self._book)
        self.binding_status_label.setText(binding_status_label(binding))
        self.binding_status_label.setToolTip(str(binding.canonical_path))
        if binding.status == "missing":
            self.binding_status_label.setStyleSheet(
                _qlabel_color_ss("#b45309", size_px=12, weight="600")
            )
        elif binding.status == "ready":
            self.binding_status_label.setStyleSheet(
                _qlabel_color_ss("#15803d", size_px=12)
            )
        else:
            self.binding_status_label.setStyleSheet(_qlabel_color_ss("#64748b", size_px=12))
        self._refresh_uuid_link_ui()

    def _refresh_uuid_link_ui(self) -> None:
        label = getattr(self, "uuid_link_label", None)
        if label is None:
            return
        uid = normalize_uuid(self._production_uuid) or ""
        if not uid:
            label.setText("Production-UUID: (noch nicht verknüpft)")
            label.setStyleSheet(_qlabel_color_ss("#b45309", size_px=12))
            label.setToolTip(
                "Beim Speichern/Export eine UUID aus GrammarGraph-Lieferungen "
                "oder Book-Studio-Büchern wählen."
            )
            return
        short = uid if len(uid) <= 13 else f"{uid[:8]}…"
        role = "Primary" if self._cover_role != "alternative" else "Alternative"
        origin = self._uuid_origin_label or "—"
        extra = f" „{self._cover_label}“" if self._cover_label.strip() else ""
        label.setText(f"Verknüpft: {short} ({role}){extra} — Herkunft: {origin}")
        label.setStyleSheet(_qlabel_color_ss("#15803d", size_px=12))
        label.setToolTip(uid)

    def _change_production_uuid(self) -> None:
        self._ensure_uuid_link(force=True)

    def _try_bind_uuid_from_active_book(self) -> bool:
        """UUID des aktiven Buchprojekts übernehmen — ohne Auswahldialog.

        Im Arbeitsweg ist das Buch schon gewählt; die Production-UUID steht am
        Buch (publish_meta / GG-Export / _book_studio.toml). Nur wenn sie
        fehlt, muss der Picker noch ran.
        """
        if not self._book:
            return False
        uid = normalize_uuid(read_book_uuid(self._book))
        if not uid:
            return False
        self._production_uuid = uid
        if not str(self._cover_role or "").strip():
            self._cover_role = "primary"
        if not self._uuid_origin_label:
            self._uuid_origin_label = "Aktives Buchprojekt"
        if not self._uuid_source_kinds:
            self._uuid_source_kinds = ["book_studio"]
        try:
            from tools.kdp_cover.assign_link import assign_cover_to_uuid

            existing = (
                Path(self._project_path)
                if getattr(self, "_project_path", None)
                else None
            )
            entry = assign_cover_to_uuid(
                production_uuid=self._production_uuid,
                cover_label=self._cover_label,
                cover_role=(
                    "alternative"
                    if str(self._cover_role or "").strip().lower() == "alternative"
                    else "primary"
                ),
                title_hint=self._book.name,
                source_kinds=self._uuid_source_kinds,
                book_path=self._book,
                cover_path=existing,
                repo=self._studio_repo(),
            )
            if existing is None and entry is not None:
                self._project_path = Path(entry.cover_path)
                label = getattr(self, "project_path_label", None)
                if label is not None:
                    label.setText(f"Cover-Layout: {entry.cover_path}")
        except (OSError, ValueError) as exc:
            log = getattr(self._studio, "log", None) if self._studio else None
            if callable(log):
                log(f"Cover↔UUID (Buch): {exc}", "warning")
        self._refresh_uuid_link_ui()
        return bool(normalize_uuid(self._production_uuid))

    def _ensure_uuid_link(self, *, force: bool = False) -> bool:
        """Ensure a production UUID is selected; return False if user cancels."""
        if not force and normalize_uuid(self._production_uuid):
            return True
        # Geführter Pfad: Buch schon bekannt → UUID vom Buch, kein Picker.
        if not force and self._try_bind_uuid_from_active_book():
            return True
        from ui_qt.dialogs.kdp_cover_uuid_dialog import pick_cover_uuid

        role = (
            "alternative"
            if str(self._cover_role or "").strip().lower() == "alternative"
            else "primary"
        )
        picked = pick_cover_uuid(
            self,
            studio=self._studio,
            book_root=self._book,
            preselect_uuid=self._production_uuid
            or (read_book_uuid(self._book) if self._book else "")
            or "",
            initial_label=self._cover_label,
            initial_role=role,  # type: ignore[arg-type]
        )
        if not picked:
            return False
        self._production_uuid = str(picked.get("uuid") or "").strip()
        self._cover_label = str(picked.get("cover_label") or "").strip()
        self._cover_role = (
            "alternative"
            if picked.get("cover_role") == "alternative"
            else "primary"
        )
        self._uuid_origin_label = str(picked.get("origin_label") or "").strip()
        kinds = picked.get("source_kinds") or []
        self._uuid_source_kinds = [str(k) for k in kinds if str(k).strip()]
        # Sofort in Registry — Cover-Spalte zeigt die Zuordnung beim nächsten Öffnen.
        try:
            from tools.kdp_cover.assign_link import assign_cover_to_uuid

            existing = (
                Path(self._project_path)
                if getattr(self, "_project_path", None)
                else None
            )
            entry = assign_cover_to_uuid(
                production_uuid=self._production_uuid,
                cover_label=self._cover_label,
                cover_role=self._cover_role,  # type: ignore[arg-type]
                title_hint=str(picked.get("title_hint") or ""),
                source_kinds=self._uuid_source_kinds,
                book_path=self._book,
                cover_path=existing,
                repo=self._studio_repo(),
            )
            if existing is None:
                self._project_path = Path(entry.cover_path)
                self.project_path_label.setText(f"Cover-Layout: {entry.cover_path}")
        except (OSError, ValueError) as exc:
            log = getattr(self._studio, "log", None) if self._studio else None
            if callable(log):
                log(f"Cover↔UUID-Registry: {exc}", "warning")
        self._refresh_uuid_link_ui()
        return bool(normalize_uuid(self._production_uuid))

    def _register_cover_uuid_link(self, cover_path: Path, layout: CoverLayout) -> None:
        from tools.kdp_cover.cover_registry import upsert_cover_link

        uid = normalize_uuid(layout.production_uuid)
        if not uid:
            return
        try:
            upsert_cover_link(
                production_uuid=uid,
                cover_path=cover_path,
                book_path=self._book,
                cover_label=layout.cover_label,
                cover_role=(
                    "alternative"
                    if layout.cover_role == "alternative"
                    else "primary"
                ),
                title_hint=layout.title or (self._book.name if self._book else ""),
                source_kinds=list(self._uuid_source_kinds),
            )
        except (OSError, ValueError):
            pass

    def _on_kdp_flag_toggled(self, checked: bool) -> None:
        if self._kdp_flag_guard or not self._book:
            return
        try:
            set_kdp_paperback(self._book, bool(checked))
        except OSError as exc:
            QMessageBox.critical(self, "Kanal-Flag", str(exc))
            self._kdp_flag_guard = True
            self.kdp_channel_check.setChecked(is_kdp_paperback(self._book))
            self._kdp_flag_guard = False
            return
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            state = "an" if checked else "aus"
            log(f"KDP-Taschenbuch-Kanal {state}: {self._book.name}", "info")
        self._refresh_binding_ui()

    def _open_cover_export_dir(self) -> None:
        if not self._book:
            return
        out = self._default_export_dir()
        out.mkdir(parents=True, exist_ok=True)
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))
        except OSError as exc:
            QMessageBox.warning(self, "Ordner öffnen", str(exc))
