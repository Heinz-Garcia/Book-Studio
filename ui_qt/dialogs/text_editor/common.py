"""Gemeinsame Hilfen von ``ui_qt.dialogs.text_dialogs`` und seinen Mixins."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget,
)

from tools.live_preview.preview_render import PreviewRenderResult, render_single_chapter_preview


class _PdfPreviewWorker(QThread):
    """Rendert im Hintergrund-Thread — hält die UI währenddessen responsiv.

    Nutzt den Einzelkapitel-Kurzweg (temporäre Buch-Kopie mit gekürzter
    ``chapters:``-Liste, siehe ``render_single_chapter_preview``): ~1-2s
    statt ~8s+ bei einem Vollbuch-Render. Fällt für ``index.md`` und
    Aggregator-Seiten (z. B. IVZ.md mit ``#outline()``) automatisch auf den
    Vollbuch-Render zurück — dort kann diese Beschleunigung nicht greifen.
    """

    finished_ok = Signal(str, str)  # (pdf_path, cleanup_dir oder "")
    finished_err = Signal(str)

    def __init__(self, markdown_file: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._markdown_file = markdown_file

    def run(self) -> None:  # noqa: D102 - QThread-Override
        result: PreviewRenderResult = render_single_chapter_preview(self._markdown_file)
        if result.success and result.pdf_path is not None:
            cleanup_dir = str(result.cleanup_dir) if result.cleanup_dir is not None else ""
            self.finished_ok.emit(str(result.pdf_path), cleanup_dir)
        else:
            message = result.log_tail.strip() or f"Render fehlgeschlagen (rc={result.returncode})."
            self.finished_err.emit(message)


_TEXT_EMPHASIS_COMMANDS: tuple[tuple[str, str, str, str], ...] = (
    ("𝐁", "Fett (**Text**)", "**", "**"),
    ("𝐼", "Kursiv (*Text*)", "*", "*"),
    ("S̶", "Durchgestrichen (~~Text~~)", "~~", "~~"),
    ("x²", "Hochgestellt (^Text^)", "^", "^"),
    ("x₂", "Tiefgestellt (~Text~)", "~", "~"),
    ("</>", "Inline-Code (`Text`)", "`", "`"),
)


_ALIGNMENT_COMMANDS: tuple[tuple[str, str, str, str], ...] = (
    (
        "↔",
        "Zentrieren horizontal (Typst). Enthält die Auswahl ein Markdown-Bild, "
        "wird es nach #image(…, width: 80%) umgewandelt (Fence-Block).",
        "`#align(center)[",
        "]`{=typst}",
    ),
    (
        "↕↔",
        "Zentrieren horizontal + vertikal (Typst). Markdown-Bilder in der Auswahl "
        "werden automatisch nach #image(\"/img/…\", width: 80%) konvertiert — sonst Klartext im PDF.",
        "`#align(center + horizon)[",
        "]`{=typst}",
    ),
)


_SIZE_COMMANDS: tuple[tuple[str, str, str, str], ...] = (
    ("A+", "Text vergrößern (Typst: #text(size: 1.2em)[Text])", "`#text(size: 1.2em)[", "]`{=typst}"),
    ("A-", "Text verkleinern (Typst: #text(size: 0.85em)[Text])", "`#text(size: 0.85em)[", "]`{=typst}"),
)


_MATH_INLINE_COMMAND: tuple[str, str, str, str] = ("∑", "Mathe inline ($Formel$)", "$", "$")


_HEADING_COMMANDS: tuple[tuple[str, str, int], ...] = (
    ("H1", "Überschrift 1 (# Text)", 1),
    ("H2", "Überschrift 2 (## Text)", 2),
    ("H3", "Überschrift 3 (### Text)", 3),
)


_LINE_PREFIX_COMMANDS: tuple[tuple[str, str, Any], ...] = (
    ("❝", "Zitat (> Text)", lambda _i: "> "),
    ("•", "Aufzählungsliste (- Text)", lambda _i: "- "),
    ("1.", "Nummerierte Liste (1. Text)", lambda i: f"{i}. "),
)
