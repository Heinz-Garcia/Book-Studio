"""Quelltext laden, Wolke erzeugen (Worker), Ergebnis anzeigen, Übergabe an den KDP-Cover-Designer.

Mixin von ``StylecloudQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from tools.stylecloud.generator import (
    ICON_HUB,
    ICON_NONE,
    StylecloudOptions,
    format_file_size,
    resolve_pack_raw_path,
)
from tools.stylecloud.text_sources import collect_book_text
from ui_qt.dialogs.stylecloud.common import (
    _GenerateWorker,
    _set_combo_by_data,
    resolve_stylecloud_handoff_png,
)


class GenerateMixin:
    """Quelltext laden, Wolke erzeugen (Worker), Ergebnis anzeigen, Übergabe an den KDP-Cover-Designer."""

    def _log(self, msg: str, level: str = "info") -> None:
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(msg, level)

    def _on_source_changed(self) -> None:
        mode = self.source_combo.currentData()
        file_mode = mode == "file"
        self.source_path.setEnabled(file_mode)
        self.btn_browse_source.setEnabled(file_mode)

    def _browse_source(self) -> None:
        start = self.source_path.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Textdatei für Schlagwortwolke",
            start,
            "Text (*.txt *.md *.qmd *.csv);;Alle Dateien (*.*)",
        )
        if path:
            self.source_path.setText(path)
            self.source_combo.setCurrentIndex(self.source_combo.findData("file"))
            self._load_text()

    def _browse_output(self) -> None:
        start = self.output_path.text().strip() or str(Path.home() / "cover_stylecloud.png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Cover-Wolke speichern",
            start,
            "PNG (*.png)",
        )
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            self.output_path.setText(path)

    def _read_source_text(self) -> str:
        """Load text from the selected source (book / file / editor).

        Raises ``ValueError`` with a German message when nothing usable is found.
        """
        mode = self.source_combo.currentData()
        if mode == "book":
            book = getattr(self._studio, "current_book", None)
            if not book:
                raise ValueError("Bitte zuerst ein Buchprojekt öffnen.")
            text = collect_book_text(Path(book))
            if not text.strip():
                raise ValueError(
                    "Im Buchordner wurden keine nutzbaren Markdown-Texte gefunden."
                )
            return text
        if mode == "file":
            raw = self.source_path.text().strip()
            if not raw:
                raise ValueError("Bitte eine Quelldatei wählen.")
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Datei nicht gefunden:\n{path}")
            if path.suffix.lower() in {".md", ".qmd"}:
                from tools.stylecloud.text_sources import extract_markdown_body

                text = extract_markdown_body(path)
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                raise ValueError(f"Die Datei ist leer:\n{path}")
            return text
        # Freitext
        text = self.text_edit.toPlainText()
        if not text.strip():
            raise ValueError(
                "Kein Text für die Schlagwortwolke.\n"
                "Bitte Freitext eingeben oder Textquelle auf Buch/Datei stellen."
            )
        return text

    def _load_text(self) -> None:
        mode = self.source_combo.currentData()
        try:
            if mode == "paste":
                self.status.setText("Freitext-Modus — Text im Editor bearbeiten.")
                return
            text = self._read_source_text()
            self.text_edit.setPlainText(text)
            if mode == "book":
                book = getattr(self._studio, "current_book", None)
                name = Path(book).name if book else "?"
                self.status.setText(
                    f"Buchtext geladen ({len(text)} Zeichen) aus {name}."
                )
                self._log(f"[stylecloud] Buchtext geladen: {name}")
            else:
                path = Path(self.source_path.text().strip()).expanduser()
                self.status.setText(
                    f"Datei geladen: {path.name} ({len(text)} Zeichen)."
                )
                self._log(f"[stylecloud] Datei geladen: {path}")
        except ValueError as exc:
            QMessageBox.warning(self, "Text laden", str(exc))
        except OSError as exc:
            QMessageBox.critical(self, "Lesen fehlgeschlagen", str(exc))

    def _build_options(self) -> StylecloudOptions:
        size = self._resolved_size()
        out = self.output_path.text().strip()
        if not out:
            raise ValueError("Bitte einen Ausgabe-Pfad angeben.")
        text = self.text_edit.toPlainText().strip()
        if not text:
            # Auto-load from book/file so "Wolke erzeugen" works without
            # an extra "Text laden" click after choosing a source file.
            mode = self.source_combo.currentData()
            if mode in ("book", "file"):
                text = self._read_source_text().strip()
                self.text_edit.setPlainText(text)
            elif mode == "paste":
                # Recover: Freitext leer, aber Quelldatei-Pfad noch gesetzt.
                raw = self.source_path.text().strip()
                if raw:
                    path = Path(raw).expanduser().resolve()
                    if path.is_file():
                        if path.suffix.lower() in {".md", ".qmd"}:
                            from tools.stylecloud.text_sources import extract_markdown_body

                            text = extract_markdown_body(path).strip()
                        else:
                            text = path.read_text(
                                encoding="utf-8", errors="replace"
                            ).strip()
                        if text:
                            self.text_edit.setPlainText(text)
                            self.source_combo.blockSignals(True)
                            _set_combo_by_data(self.source_combo, "file")
                            self.source_combo.blockSignals(False)
                            self.status.setText(
                                f"Leerer Freitext — Quelldatei geladen: {path.name}"
                            )
        if not text:
            has_must = bool(
                self.must_word.text().strip() or self.must_word_line2.text().strip()
            )
            is_hub = (
                self._resolved_icon_name() == ICON_HUB
                and not self.mask_path.text().strip()
            )
            if is_hub or not has_must:
                raise ValueError(
                    "Kein Text für die Schlagwortwolke.\n"
                    "Bitte Text laden (Buch/Datei) oder einfügen.\n"
                    + (
                        "Freie Form braucht Begleitwörter zusätzlich zum Kernwort."
                        if is_hub
                        else "Tipp: Mit Muss-Wort allein (ohne Freie Form) geht’s auch."
                    )
                )
            # Non-hub + Muss-Wort: blank canvas + overlay (generator path).
        icon_name = self._resolved_icon_name()
        return StylecloudOptions(
            text=text,
            output_path=Path(out),
            size=size if size is not None else 1024,
            icon_name=icon_name,
            mask_path=(
                Path(self.mask_path.text().strip())
                if self.mask_path.text().strip()
                else None
            ),
            free_form_margin_pct=float(self.free_form_margin.value()),
            free_form_density=self._resolved_free_form_density(),
            free_form_packing=self._resolved_free_form_packing(),
            word_density=self._resolved_word_density(),
            free_form_prefer_horizontal=self._resolved_prefer_horizontal(),
            palette=str(
                self.palette_combo.currentData() or "cartocolors.qualitative.Bold_5"
            ),
            background_color=self.bg_edit.text().strip() or "white",
            max_colors=int(self.max_colors.value()),
            gradient=(
                self.gradient_combo.currentData()
                if self._uses_font_awesome() and self._canvas_is_square()
                else None
            ),
            hub_gradient=self._hub_gradient_stops(),
            max_font_size=int(self.max_font.value()),
            max_words=int(self.max_words.value()),
            use_german_stopwords=self.german_stop.isChecked(),
            extra_stopwords=self.extra_stop.text(),
            nouns_only=self.nouns_only.isChecked(),
            collocations=self.collocations.isChecked(),
            invert_mask=self.invert_mask.isChecked(),
            random_state=int(getattr(self, "_layout_seed", 42)),
            must_word=self.must_word.text().strip(),
            must_word_line2=self.must_word_line2.text().strip(),
            must_word_font_size=int(self.must_word_size.value()),
            must_word_color=self.must_word_color.text().strip() or "#c0392b",
            must_word_angle=int(self.must_word_angle.currentData() or 0),
            must_word_gap=int(self.must_word_gap.value()),
            must_word_match_line1_width=self.must_word_match_width.isChecked(),
            auto_fit=bool(self.auto_fit.isChecked()),
            cover_scale=float(self._cover_scale),
            save_svg=bool(self.save_svg.isChecked()),
            png_compress_level=int(self.png_compress.value()),
            png_optimize=self.png_optimize.isChecked(),
            png_dpi=int(self.png_dpi.value()),
        )

    def _generate(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not hasattr(self, "_layout_seed"):
            self._layout_seed = 42
        self._generation_max_font_size = int(self.max_font.value())
        self._is_generating = True
        try:
            options = self._build_options()
        except ValueError as exc:
            self._is_generating = False
            self._generation_max_font_size = None
            QMessageBox.warning(self, "Eingabe", str(exc))
            return

        self._set_busy(True)
        self.progress.setValue(0)
        self.progress.setFormat("Start…")
        self.status.setText("Erzeuge Schlagwortwolke…")

        worker = _GenerateWorker(options, self)
        self._worker = worker
        worker.progress.connect(self._on_generate_progress)
        worker.succeeded.connect(self._on_generate_succeeded)
        worker.failed.connect(self._on_generate_failed)
        worker.finished.connect(self._on_generate_finished)
        worker.start()

    def _preserve_generation_font(self, value: int) -> None:
        """Reject stale UI updates while a generation is using this font size."""
        expected = self._generation_max_font_size
        if not self._is_generating or expected is None or int(value) == expected:
            return
        self.max_font.blockSignals(True)
        self.max_font.setValue(expected)
        self.max_font.blockSignals(False)

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.btn_generate.setEnabled(not busy)
        self.btn_reset.setEnabled(not busy)
        self.btn_open.setEnabled(not busy)
        self.btn_handoff_kdp.setEnabled(False if busy else bool(self._resolve_handoff_png()))
        self.btn_close.setEnabled(not busy)
        self.btn_preset_load.setEnabled(not busy and self.preset_combo.count() > 1)
        self.btn_preset_save.setEnabled(not busy)
        self.btn_preset_manage.setEnabled(not busy)
        self.btn_factory_freeform.setEnabled(not busy)
        self.preset_combo.setEnabled(not busy)
        self.max_font.setEnabled(not busy)
        self.hub_orient_slider.setEnabled(not busy)
        self.word_density_slider.setEnabled(not busy)
        # ± usable when a packed raw sidecar exists and we are idle.
        if busy:
            self._set_hub_fit_enabled(False)
            self.free_form_packing.setEnabled(False)
        else:
            is_cover = (
                not self.mask_path.text().strip()
                and self._resolved_icon_name() == ICON_NONE
            )
            self.free_form_packing.setEnabled(bool(is_cover))
            self._set_hub_fit_enabled(bool(self._hub_raw_path))
            # Restore Auto-Fit lock on Schrift (busy path enables max_font).
            self._on_auto_fit_toggled(self.auto_fit.isChecked())

    def _reshuffle_generate(self) -> None:
        """Same settings, new random layout — does not wipe the form or Schrift."""
        if self._worker is not None and self._worker.isRunning():
            return
        import random

        self._layout_seed = random.randint(1, 2_147_483_647)
        self._generate()

    def _on_generate_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(int(percent))
        self.progress.setFormat(f"{int(percent)}% — {message}")
        self.status.setText(message)

    def _on_generate_succeeded(self, path: object) -> None:
        out = Path(str(path))
        meta = ""
        try:
            from PIL import Image

            with Image.open(out) as img:
                w, h = img.size
                dpi = img.info.get("dpi") or (self.png_dpi.value(), self.png_dpi.value())
                dpi_x = int(round(float(dpi[0]))) if dpi else int(self.png_dpi.value())
            meta = f" · {w}×{h} px · {dpi_x} dpi · {format_file_size(out.stat().st_size)}"
        except OSError:
            try:
                meta = f" · {format_file_size(out.stat().st_size)}"
            except OSError:
                meta = ""
        self.status.setText(f"Gespeichert: {out}{meta}")
        self._log(f"[stylecloud] Cover-Wolke erzeugt: {out}{meta}", "success")
        svg = out.with_suffix(".svg")
        if self.save_svg.isChecked() and svg.is_file():
            self.status.setText(f"Gespeichert: {out}{meta} · SVG: {svg.name}")
            self._log(f"[stylecloud] SVG: {svg}", "success")
        # Persist exactly the Schrift the user has set — never invent a value.
        self._user_font_size = int(self.max_font.value())
        self._last_output_path = out
        raw = resolve_pack_raw_path(out, prefer_hub=self._prefer_hub_raw())
        self._hub_raw_path = raw
        self._set_hub_fit_enabled(bool(self._hub_raw_path))
        self.btn_handoff_kdp.setEnabled(True)
        self._persist_settings()
        pix = QPixmap(str(out))
        if not pix.isNull():
            self._preview_pixmap = pix
            self._refresh_preview_pixmap()
        else:
            self._preview_pixmap = None
            self.preview.setText(f"Datei erzeugt:\n{out}")

    def _on_generate_failed(self, kind: str, message: str) -> None:
        titles = {
            "dependency": "stylecloud fehlt",
            "spacy": "spaCy fehlt",
            "value": "Eingabe",
            "os": "Erzeugung fehlgeschlagen",
            "runtime": "Erzeugung fehlgeschlagen",
        }
        title = titles.get(kind, "Fehler")
        if kind == "value":
            QMessageBox.warning(self, title, message)
        else:
            QMessageBox.critical(self, title, message)
            self._log(f"[stylecloud] Fehler: {message}", "error")
        self.status.setText(message)

    def _on_generate_finished(self) -> None:
        self._is_generating = False
        self._generation_max_font_size = None
        self._set_busy(False)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self._worker = None

    def _open_folder(self) -> None:
        raw = self.output_path.text().strip()
        if not raw:
            return
        folder = Path(raw).expanduser().resolve().parent
        if not folder.is_dir():
            QMessageBox.information(self, "Ordner", f"Ordner existiert noch nicht:\n{folder}")
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _resolve_handoff_png(self) -> Path | None:
        return resolve_stylecloud_handoff_png(
            last_output=self._last_output_path,
            output_field=self.output_path.text().strip(),
        )

    def _update_handoff_button(self) -> None:
        if self._is_generating:
            self.btn_handoff_kdp.setEnabled(False)
            return
        self.btn_handoff_kdp.setEnabled(bool(self._resolve_handoff_png()))

    def _handoff_to_kdp_cover(self) -> None:
        png = self._resolve_handoff_png()
        if png is None:
            QMessageBox.warning(
                self,
                "KDP Cover",
                "Keine Ausgabe-PNG gefunden.\n"
                "Bitte zuerst eine Schlagwortwolke erzeugen.",
            )
            return
        from ui_qt.dialogs.kdp_cover_dialog import open_kdp_cover_qt

        self.status.setText(f"Übergabe an KDP Cover: {png.name}")
        self._log(f"[stylecloud] An KDP Cover übergeben: {png}", "success")
        # Parent = Studio-Hauptfenster (nicht Stylecloud), vermeidet Nested-Modal-Probleme.
        parent = getattr(self._studio, "root", None) or self.window() or self
        open_kdp_cover_qt(
            self._studio,
            parent=parent,
            front_image=png,
            disable_compose=False,
        )

    def _refresh_preview_pixmap(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        self.preview.setPixmap(
            self._preview_pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
