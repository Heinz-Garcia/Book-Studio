"""Ansichten: Code, Leservorschau und PDF-Vorschau.

Mixin von ``TextEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtPdf import QPdfDocument

from ui_qt.dialogs.text_editor.common import (
    _PdfPreviewWorker,
)
from ui_qt.markdown_preview import body_for_preview, markdown_to_preview_html


class PreviewMixin:
    """Ansichten: Code, Leservorschau und PDF-Vorschau."""

    def _ensure_code_view(self) -> None:
        """Wechselt in die Codeansicht, falls gerade die Leservorschau aktiv
        ist - Formatier-Buttons bearbeiten den Rohtext, nicht das gerenderte
        HTML der Vorschau."""
        if self._stack.currentWidget() is not self.editor:
            if hasattr(self, "_btn_code"):
                self._btn_code.setChecked(True)
            self._show_code()

    def _on_mode_changed(self, mode_id: int) -> None:
        if mode_id == 1:
            self._show_preview()
        elif mode_id == 2:
            self._show_pdf_preview()
        else:
            self._show_code()

    def _show_code(self) -> None:
        self._stack.setCurrentWidget(self.editor)
        for btn in self._end_command_buttons:
            btn.setEnabled(True)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._set_status("Codeansicht aktiv", "dim")

    def _show_preview(self) -> None:
        if self._preview_dirty:
            self._preview.setHtml(
                markdown_to_preview_html(
                    self.editor.toPlainText(),
                    book_root=self.book_path,
                    markdown_file=self.path,
                )
            )
            self._preview_dirty = False
        self._stack.setCurrentWidget(self._preview)
        for btn in self._end_command_buttons:
            btn.setEnabled(False)
        self._set_status("Leservorschau (Frontmatter/Seitenumbruch ausgeblendet)", "ok")

    def _show_pdf_preview(self) -> None:
        self._stack.setCurrentWidget(self._pdf_page)
        for btn in self._end_command_buttons:
            btn.setEnabled(False)
        if self._pdf_worker is not None and self._pdf_worker.isRunning():
            return
        if not self._pdf_preview_dirty and self._pdf_document.pageCount() > 0:
            self._set_status(
                "PDF-Vorschau (letzter Render-Stand, unverändert seit dem letzten Klick)", "dim"
            )
            return
        self._start_pdf_render()

    def _start_pdf_render(self) -> None:
        self._pdf_render_pending = True
        self._pdf_status_label.setVisible(True)
        self._pdf_status_label.setStyleSheet(
            "padding: 6px 10px; background:#fef3c7; color:#78350f;"
        )
        self._pdf_status_label.setText(
            "🔄 Rendert echte PDF-Vorschau (ganzes Buch, Quarto/Typst) — "
            "kann je nach Buchgröße mehrere Sekunden dauern…"
        )
        self._set_status("PDF-Vorschau wird gerendert…", "dim")
        self._btn_pdf_preview.setEnabled(False)
        worker = _PdfPreviewWorker(self.path, self)
        worker.finished_ok.connect(self._on_pdf_render_ok)
        worker.finished_err.connect(self._on_pdf_render_err)
        worker.finished.connect(self._on_pdf_worker_finished)
        self._pdf_worker = worker
        worker.start()

    def _on_pdf_worker_finished(self) -> None:
        self._pdf_render_pending = False
        self._btn_pdf_preview.setEnabled(True)

    def _on_pdf_render_ok(self, pdf_path: str, cleanup_dir: str) -> None:
        self._pdf_preview_dirty = False
        self._pdf_status_label.setVisible(False)
        note = (
            " (Einzelkapitel-Vorschau — Kapitelnummer/Seitenzahl weichen von der "
            "echten Position im Buch ab)"
            if cleanup_dir
            else ""
        )
        self._set_status(f"PDF-Vorschau: {pdf_path}{note}", "ok")
        self._pdf_document.load(pdf_path)
        # Alten Temp-Ordner erst NACH dem Nachladen der neuen PDF entfernen —
        # load() gibt die vorherige Datei frei, sonst würde Windows das
        # Löschen der noch offenen alten PDF verweigern.
        stale_dir = self._pdf_cleanup_dir
        self._pdf_cleanup_dir = Path(cleanup_dir) if cleanup_dir else None
        if stale_dir is not None:
            shutil.rmtree(stale_dir, ignore_errors=True)

    def _on_pdf_render_err(self, message: str) -> None:
        self._pdf_status_label.setStyleSheet(
            "padding: 6px 10px; background:#fee2e2; color:#7f1d1d;"
        )
        self._pdf_status_label.setText(f"⚠ PDF-Vorschau fehlgeschlagen:\n{message}")
        self._pdf_status_label.setVisible(True)
        self._set_status("PDF-Vorschau fehlgeschlagen", "error")

    def _on_pdf_document_status_changed(self, status: QPdfDocument.Status) -> None:
        if status != QPdfDocument.Status.Ready:
            return
        self._jump_to_matching_pdf_page()

    def _jump_to_matching_pdf_page(self) -> None:
        """Springt zur ersten PDF-Seite, die einen Textausschnitt der
        aktuellen Datei enthält — sonst müsste man im ganzen Buch-PDF
        manuell nach der eigenen Seite suchen."""
        snippet = self._distinctive_body_snippet()
        if not snippet:
            return
        page_count = self._pdf_document.pageCount()
        for page in range(page_count):
            selection = self._pdf_document.getAllText(page)
            page_text = re.sub(r"\s+", " ", selection.text() if selection else "")
            if snippet in page_text:
                self._pdf_view.pageNavigator().jump(page, QPointF(0, 0))
                return

    def _distinctive_body_snippet(self, *, min_len: int = 12) -> str:
        body = body_for_preview(self.editor.toPlainText())
        for line in body.splitlines():
            candidate = re.sub(r"\s+", " ", line).strip("# >*-\t ").strip()
            if len(candidate) >= min_len:
                return candidate[:80]
        return ""
