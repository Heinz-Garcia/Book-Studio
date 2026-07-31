"""Dialog zum Auswählen und Einfügen eines Bildes in Markdown oder Typst."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ui_qt.editor_image import (
    DEFAULT_TYPST_IMAGE_WIDTH,
    IMAGE_FILTER,
    build_image_markdown_snippet,
    build_image_typst_snippet,
    import_image_for_markdown,
    normalize_typst_width,
    suggested_image_start_dir,
)


class InsertImageDialog(QDialog):
    """Datei wählen, Alt-Text / Ausgabeformat, Vorschau — liefert Snippet."""

    def __init__(
        self,
        parent=None,
        *,
        book_root: Path,
        start_dir: Path | str | None = None,
        default_alt: str = "",
        default_format: str = "markdown",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bild einfügen")
        self.setMinimumWidth(460)
        self._book_root = Path(book_root)
        self._start_dir = Path(start_dir) if start_dir else suggested_image_start_dir(self._book_root)
        self._source: Path | None = None
        self._markdown_ref: str | None = None

        layout = QVBoxLayout(self)

        file_row = QHBoxLayout()
        self._path_label = QLabel("Noch keine Datei gewählt.")
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: #64748b;")
        file_row.addWidget(self._path_label, stretch=1)
        choose_btn = QPushButton("Datei wählen…")
        choose_btn.clicked.connect(self._choose_file)
        file_row.addWidget(choose_btn)
        layout.addLayout(file_row)

        self._preview = QLabel("Vorschau")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(160)
        self._preview.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; color: #94a3b8;"
        )
        layout.addWidget(self._preview)

        form = QFormLayout()
        self._alt_edit = QLineEdit(default_alt.strip())
        self._alt_edit.setPlaceholderText("Alternativtext (Barrierefreiheit)")
        form.addRow("Alt-Text:", self._alt_edit)

        self._format = QComboBox()
        self._format.addItem("Markdown  ![…](/img/…)", "markdown")
        self._format.addItem('Typst  #image("/img/…", width: …%)  (zentriert)', "typst")
        idx = self._format.findData(default_format)
        self._format.setCurrentIndex(idx if idx >= 0 else 0)
        self._format.setToolTip(
            "Typst wählen für Deckblatt/Rückseite/Zentrierung. "
            "Markdown-Bilder in Typst-Raw-Blöcken erscheinen sonst als Klartext."
        )
        self._format.currentIndexChanged.connect(self._sync_width_enabled)
        form.addRow("Einfügen als:", self._format)

        width_row = QHBoxLayout()
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 100)
        default_pct = int(normalize_typst_width(DEFAULT_TYPST_IMAGE_WIDTH).rstrip("%") or "80")
        self._width_spin.setValue(default_pct)
        self._width_spin.setSuffix(" %")
        self._width_spin.setToolTip(
            "Breite für Typst-#image (width: …%). Beim Zentrieren von Markdown-Bildern "
            f"wird ebenfalls standardmäßig {DEFAULT_TYPST_IMAGE_WIDTH} gesetzt."
        )
        width_row.addWidget(self._width_spin)
        width_row.addStretch(1)
        form.addRow("Breite (Typst):", width_row)
        layout.addLayout(form)
        self._sync_width_enabled()

        hint = QLabel(
            "Bilder werden bei Bedarf nach img/ kopiert (/img/…). "
            "Für Ausrichtung (↔ / ↕↔) Markdown-Bild markieren und zentrieren — "
            "der Editor wandelt automatisch nach #image(…, width: …%) um."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)
        self._ok_button.setText("Einfügen")
        buttons.accepted.connect(self._accept_if_ready)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def markdown_snippet(self) -> str:
        """Rückwärtskompatibel: liefert das gewählte Snippet (MD oder Typst)."""
        return self.snippet()

    def snippet(self) -> str:
        if not self._markdown_ref:
            return ""
        kind = self._format.currentData()
        if kind == "typst":
            width = normalize_typst_width(self._width_spin.value())
            return build_image_typst_snippet(
                self._markdown_ref,
                width=width,
                center_horizon=True,
            )
        return build_image_markdown_snippet(self._alt_edit.text(), self._markdown_ref)

    def _sync_width_enabled(self) -> None:
        is_typst = self._format.currentData() == "typst"
        self._width_spin.setEnabled(is_typst)

    def _choose_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Bild auswählen",
            str(self._start_dir),
            IMAGE_FILTER,
        )
        if not path_str:
            return
        source = Path(path_str)
        try:
            markdown_ref, dest = import_image_for_markdown(source, self._book_root)
        except OSError as exc:
            QMessageBox.warning(self, "Bild einfügen", f"Datei konnte nicht übernommen werden:\n{exc}")
            return

        self._source = dest
        self._markdown_ref = markdown_ref
        self._path_label.setText(str(dest))
        self._path_label.setStyleSheet("color: #1a1d23;")
        if not self._alt_edit.text().strip():
            self._alt_edit.setText(source.stem)
        self._update_preview(dest)
        self._ok_button.setEnabled(True)

    def _update_preview(self, image_path: Path) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self._preview.setText("Vorschau nicht verfügbar")
            self._preview.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            420,
            220,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)
        self._preview.setText("")

    def _accept_if_ready(self) -> None:
        if self._markdown_ref:
            self.accept()
