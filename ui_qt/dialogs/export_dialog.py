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
        self.resize(520, 360)
        self.book_path = book_path
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

        layout.addLayout(form)

        self.hint = QLabel(initial_profile.description)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addWidget(
            QLabel(
                "Wird nur in die Temp-Kopie für den Render geschrieben — _quarto.yml bleibt unverändert."
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
        self.result = {
            "format": self.format_combo.currentText(),
            "template": self.template_combo.currentText(),
            "layout_profile": profile_id_from_label(self.profile_combo.currentText()),
            "linestretch": self._selected_linestretch(),
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
