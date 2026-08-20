"""Breathcloud Qt dialog — Wortquelle wie Stylecloud, Verlauf per Farbdialog."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tools.breathcloud.engine import BreathcloudOptions, generate_breathcloud
from tools.breathcloud.session import load_session, resolve_ui_defaults, save_session
from tools.stylecloud.preset_store import load_preset
from tools.stylecloud.settings import load_settings as load_stylecloud_settings
from tools.stylecloud.text_sources import (
    collect_book_text,
    default_output_path,
    extract_markdown_body,
)


def _hex(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexRgb)


class _ColorSwatch(QToolButton):
    """Click → QColorDialog; shows current color as flat swatch."""

    colorChanged = Signal()

    def __init__(self, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Klicken zum Wählen der Verlaufsfarbe")
        self.clicked.connect(self._pick)
        self._paint()

    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self._paint()
        self.colorChanged.emit()

    def _paint(self) -> None:
        self.setStyleSheet(
            f"QToolButton {{ background-color: {_hex(self._color)}; "
            f"border: 1px solid #444; border-radius: 4px; }}"
        )

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(
            self._color, self.window(), "Verlaufsfarbe wählen"
        )
        if chosen.isValid():
            self.set_color(chosen)


class _Worker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str)
    finished_err = Signal(str)

    def __init__(self, options: BreathcloudOptions) -> None:
        super().__init__()
        self._options = options

    def run(self) -> None:
        try:
            path = generate_breathcloud(
                self._options,
                progress=lambda p, m: self.progress.emit(p, m),
            )
            self.finished_ok.emit(str(path))
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.finished_err.emit(str(exc))


class BreathcloudDialog(QDialog):
    """Organische Wolke: Kernwort + Buch/Datei-Quelle + Farbverlauf-Dialoge."""

    def __init__(
        self, studio: Any | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._studio = studio
        self.setWindowTitle("Breathcloud — organische Wortwolke")
        self.resize(960, 720)
        self._worker: _Worker | None = None
        self._last_png: Path | None = None

        # freeForm → only source/size/stopwords. Word count never from freeForm
        # (that was silently overwriting the user's „Wörter“ spinbox).
        preset: dict[str, Any] = {}
        try:
            preset = load_preset("freeForm")
        except (OSError, ValueError, FileNotFoundError):
            preset = {}
        try:
            style_session = load_stylecloud_settings()
        except (OSError, ValueError, TypeError):
            style_session = {}
        breath_session = load_session()
        ui = resolve_ui_defaults(
            freeform_preset=preset,
            style_session=style_session,
            breath_session=breath_session,
        )

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.source_combo = QComboBox()
        self.source_combo.addItem("Aktuelles Buch (content/*.md)", "book")
        self.source_combo.addItem("Textdatei…", "file")
        self.source_combo.addItem("Freitext", "paste")
        mode = str(ui["source_mode"] or "book")
        idx = self.source_combo.findData(mode)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        self.source_combo.currentIndexChanged.connect(self._on_source_mode)
        form.addRow("Textquelle:", self.source_combo)

        src_row = QHBoxLayout()
        self.source_path = QLineEdit(str(ui.get("source_path") or ""))
        self.source_path.setPlaceholderText("Pfad zur .txt / .md")
        self.btn_browse_source = QPushButton("Datei…")
        self.btn_browse_source.clicked.connect(self._browse_source)
        self.btn_load = QPushButton("Text laden")
        self.btn_load.clicked.connect(self._load_text)
        src_row.addWidget(self.source_path, 1)
        src_row.addWidget(self.btn_browse_source)
        src_row.addWidget(self.btn_load)
        form.addRow("Quelldatei:", src_row)

        self.hub = QLineEdit(str(ui.get("hub_word") or ""))
        self.hub.setPlaceholderText("Kernwort — die Wolke schart sich darum")
        form.addRow("Kernwort:", self.hub)

        grad_colors = list(ui.get("gradient") or ["#1e5f8a", "#2ec4b6", "#c8f542"])
        while len(grad_colors) < 3:
            grad_colors.append(grad_colors[-1] if grad_colors else "#888888")
        grad_row = QHBoxLayout()
        self.swatch_a = _ColorSwatch(QColor(str(grad_colors[0])))
        self.swatch_b = _ColorSwatch(QColor(str(grad_colors[1])))
        self.swatch_c = _ColorSwatch(QColor(str(grad_colors[2])))
        for sw in (self.swatch_a, self.swatch_b, self.swatch_c):
            sw.colorChanged.connect(self._update_gradient_preview)
            grad_row.addWidget(sw)
        self.gradient_preview = QLabel()
        self.gradient_preview.setFixedHeight(28)
        self.gradient_preview.setMinimumWidth(160)
        grad_row.addWidget(self.gradient_preview, 1)
        form.addRow("Farbverlauf:", grad_row)
        self._update_gradient_preview()

        size_row = QHBoxLayout()
        self.hub_size = QSpinBox()
        self.hub_size.setRange(40, 400)
        self.hub_size.setValue(int(ui["hub_font_size"]))
        self.max_font = QSpinBox()
        self.max_font.setRange(12, 200)
        self.max_font.setValue(int(ui["max_font_size"]))
        self.max_words = QSpinBox()
        self.max_words.setRange(20, 800)
        self.max_words.setValue(int(ui["max_words"]))
        self.max_words.setToolTip(
            "Maximale Begleitwörter — bleibt erhalten (nicht aus freeForm überschrieben)."
        )
        size_row.addWidget(QLabel("Kern-Schrift:"))
        size_row.addWidget(self.hub_size)
        size_row.addWidget(QLabel("Max:"))
        size_row.addWidget(self.max_font)
        size_row.addWidget(QLabel("Wörter:"))
        size_row.addWidget(self.max_words)
        form.addRow("Größen:", size_row)

        book = getattr(studio, "current_book", None) if studio else None
        out_default = str(ui.get("output_path") or "").strip() or str(
            default_output_path(
                Path(book) if book else None, filename="breathcloud.png"
            )
        )
        out_row = QHBoxLayout()
        self.output_path = QLineEdit(str(out_default))
        self.btn_browse_out = QPushButton("Speichern unter…")
        self.btn_browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.output_path, 1)
        out_row.addWidget(self.btn_browse_out)
        form.addRow("Ausgabe-PNG:", out_row)

        self.text = QTextEdit()
        self.text.setPlaceholderText(
            "Schlagwörter / Fließtext — „Text laden“ übernimmt Buch oder Datei "
            "(wie Cover-Schlagwortwolke / freeForm)."
        )
        self.text.setMinimumHeight(72)
        form.addRow("Text:", self.text)

        root.addLayout(form)

        btns = QHBoxLayout()
        self.btn_generate = QPushButton("Wolke erzeugen")
        self.btn_generate.clicked.connect(self._generate)
        btns.addWidget(self.btn_generate)
        self.btn_save = QPushButton("PNG speichern unter…")
        self.btn_save.clicked.connect(self._save_as)
        self.btn_save.setEnabled(False)
        btns.addWidget(self.btn_save)
        btns.addStretch(1)
        root.addLayout(btns)

        self.status = QLabel("Bereit — Textquelle wählen und laden.")
        root.addWidget(self.status)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(360)
        self.preview.setStyleSheet("background:#f4f4f4; border:1px solid #ccc;")
        root.addWidget(self.preview, stretch=1)

        self._use_stopwords = bool(ui.get("use_german_stopwords", True))
        size = ui.get("size") or [1594, 2539]
        try:
            self._export_side = max(int(size[0]), int(size[1]))
        except (TypeError, ValueError, IndexError):
            self._export_side = 2539

        self._on_source_mode()
        # Auto-load book text when studio has a book and source is book.
        if mode == "book" and book:
            try:
                self._load_text()
            except Exception:
                pass

    def _update_gradient_preview(self) -> None:
        a, b, c = (
            _hex(self.swatch_a.color()),
            _hex(self.swatch_b.color()),
            _hex(self.swatch_c.color()),
        )
        self.gradient_preview.setStyleSheet(
            f"border:1px solid #666; border-radius:4px; "
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            f"stop:0 {a}, stop:0.5 {b}, stop:1 {c});"
        )

    def _gradient_spec(self) -> str:
        return ",".join(
            [
                _hex(self.swatch_a.color()),
                _hex(self.swatch_b.color()),
                _hex(self.swatch_c.color()),
            ]
        )

    def _on_source_mode(self) -> None:
        mode = str(self.source_combo.currentData() or "book")
        is_file = mode == "file"
        is_paste = mode == "paste"
        self.source_path.setEnabled(is_file)
        self.btn_browse_source.setEnabled(is_file)
        self.btn_load.setEnabled(not is_paste)
        if is_paste:
            self.status.setText("Freitext-Modus — Text im Editor bearbeiten.")

    def _browse_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Textdatei wählen",
            "",
            "Text (*.txt *.md *.qmd *.csv);;Alle Dateien (*.*)",
        )
        if path:
            self.source_path.setText(path)
            self.source_combo.setCurrentIndex(self.source_combo.findData("file"))
            self._load_text()

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Ausgabe-PNG", self.output_path.text(), "PNG (*.png)"
        )
        if path:
            self.output_path.setText(path)

    def _resolve_text(self) -> str:
        mode = str(self.source_combo.currentData() or "book")
        if mode == "book":
            book = getattr(self._studio, "current_book", None) if self._studio else None
            if not book:
                raise ValueError("Bitte zuerst ein Buchprojekt öffnen.")
            text = collect_book_text(Path(book))
            if not text.strip():
                raise ValueError(
                    "Im Buchordner wurden keine nutzbaren Markdown-Texte gefunden."
                )
            return text
        if mode == "file":
            path = Path(self.source_path.text().strip())
            if not path.is_file():
                raise ValueError(f"Datei nicht gefunden:\n{path}")
            if path.suffix.lower() in {".md", ".qmd"}:
                return extract_markdown_body(path)
            return path.read_text(encoding="utf-8", errors="replace")
        # paste
        text = self.text.toPlainText().strip()
        if not text:
            raise ValueError("Bitte Freitext eingeben oder Textquelle auf Buch/Datei stellen.")
        return text

    def _load_text(self) -> None:
        try:
            mode = str(self.source_combo.currentData() or "book")
            if mode == "paste":
                self.status.setText("Freitext-Modus — Text im Editor bearbeiten.")
                return
            text = self._resolve_text()
            self.text.setPlainText(text)
            if mode == "book":
                book = getattr(self._studio, "current_book", None)
                name = Path(book).name if book else "Buch"
                self.status.setText(f"Buchtext geladen ({len(text)} Zeichen) aus {name}.")
            else:
                self.status.setText(
                    f"Datei geladen ({len(text)} Zeichen): {Path(self.source_path.text()).name}"
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Text laden", str(exc))

    def _generate(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        hub = self.hub.text().strip()
        if not hub:
            QMessageBox.warning(self, "Breathcloud", "Bitte ein Kernwort setzen.")
            return
        try:
            # Prefer editor contents if already loaded; else resolve from source.
            text = self.text.toPlainText().strip()
            if not text:
                text = self._resolve_text()
                self.text.setPlainText(text)
        except ValueError as exc:
            QMessageBox.warning(self, "Breathcloud", str(exc))
            return
        if not text.strip():
            QMessageBox.warning(self, "Breathcloud", "Kein Text — bitte Quelle laden.")
            return

        out = Path(self.output_path.text().strip() or "breathcloud_preview.png")
        options = BreathcloudOptions(
            text=text,
            hub_word=hub,
            output_path=out,
            hub_font_size=int(self.hub_size.value()),
            max_font_size=int(self.max_font.value()),
            max_words=int(self.max_words.value()),
            gradient=self._gradient_spec(),
            use_stopwords=self._use_stopwords,
            export_max_side=int(self._export_side),
            canvas_size=max(1200, int(self._export_side)),
        )
        self.btn_generate.setEnabled(False)
        self.status.setText("Erzeuge…")
        self._persist_session()
        self._worker = _Worker(options)
        self._worker.progress.connect(lambda p, m: self.status.setText(f"{p}% — {m}"))
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.finished_err.connect(self._on_err)
        self._worker.start()

    def _persist_session(self) -> None:
        """Keep Wörter / fonts / hub — never let freeForm clobber them next open."""
        try:
            save_session(
                {
                    "hub_word": self.hub.text().strip(),
                    "hub_font_size": int(self.hub_size.value()),
                    "max_font_size": int(self.max_font.value()),
                    "max_words": int(self.max_words.value()),
                    "gradient": [
                        _hex(self.swatch_a.color()),
                        _hex(self.swatch_b.color()),
                        _hex(self.swatch_c.color()),
                    ],
                    "output_path": self.output_path.text().strip(),
                }
            )
        except OSError:
            pass

    def _on_ok(self, path_str: str) -> None:
        self.btn_generate.setEnabled(True)
        path = Path(path_str)
        self._last_png = path
        self.btn_save.setEnabled(True)
        self._persist_session()
        pix = QPixmap(str(path))
        if not pix.isNull():
            self.preview.setPixmap(
                pix.scaled(
                    self.preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.status.setText(f"Fertig: {path}")

    def _on_err(self, message: str) -> None:
        self.btn_generate.setEnabled(True)
        QMessageBox.critical(self, "Breathcloud", message)
        self.status.setText("Fehler.")

    def _save_as(self) -> None:
        if self._last_png is None or not self._last_png.is_file():
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "PNG speichern", self.output_path.text() or "breathcloud.png", "PNG (*.png)"
        )
        if not target:
            return
        Path(target).write_bytes(self._last_png.read_bytes())
        self.output_path.setText(target)
        self.status.setText(f"Gespeichert: {target}")


def open_breathcloud_dialog(
    studio: Optional[Any] = None, parent: QWidget | None = None
) -> BreathcloudDialog:
    dlg = BreathcloudDialog(studio, parent)
    dlg.show()
    return dlg
