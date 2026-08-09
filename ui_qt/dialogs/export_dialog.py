"""Qt-Export-Dialog (Parität zu ``export_dialog.ExportDialog``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from render_artifact_store import (
    default_export_display_name,
    normalize_pdf_stem_from_display,
)
from tools.distribution.book_store import CHANNEL_KDP_PAPERBACK, is_kdp_paperback, list_excluded_chapters
from tools.layout_profiles.catalog import (
    LINE_STRETCH_OPTIONS,
    get_profile,
    linestretch_label,
    normalize_linestretch,
    profile_id_from_label,
    profile_labels,
)

_CHANNEL_STANDARD_LABEL = "Standard"
_CHANNEL_KDP_LABEL = "Amazon KDP (Interior, ohne Cover-Seiten)"
_CHANNEL_LABEL_TO_ID = {
    _CHANNEL_STANDARD_LABEL: "",
    _CHANNEL_KDP_LABEL: CHANNEL_KDP_PAPERBACK,
}


def _default_display_name(book_path: Optional[Path], initial: dict[str, Any]) -> str:
    """Anzeigename: explizit aus initial, sonst aus Buchprojekt."""
    explicit = str(initial.get("notes") or "").strip()
    if explicit:
        return explicit
    if book_path is not None:
        try:
            return default_export_display_name(Path(book_path))
        except (OSError, ValueError, TypeError):
            return Path(book_path).name
    return ""


def _default_pdf_stem(
    book_path: Optional[Path],
    initial: dict[str, Any],
    display_name: str,
) -> str:
    """Dateiname: explizit aus initial, sonst normalisierter Anzeigename."""
    explicit = str(initial.get("pdf_stem") or "").strip()
    if explicit:
        return normalize_pdf_stem_from_display(explicit)
    derived = normalize_pdf_stem_from_display(display_name)
    if derived:
        return derived
    if book_path is not None:
        return normalize_pdf_stem_from_display(Path(book_path).name)
    return ""


class ExportDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        templates: list[str],
        initial: Optional[dict[str, Any]] = None,
        *,
        book_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export & Layout")
        self.setModal(True)
        self.resize(560, 420)
        self.book_path = Path(book_path) if book_path else None
        self._profile_name = str((initial or {}).get("profile_name") or "").strip() or None
        self.result: Optional[dict[str, Any]] = None
        self._stem_linked = True
        self._updating_stem = False

        initial = initial or {}
        templates = templates or ["Standard"]
        initial_format = str(initial.get("format") or "typst")
        initial_template = str(initial.get("template") or templates[0])
        if initial_template not in templates:
            initial_template = templates[0]
        initial_profile_id = str(initial.get("layout_profile") or "taschenbuch-bod")
        initial_profile = get_profile(initial_profile_id)
        initial_linestretch = normalize_linestretch(
            initial.get("linestretch", initial_profile.linestretch)
        )
        initial_display = _default_display_name(self.book_path, initial)
        initial_stem = _default_pdf_stem(self.book_path, initial, initial_display)
        # Entkoppeln, wenn initial explizit abweichenden Stem mitliefert.
        if str(initial.get("pdf_stem") or "").strip():
            self._stem_linked = (
                normalize_pdf_stem_from_display(initial_stem)
                == normalize_pdf_stem_from_display(initial_display)
            )

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["typst", "docx", "html", "pdf"])
        self.format_combo.setCurrentText(initial_format)
        form.addRow("Format:", self.format_combo)

        self.template_combo = QComboBox()
        self.template_combo.addItems(templates)
        self.template_combo.setCurrentText(initial_template)
        form.addRow("Template:", self.template_combo)

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(profile_labels())
        self.profile_combo.setCurrentText(initial_profile.label)
        form.addRow("Layout-Profil:", self.profile_combo)

        self.linestretch_combo = QComboBox()
        self.linestretch_combo.addItems([opt.label for opt in LINE_STRETCH_OPTIONS])
        self.linestretch_combo.setCurrentText(linestretch_label(initial_linestretch))
        form.addRow("Zeilenabstand:", self.linestretch_combo)

        self._kdp_channel_available = bool(
            self.book_path is not None and is_kdp_paperback(self.book_path)
        )
        self.channel_combo = QComboBox()
        channel_labels = [_CHANNEL_STANDARD_LABEL]
        if self._kdp_channel_available:
            channel_labels.append(_CHANNEL_KDP_LABEL)
        self.channel_combo.addItems(channel_labels)
        initial_channel_id = str(initial.get("render_channel") or "").strip()
        if initial_channel_id == CHANNEL_KDP_PAPERBACK and self._kdp_channel_available:
            self.channel_combo.setCurrentText(_CHANNEL_KDP_LABEL)
        form.addRow("Ziel-Kanal:", self.channel_combo)

        self.channel_hint = QLabel("")
        self.channel_hint.setWordWrap(True)
        form.addRow("", self.channel_hint)

        self.notes_edit = QLineEdit()
        self.notes_edit.setText(initial_display)
        self.notes_edit.setPlaceholderText(
            "Anzeigename — erscheint im PDF Manager (aus Buchprojekt vorbelegt)"
        )
        self.notes_edit.setClearButtonEnabled(True)
        form.addRow("Anzeigename:", self.notes_edit)

        self.pdf_stem_edit = QLineEdit()
        self.pdf_stem_edit.setText(initial_stem)
        self.pdf_stem_edit.setPlaceholderText(
            "Dateiname ohne .pdf — abgeleitet aus dem Anzeigenamen"
        )
        self.pdf_stem_edit.setClearButtonEnabled(True)
        form.addRow("Dateiname:", self.pdf_stem_edit)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Zielpfad der gerenderten Datei")
        form.addRow("Pfad:", self.path_edit)

        market_variant = ""
        variant_system_prompt = ""
        if self.book_path is not None:
            try:
                from tools.publish_map.metadata import provenance_summary

                prov = provenance_summary(self.book_path)
                market_variant = str(prov.get("market_variant") or "").strip()
                variant_system_prompt = str(
                    prov.get("variant_system_prompt_path") or ""
                ).strip()
            except (OSError, TypeError, ValueError, ImportError):
                market_variant = ""
                variant_system_prompt = ""

        self.market_variant_label = QLabel("")
        self.market_variant_label.setWordWrap(True)
        if market_variant:
            prompt_name = (
                Path(variant_system_prompt).name if variant_system_prompt else "—"
            )
            self.market_variant_label.setText(
                f"Marktvariante: {market_variant} · Systemprompt: {prompt_name}"
            )
            self.market_variant_label.setStyleSheet(
                "QLabel { color: #166534; background: #ecfdf3; "
                "border: 1px solid #bbf7d0; border-radius: 6px; padding: 6px 8px; }"
            )
        else:
            self.market_variant_label.setText(
                "Marktvariante: keine (Basisbuch / ohne Variantenkontext)"
            )
            self.market_variant_label.setStyleSheet("color: #5b6573;")
        form.addRow("Provenance:", self.market_variant_label)
        self._market_variant = market_variant
        self._variant_system_prompt = variant_system_prompt

        layout.addLayout(form)

        self.hint = QLabel(initial_profile.description)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addWidget(
            QLabel(
                "Anzeigename = vorbelegt aus dem Buchprojekt "
                "(project_label oder Ordnername). "
                "Dateiname = normalisierte Ableitung davon (änderbar)."
            )
        )
        layout.addWidget(
            QLabel(
                "Pfad = Convenience-Ausgabe unter export/_book "
                "(Archiv zusätzlich im PDF Manager)."
            )
        )
        layout.addWidget(
            QLabel(
                "Layout wird nur in die Temp-Kopie für den Render geschrieben — "
                "_quarto.yml bleibt unverändert."
            )
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export starten")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        self.pdf_stem_edit.textChanged.connect(self._on_stem_changed)
        self.format_combo.currentTextChanged.connect(self._refresh_path_preview)
        self.channel_combo.currentTextChanged.connect(self._on_channel_changed)
        self._on_channel_changed()

    def _selected_render_channel_id(self) -> str:
        return _CHANNEL_LABEL_TO_ID.get(self.channel_combo.currentText(), "")

    def _on_channel_changed(self, _text: str = "") -> None:
        channel_id = self._selected_render_channel_id()
        if not channel_id:
            self.channel_hint.setText(
                "Standard: enthält alle Kapitel der Buchstruktur (inkl. Deckblatt)."
            )
        elif self.book_path is not None:
            excluded = list_excluded_chapters(self.book_path, channel_id)
            if excluded:
                self.channel_hint.setText(
                    "Ausgeschlossen für diesen Kanal: " + ", ".join(excluded)
                )
            else:
                self.channel_hint.setText(
                    "Kein Kapitel als Interior-Ausschluss markiert — per Rechtsklick "
                    "im Struktur-Panel auf ein Kapitel (z. B. Deckblatt) markieren, "
                    "falls es nicht ins KDP-Interior soll."
                )
        self._refresh_path_preview()

    def _artifact_suffix(self) -> str:
        fmt = (self.format_combo.currentText() or "typst").lower()
        if fmt in ("typst", "pdf"):
            return ".pdf"
        if fmt == "html":
            return ".html"
        if fmt == "docx":
            return ".docx"
        return ".pdf"

    def _out_dir(self) -> Optional[Path]:
        if self.book_path is None:
            return None
        from services.render_service import RenderService

        effective_profile_name = RenderService.compose_channel_profile_name(
            self._profile_name, self._selected_render_channel_id()
        )
        return RenderService.build_render_out_dir(self.book_path, effective_profile_name)

    def _on_notes_changed(self, *_args: Any) -> None:
        if self._stem_linked:
            self._updating_stem = True
            try:
                self.pdf_stem_edit.setText(
                    normalize_pdf_stem_from_display(self.notes_edit.text())
                )
            finally:
                self._updating_stem = False
        self._refresh_path_preview()

    def _on_stem_changed(self, *_args: Any) -> None:
        if not self._updating_stem:
            derived = normalize_pdf_stem_from_display(self.notes_edit.text())
            current = normalize_pdf_stem_from_display(self.pdf_stem_edit.text())
            self._stem_linked = current == derived
        self._refresh_path_preview()

    def _refresh_path_preview(self, *_args: Any) -> None:
        out_dir = self._out_dir()
        stem = normalize_pdf_stem_from_display(self.pdf_stem_edit.text())
        if out_dir is None:
            self.path_edit.setText("")
            return
        if not stem:
            self.path_edit.setText(str(out_dir))
            return
        self.path_edit.setText(str(out_dir / f"{stem}{self._artifact_suffix()}"))

    def _on_profile_changed(self, _text: str = "") -> None:
        profile = get_profile(profile_id_from_label(self.profile_combo.currentText()))
        self.hint.setText(profile.description)
        self.linestretch_combo.setCurrentText(linestretch_label(profile.linestretch))

    def _selected_linestretch(self) -> float:
        label = self.linestretch_combo.currentText()
        for opt in LINE_STRETCH_OPTIONS:
            if opt.label == label:
                return opt.value
        return normalize_linestretch(1.2)

    def _confirm(self) -> None:
        stem = normalize_pdf_stem_from_display(self.pdf_stem_edit.text())
        if self._market_variant and not self._variant_system_prompt:
            from PySide6.QtWidgets import QMessageBox

            answer = QMessageBox.question(
                self,
                "Unvollständiger Variantenkontext",
                f"Marktvariante „{self._market_variant}“ ist gesetzt, "
                "aber kein Variantensystemprompt in der Provenance.\n\n"
                "Trotzdem rendern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.result = {
            "format": self.format_combo.currentText(),
            "template": self.template_combo.currentText(),
            "layout_profile": profile_id_from_label(self.profile_combo.currentText()),
            "linestretch": self._selected_linestretch(),
            "notes": self.notes_edit.text().strip(),
            "pdf_stem": stem,
            "market_variant": self._market_variant,
            "render_channel": self._selected_render_channel_id(),
        }
        self.accept()


def ask_export_options(
    parent: Optional[QWidget],
    templates: list[str],
    initial: Optional[dict[str, Any]] = None,
    *,
    book_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    dialog = ExportDialog(parent, templates, initial=initial, book_path=book_path)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.result
    return None
