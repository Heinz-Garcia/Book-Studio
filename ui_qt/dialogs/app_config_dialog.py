"""Studio-Konfiguration — deklaratives Formular für app_config.json.

Elegante Variante (kein JSON-Baum-Editor): Feldliste mit Typen
(path / path_list / file / str / enum / bool / int / float), Ordner-/Datei-Browse und
Gruppen. Nested Keys (frontmatter_requirements, editor_end_commands)
bleiben bewusst aus dem Formular; Speichern merget in die geladene Config.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

import app_config as _app_config
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

FieldKind = Literal["path", "path_list", "file", "str", "enum", "bool", "int", "float"]


@dataclass(frozen=True)
class ConfigField:
    key: str
    label: str
    kind: FieldKind
    group: str
    tip: str = ""
    choices: tuple[str, ...] = ()
    minimum: float = 0
    maximum: float = 1_000_000
    step: float = 1
    # Nur kind=file: QFileDialog-Filter, z. B. "ExifTool (exiftool.exe)"
    file_filter: str = ""


def _layout_profile_choices() -> tuple[str, ...]:
    try:
        from tools.layout_profiles.catalog import profile_ids

        return tuple(profile_ids())
    except (ImportError, OSError, TypeError, ValueError):
        return ("taschenbuch-bod", "paperback", "standard")


# SSOT der GUI-Felder — neue Keys hier ergänzen (und in app_config.DEFAULTS).
FIELDS: tuple[ConfigField, ...] = (
    ConfigField(
        "content_root_path",
        "Buch-Suchpfade",
        "path_list",
        "Pfade",
        tip="Mehrere Pfade durch Komma trennen. „Ordner…“ hängt einen Pfad an.",
    ),
    ConfigField(
        "production_root_path",
        "Production-Root",
        "path",
        "Pfade",
        tip="Relativ zum Repo oder absolut (Standard: production).",
    ),
    ConfigField(
        "books_workspace_path",
        "Bücher-Workspace",
        "path",
        "Pfade",
        tip="Leer = <production>/books. Überschreibt den Bücher-Ordner.",
    ),
    ConfigField(
        "grammargraph_inbox_path",
        "GrammarGraph-Inbox",
        "path",
        "Pfade",
        tip="Optionaler Eingangsordner für GG-Lieferungen.",
    ),
    ConfigField(
        "pdf_deploy_folder",
        "PDF-Deploy-Ordner",
        "path",
        "Pfade",
        tip="Ziel für „Deploy“ im PDF Manager. Leer = WEB.DE-Discovery.",
    ),
    ConfigField(
        "exiftool_path",
        "ExifTool-Pfad",
        "file",
        "Pfade",
        tip="Pfad zu exiftool.exe für Production-UUID in PDF-Metadaten. Leer = PATH.",
        file_filter="ExifTool (exiftool.exe exiftool);;Alle Dateien (*)",
    ),
    ConfigField(
        "uuid_manager_help_text",
        "UUID-Manager-Hilfe",
        "str",
        "Pfade",
        tip="Kurzer Orientierungstext für das Hilfe-Badge im UUID-Manager.",
    ),
    ConfigField(
        "asset_pool_path",
        "Asset-Pool",
        "path",
        "Pfade",
        tip="Zentraler Bild-Pool (Asset Manager).",
    ),
    ConfigField(
        "sanitizer_backup_path",
        "Sanitizer-Backup",
        "path",
        "Pfade",
    ),
    ConfigField(
        "prep_sources",
        "Prep-Quellen",
        "path_list",
        "Pfade",
        tip="Book-Preper-Quellen, Komma-getrennt.",
    ),
    ConfigField(
        "prep_dest_folder",
        "Prep-Zielordner",
        "path",
        "Pfade",
    ),
    ConfigField(
        "indexer_target_folder",
        "Indexer-Zielordner",
        "path",
        "Pfade",
    ),
    ConfigField(
        "skeleton_library_path",
        "Skeleton-Bibliothek",
        "path",
        "Pfade",
    ),
    ConfigField(
        "default_export_format",
        "Export-Format",
        "enum",
        "Export",
        choices=("typst", "docx", "html", "pdf"),
    ),
    ConfigField(
        "default_export_template",
        "Export-Template",
        "str",
        "Export",
    ),
    ConfigField(
        "default_layout_profile",
        "Layout-Profil",
        "enum",
        "Export",
        choices=_layout_profile_choices(),
    ),
    ConfigField(
        "default_linestretch",
        "Zeilenabstand",
        "float",
        "Export",
        minimum=0.8,
        maximum=2.5,
        step=0.05,
    ),
    ConfigField(
        "handbuch_pdf_format",
        "Handbuch-PDF-Format",
        "enum",
        "Export",
        choices=("typst", "pdf"),
    ),
    ConfigField(
        "abort_on_first_preflight_error",
        "Bei erstem Buch-Doktor-Fehler abbrechen",
        "bool",
        "Export",
    ),
    ConfigField(
        "abort_on_first_render_colon_warning",
        "Bei erstem Colon-Warnung abbrechen",
        "bool",
        "Export",
    ),
    ConfigField(
        "log_font_size",
        "Log-Schriftgröße",
        "int",
        "Log & Editor",
        minimum=8,
        maximum=28,
    ),
    ConfigField(
        "log_max_lines_default",
        "Log-Max. Zeilen",
        "int",
        "Log & Editor",
        minimum=50,
        maximum=50_000,
    ),
    ConfigField(
        "log_auto_clear_default",
        "Log beim Start leeren",
        "bool",
        "Log & Editor",
    ),
    ConfigField(
        "undo_max_depth",
        "Undo-Tiefe (0 = unbegrenzt)",
        "int",
        "Log & Editor",
        minimum=0,
        maximum=10_000,
    ),
    ConfigField(
        "skeleton_default_profile",
        "Skeleton-Profil",
        "str",
        "Skeleton",
    ),
    ConfigField(
        "skeleton_on_conflict",
        "Bei Konflikt",
        "enum",
        "Skeleton",
        choices=("ask", "skip", "replace"),
    ),
    ConfigField(
        "skeleton_populate_mode",
        "Populate-Modus",
        "enum",
        "Skeleton",
        choices=("all", "missing_only"),
    ),
    ConfigField(
        "frontmatter_update_mode",
        "Frontmatter-Update",
        "enum",
        "Skeleton",
        choices=("append_only", "overwrite"),
    ),
)


def _path_list_to_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if str(x).strip())
    return str(value or "")


class _PathRow(QWidget):
    """QLineEdit + Browse (Ordner oder Datei)."""

    def __init__(
        self,
        *,
        append: bool = False,
        tip: str = "",
        file_mode: bool = False,
        file_filter: str = "",
    ) -> None:
        super().__init__()
        self._append = append
        self._file_mode = file_mode
        self._file_filter = file_filter or "Alle Dateien (*)"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        if tip:
            self.edit.setToolTip(tip)
            self.edit.setPlaceholderText(tip)
        browse = QPushButton("Datei…" if file_mode else "Ordner…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.edit, stretch=1)
        row.addWidget(browse)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, value: str) -> None:  # noqa: N802 — Qt-API
        self.edit.setText(value)

    def _browse(self) -> None:
        start = self.edit.text().strip()
        if self._append and "," in start:
            start = start.split(",")[-1].strip()
        if start:
            try:
                p = Path(start)
                if p.is_file():
                    start = str(p.parent)
                elif not p.is_dir():
                    start = str(p.parent) if p.parent.is_dir() else ""
            except OSError:
                start = ""
        if self._file_mode:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "Datei wählen",
                start or "",
                self._file_filter,
            )
            if chosen:
                self.edit.setText(chosen)
            return
        chosen = QFileDialog.getExistingDirectory(self, "Ordner wählen", start or "")
        if not chosen:
            return
        if self._append:
            current = self.edit.text().strip()
            if current:
                self.edit.setText(f"{current}, {chosen}")
            else:
                self.edit.setText(chosen)
        else:
            self.edit.setText(chosen)


class AppConfigDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], config_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Studio-Konfiguration")
        self.setMinimumSize(640, 520)
        self.resize(720, 640)
        self.config_path = Path(config_path)
        try:
            self.data: dict[str, Any] = _app_config.read_config(self.config_path)
        except (OSError, TypeError, ValueError):
            self.data = dict(_app_config.DEFAULTS)

        self._widgets: dict[str, Any] = {}

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(12)

        groups: dict[str, QFormLayout] = {}
        for spec in FIELDS:
            if spec.group not in groups:
                box = QGroupBox(spec.group)
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                groups[spec.group] = form
                body_layout.addWidget(box)
            widget = self._build_widget(spec)
            self._widgets[spec.key] = widget
            groups[spec.group].addRow(f"{spec.label}:", widget)

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_widget(self, spec: ConfigField) -> QWidget:
        value = self.data.get(spec.key, _app_config.DEFAULTS.get(spec.key))
        if spec.kind == "path":
            row = _PathRow(append=False, tip=spec.tip)
            row.setText(str(value or ""))
            return row
        if spec.kind == "file":
            row = _PathRow(
                append=False,
                tip=spec.tip,
                file_mode=True,
                file_filter=spec.file_filter,
            )
            row.setText(str(value or ""))
            return row
        if spec.kind == "path_list":
            row = _PathRow(append=True, tip=spec.tip)
            row.setText(_path_list_to_text(value))
            return row
        if spec.kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(value))
            if spec.tip:
                w.setToolTip(spec.tip)
            return w
        if spec.kind == "enum":
            w = QComboBox()
            choices = list(spec.choices) or [str(value or "")]
            w.addItems(choices)
            current = str(value or "")
            if current and current not in choices:
                w.addItem(current)
            w.setCurrentText(current or (choices[0] if choices else ""))
            if spec.tip:
                w.setToolTip(spec.tip)
            return w
        if spec.kind == "int":
            w = QSpinBox()
            w.setRange(int(spec.minimum), int(spec.maximum))
            w.setValue(int(value if value is not None else 0))
            if spec.tip:
                w.setToolTip(spec.tip)
            return w
        if spec.kind == "float":
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setSingleStep(float(spec.step))
            w.setRange(float(spec.minimum), float(spec.maximum))
            w.setValue(float(value if value is not None else 1.0))
            if spec.tip:
                w.setToolTip(spec.tip)
            return w
        w = QLineEdit(str(value or ""))
        if spec.tip:
            w.setToolTip(spec.tip)
        return w

    def _read_widget(self, spec: ConfigField, widget: Any) -> Any:
        if spec.kind in ("path", "file"):
            return widget.text().strip()
        if spec.kind == "path_list":
            text = widget.text().strip()
            if spec.key == "content_root_path":
                # Ein Pfad als String belassen (Historie), mehrere als Liste.
                if "," in text:
                    return [p.strip() for p in text.split(",") if p.strip()]
                return text or "."
            if "," in text:
                return [p.strip() for p in text.split(",") if p.strip()]
            return [text] if text else []
        if spec.kind == "bool":
            return widget.isChecked()
        if spec.kind == "enum":
            return widget.currentText()
        if spec.kind == "int":
            return int(widget.value())
        if spec.kind == "float":
            return float(widget.value())
        return widget.text().strip()

    def _save(self) -> None:
        for spec in FIELDS:
            widget = self._widgets[spec.key]
            self.data[spec.key] = self._read_widget(spec, widget)
        try:
            _app_config.write_config(self.config_path, self.data)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self.accept()
