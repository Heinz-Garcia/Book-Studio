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

from tools.layout_profiles.catalog import (
    LINE_STRETCH_OPTIONS,
    get_profile,
    linestretch_label,
    normalize_linestretch,
    profile_id_from_label,
    profile_labels,
)


def _default_pdf_stem(book_path: Optional[Path], initial: dict[str, Any]) -> str:
    explicit = str(initial.get("pdf_stem") or "").strip()
    if explicit:
        if explicit.lower().endswith(".pdf"):
            explicit = explicit[:-4].rstrip()
        return explicit
    if book_path is not None:
        try:
            from render_artifact_store import resolve_preferred_pdf_stem

            return resolve_preferred_pdf_stem(Path(book_path))
        except (OSError, ValueError, TypeError):
            return Path(book_path).name
    return ""


def _normalize_pdf_stem(raw: str) -> str:
    stem = str(raw or "").strip().replace("/", "_").replace("\\", "_")
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4].rstrip()
    return stem


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
        initial_stem = _default_pdf_stem(self.book_path, initial)

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

        self.pdf_stem_edit = QLineEdit()
        self.pdf_stem_edit.setText(initial_stem)
        self.pdf_stem_edit.setPlaceholderText(
            "Dateiname ohne .pdf — z. B. Publish_MeinBuch_rev.07"
        )
        self.pdf_stem_edit.setClearButtonEnabled(True)
        form.addRow("Dateiname:", self.pdf_stem_edit)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Zielpfad der gerenderten Datei")
        form.addRow("Pfad:", self.path_edit)

        self.notes_edit = QLineEdit()
        self.notes_edit.setText(str(initial.get("notes") or "").strip())
        self.notes_edit.setPlaceholderText(
            "Anzeigename: z. B. rev.5 Probe — erscheint im PDF Manager (nicht Layout/BoD)"
        )
        self.notes_edit.setClearButtonEnabled(True)
        form.addRow("Anzeigename:", self.notes_edit)

        layout.addLayout(form)

        self.hint = QLabel(initial_profile.description)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addWidget(
            QLabel(
                "Dateiname = Name der PDF-Datei (änderbar). "
                "Pfad = Convenience-Ausgabe unter export/_book "
                "(Archiv zusätzlich im PDF Manager)."
            )
        )
        layout.addWidget(
            QLabel(
                "Anzeigename = optionaler Merknamen zum Wiederfinden. "
                "Layout wählst du darüber im Layout-Profil."
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
        self.pdf_stem_edit.textChanged.connect(self._refresh_path_preview)
        self.format_combo.currentTextChanged.connect(self._refresh_path_preview)
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

        return RenderService.build_render_out_dir(self.book_path, self._profile_name)

    def _refresh_path_preview(self, *_args: Any) -> None:
        out_dir = self._out_dir()
        stem = _normalize_pdf_stem(self.pdf_stem_edit.text())
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
        stem = _normalize_pdf_stem(self.pdf_stem_edit.text())
        self.result = {
            "format": self.format_combo.currentText(),
            "template": self.template_combo.currentText(),
            "layout_profile": profile_id_from_label(self.profile_combo.currentText()),
            "linestretch": self._selected_linestretch(),
            "notes": self.notes_edit.text().strip(),
            "pdf_stem": stem,
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
