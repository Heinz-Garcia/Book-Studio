"""Read-only Preview-Dialoge und einfache Text-/JSON-Editoren."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ui_qt import markdown_formatting
from ui_qt.end_commands import DEFAULT_PAGEBREAK_COMMAND, insert_end_command_text
from ui_qt.markdown_preview import body_for_preview, markdown_to_preview_html

# Eigenständiges Tool (tools/live_preview) — kein PySide6-Import dort, damit
# die Render-Logik ohne GUI testbar/aufrufbar bleibt (siehe dortiger Modul-
# Docstring). Diese Datei ruft nur render_single_chapter_preview() auf und
# zeigt das Ergebnis an.
from tools.live_preview.preview_render import PreviewRenderResult, render_single_chapter_preview


_BLANK_PDF_BYTES = b"%PDF-1.4\n%%EOF"


def _blank_pdf_path() -> Path:
    """Minimaler Platzhalter-PDF-Pfad, um ``QPdfDocument`` zum Freigeben der
    vorher geladenen Datei zu zwingen (siehe ``TextEditorDialog.closeEvent``).

    Empirisch geprüft: ``QPdfDocument.close()`` allein gibt eine unter
    Windows offene PDF-Datei NICHT zuverlässig frei (Sperre bleibt bestehen,
    ``shutil.rmtree`` schlägt fehl) — auch nicht mit ``deleteLater()`` +
    ``processEvents()`` + ``gc.collect()``. Erst das Laden eines ANDEREN,
    tatsächlich existierenden Pfads (auch wenn dessen Inhalt ungültig ist
    und der Ladevorgang selbst mit ``Status.Error`` endet) löst die Sperre.
    Ein nicht existierender Pfad reicht nachweislich NICHT.
    """
    path = Path(tempfile.gettempdir()) / "book_studio_pdf_preview_blank.pdf"
    if not path.is_file():
        path.write_bytes(_BLANK_PDF_BYTES)
    return path


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

# Alle folgenden (Icon, Tooltip, Marker davor, Marker danach)-Tupel wickeln die
# Auswahl ein bzw. fügen bei leerer Auswahl einen selektierten Platzhalter ein
# (siehe `_wrap_selection`). Sieben klar getrennte Gruppen (je eigener
# Toolbar-Abschnitt), damit man bei so vielen Buttons noch durchblickt:
# Textformatierung -> Ausrichtung -> Schriftgröße -> Mathe -> Überschriften ->
# Listen/Zitat -> Einfügen.

_TEXT_EMPHASIS_COMMANDS: tuple[tuple[str, str, str, str], ...] = (
    ("𝐁", "Fett (**Text**)", "**", "**"),
    ("𝐼", "Kursiv (*Text*)", "*", "*"),
    ("S̶", "Durchgestrichen (~~Text~~)", "~~", "~~"),
    ("x²", "Hochgestellt (^Text^)", "^", "^"),
    ("x₂", "Tiefgestellt (~Text~)", "~", "~"),
    ("</>", "Inline-Code (`Text`)", "`", "`"),
)

# Typst-Raw-Passthrough (`center`/`horizon`): Pandoc-Markdown kennt keine
# Ausrichtung nativ, das ist reine Typst-Fähigkeit.
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

# Ebenfalls Typst-Raw-Passthrough: `em` ist relativ zur aktuellen Schriftgröße,
# funktioniert also unabhängig davon, welche Basisgröße gerade gilt.
_SIZE_COMMANDS: tuple[tuple[str, str, str, str], ...] = (
    ("A+", "Text vergrößern (Typst: #text(size: 1.2em)[Text])", "`#text(size: 1.2em)[", "]`{=typst}"),
    ("A-", "Text verkleinern (Typst: #text(size: 0.85em)[Text])", "`#text(size: 0.85em)[", "]`{=typst}"),
)

_MATH_INLINE_COMMAND: tuple[str, str, str, str] = ("∑", "Mathe inline ($Formel$)", "$", "$")

# (Icon, Tooltip, Überschrift-Ebene)
_HEADING_COMMANDS: tuple[tuple[str, str, int], ...] = (
    ("H1", "Überschrift 1 (# Text)", 1),
    ("H2", "Überschrift 2 (## Text)", 2),
    ("H3", "Überschrift 3 (### Text)", 3),
)

# (Icon, Tooltip, Marker-Fabrik pro Zeilenindex)
_LINE_PREFIX_COMMANDS: tuple[tuple[str, str, Any], ...] = (
    ("❝", "Zitat (> Text)", lambda _i: "> "),
    ("•", "Aufzählungsliste (- Text)", lambda _i: "- "),
    ("1.", "Nummerierte Liste (1. Text)", lambda i: f"{i}. "),
)


class PreviewDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        text: str,
        *,
        title: str = "Preview",
        banner: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 560)
        layout = QVBoxLayout(self)
        if banner:
            note = QLabel(banner)
            note.setWordWrap(True)
            note.setObjectName("previewBanner")
            note.setStyleSheet(
                "QLabel#previewBanner {"
                " background-color: #fff4d6;"
                " color: #5c4a00;"
                " border: 1px solid #e0c56a;"
                " border-radius: 4px;"
                " padding: 8px 10px;"
                "}"
            )
            layout.addWidget(note)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        font = view.font()
        font.setFamily("Consolas")
        font.setStyleHint(font.StyleHint.Monospace)
        font.setPointSize(max(10, font.pointSize()))
        view.setFont(font)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


class TextEditorDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        path: Path,
        *,
        title: str = "Editor",
        end_commands: Optional[Sequence[dict[str, Any]]] = None,
        on_save: Optional[Callable[[], None]] = None,
        initial_line: Optional[int] = None,
        book_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.book_path = Path(book_path) if book_path else None
        self._on_save = on_save
        self._pending_skeleton_command: Optional[dict[str, Any]] = None
        self._is_markdown = self.path.suffix.lower() == ".md"
        self._preview_dirty = True
        self._pdf_preview_dirty = True
        self.setWindowTitle(f"{title} — {self.path.name}")
        self.resize(1500, 720)
        layout = QVBoxLayout(self)

        # Zwei Zeilen statt einer: die volle Formatier-Toolbar braucht in einer
        # einzigen Zeile ~2300px, weit über eine praktikable Dialogbreite hinaus
        # (und QToolBar würde den Rest sonst hinter einem "»"-Overflow-Button
        # verstecken). Zeile 1: Ansicht/Seite + Text-Format/Ausrichtung/Größe/
        # Mathe. Zeile 2: Struktur (Überschrift/Listen/Einfügen) + Umbruch/Ende/Verlauf.
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar QPushButton { font-size: 13px; }")
        layout.addWidget(toolbar)

        toolbar2 = QToolBar()
        toolbar2.setMovable(False)
        toolbar2.setStyleSheet("QToolBar QPushButton { font-size: 13px; }")
        layout.addWidget(toolbar2)

        if self._is_markdown:
            self._add_toolbar_group_label(toolbar, "Ansicht")
            self._mode_group = QButtonGroup(self)
            self._btn_code = QPushButton("📝")
            self._btn_code.setToolTip("Codeansicht (Rohtext bearbeiten)")
            self._btn_preview = QPushButton("👁️")
            self._btn_preview.setToolTip(
                "Leservorschau (gerendert; Frontmatter/Seitenumbruch ausgeblendet)"
            )
            self._btn_pdf_preview = QPushButton("🖨️")
            self._btn_pdf_preview.setToolTip(
                "Echte PDF-Vorschau: rendert nur diese Datei in einer temporären "
                "Buch-Kopie (wie beim finalen Export, aber ~1-2s statt mehrerer "
                "Sekunden für's ganze Buch).\n"
                "Kapitelnummer/Seitenzahl weichen dabei von der echten Position "
                "im Buch ab. Aggregator-Seiten (z. B. IVZ.md) und index.md "
                "rendern automatisch das ganze Buch."
            )
            for btn in (self._btn_code, self._btn_preview, self._btn_pdf_preview):
                btn.setCheckable(True)
                btn.setFixedWidth(40)
                toolbar.addWidget(btn)
            self._mode_group.addButton(self._btn_code, 0)
            self._mode_group.addButton(self._btn_preview, 1)
            self._mode_group.addButton(self._btn_pdf_preview, 2)
            self._btn_code.setChecked(True)
            self._mode_group.idClicked.connect(self._on_mode_changed)
            toolbar.addSeparator()

            self._add_toolbar_group_label(toolbar, "YAML")
            self._yaml_toggle_buttons: dict[str, QPushButton] = {}
            self._yaml_toggle_keys_sig: tuple[str, ...] = ()
            self._yaml_toggle_host = QWidget()
            self._yaml_toggle_layout = QHBoxLayout(self._yaml_toggle_host)
            self._yaml_toggle_layout.setContentsMargins(0, 0, 0, 0)
            self._yaml_toggle_layout.setSpacing(2)
            toolbar.addWidget(self._yaml_toggle_host)
            # Buttons erst nach Editor-Erzeugung (_rebuild_yaml_toggles).

            toolbar.addSeparator()
            self._add_toolbar_group_label(toolbar, "Inhalt")
            self._btn_gg = QPushButton("🧬")
            self._btn_gg.setCheckable(False)
            self._btn_gg.setFlat(False)
            self._btn_gg.setFixedWidth(40)
            self._btn_gg.setToolTip(
                "GrammarGraph-Inhalt aktualisieren…\n"
                "Anderen GG-Export wählen und Nutzinhalt (Body) tauschen."
            )
            self._btn_gg.clicked.connect(self._open_gg_swap)
            toolbar.addWidget(self._btn_gg)

            toolbar.addSeparator()
            self._add_toolbar_group_label(toolbar, "Cover")
            self._btn_kdp_cover = QPushButton("KDP-Wrap…")
            self._btn_kdp_cover.setCheckable(False)
            self._btn_kdp_cover.setToolTip(
                "KDP-Wrap (separat) — Upload-Cover-PDF "
                "(Rückseite + Rücken + Vorderseite inkl. Bleed).\n"
                "Unabhängig von Deckblatt.md / Innenwerk; ändert diese Datei nicht."
            )
            self._btn_kdp_cover.clicked.connect(self._open_kdp_cover)
            toolbar.addWidget(self._btn_kdp_cover)

            self._btn_skeleton_sync: Optional[QPushButton] = None
            if self._find_skeleton_sync_targets():
                self._btn_skeleton_sync = QPushButton("🧩")
                self._btn_skeleton_sync.setCheckable(False)
                self._btn_skeleton_sync.setFixedWidth(40)
                # Auffaelliger Hintergrund statt nur Emoji-Eigenfarbe: der
                # Button existiert NUR, wenn eine gleichnamige Skeleton-Datei
                # gefunden wurde (kein "sichtbar aber deaktiviert"-Zustand) -
                # das muss auf den ersten Blick als "aktiv/klickbar" erkennbar
                # sein, nicht wie ein ausgegrautes Icon wirken. Kein border/
                # border-radius (liess den Button trotz gleicher fixedWidth
                # optisch groesser/breiter als die Nachbar-Icons wirken) -
                # nur ein dezenter Farbton, sonst identisches Erscheinungsbild.
                self._btn_skeleton_sync.setStyleSheet(
                    "QPushButton { background-color: #e0ecff; }"
                    "QPushButton:hover { background-color: #cfe0ff; }"
                    "QPushButton:pressed { background-color: #b9d3fb; }"
                )
                self._btn_skeleton_sync.setToolTip(
                    "Mit Skeleton-Pool abgleichen…\n"
                    "Zeigt Buchdatei und gleichnamige Pool-Vorlage side by side — "
                    "manuell markieren/kopieren, dann speichern.\n"
                    "„standard“ ist ausgenommen und bleibt unverändert."
                )
                self._btn_skeleton_sync.clicked.connect(self._open_skeleton_sync)
                toolbar.addWidget(self._btn_skeleton_sync)
            toolbar.addSeparator()

            self._build_formatting_toolbar_row1(toolbar)

            self._build_formatting_toolbar_row2(toolbar2)
            toolbar2.addSeparator()

            self._add_toolbar_group_label(toolbar2, "Umbruch")
            self._btn_linebreak = QPushButton("\\")
            self._btn_linebreak.setToolTip(
                "Harter Zeilenumbruch: fügt einen Backslash „\\“ am Ende der aktuellen "
                "Zeile ein.\nPandocs eigene Hard-Break-Syntax - wird beim Rendern (auch "
                "nach Typst/PDF) in einen echten Zeilenumbruch übersetzt.\nHTML <br> "
                "funktioniert hier NICHT: Pandoc verwirft rohes HTML bei Nicht-HTML-Zielen."
            )
            self._btn_linebreak.setFixedWidth(32)
            self._btn_linebreak.clicked.connect(self._insert_hard_line_break)
            toolbar2.addWidget(self._btn_linebreak)
            toolbar2.addSeparator()
        else:
            self._yaml_toggle_buttons = {}
            self._yaml_toggle_keys_sig = ()
            self._yaml_toggle_host = None
            self._btn_gg = None

        commands = list(end_commands) if end_commands is not None else []
        if not commands and self._is_markdown:
            commands = self._load_end_commands_from_config()
        if not commands and self._is_markdown:
            commands = [DEFAULT_PAGEBREAK_COMMAND]

        if commands and self._is_markdown:
            self._add_toolbar_group_label(toolbar2, "Ende")
        self._end_command_buttons: list[QPushButton] = []
        for command in commands:
            label = str(command.get("label") or "End-Befehl")
            btn = QPushButton("⏭️")
            btn.setFixedWidth(40)
            btn.setToolTip(f"{label}\nFügt den Befehl automatisch ans Dateiende ein.")
            btn.clicked.connect(lambda _checked=False, cmd=command: self._insert_end_command(cmd))
            toolbar2.addWidget(btn)
            self._end_command_buttons.append(btn)

        if self._is_markdown:
            toolbar2.addSeparator()
            self._add_toolbar_group_label(toolbar2, "Suche")
            btn_find = QPushButton("🔍")
            btn_find.setFixedWidth(34)
            btn_find.setToolTip("Suchen (Strg+F) - Enter: nächster Treffer, Esc: schließen")
            btn_find.clicked.connect(self._show_find_bar)
            toolbar2.addWidget(btn_find)

            # Verlauf bleibt bewusst die LETZTE Gruppe (Undo/Redo als letzte 2 Buttons).
            toolbar2.addSeparator()
            self._add_toolbar_group_label(toolbar2, "Verlauf")
            self._btn_undo = QPushButton("↶")
            self._btn_undo.setToolTip("Rückgängig (Strg+Z)")
            self._btn_undo.setFixedWidth(32)
            self._btn_undo.setEnabled(False)
            self._btn_redo = QPushButton("↷")
            self._btn_redo.setToolTip("Wiederholen (Strg+Y)")
            self._btn_redo.setFixedWidth(32)
            self._btn_redo.setEnabled(False)
            toolbar2.addWidget(self._btn_undo)
            toolbar2.addWidget(self._btn_redo)

        self._find_bar = QWidget()
        find_layout = QHBoxLayout(self._find_bar)
        find_layout.setContentsMargins(4, 2, 4, 2)
        find_layout.addWidget(QLabel("🔍"))
        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Suchen…")
        self._find_input.returnPressed.connect(self._find_next)
        find_layout.addWidget(self._find_input, stretch=1)
        btn_find_prev = QPushButton("◀")
        btn_find_prev.setFixedWidth(28)
        btn_find_prev.setToolTip("Vorheriger Treffer")
        btn_find_prev.clicked.connect(self._find_previous)
        find_layout.addWidget(btn_find_prev)
        btn_find_next = QPushButton("▶")
        btn_find_next.setFixedWidth(28)
        btn_find_next.setToolTip("Nächster Treffer")
        btn_find_next.clicked.connect(self._find_next)
        find_layout.addWidget(btn_find_next)
        btn_find_close = QPushButton("✕")
        btn_find_close.setFixedWidth(28)
        btn_find_close.setToolTip("Suche schließen (Esc)")
        btn_find_close.clicked.connect(self._hide_find_bar)
        find_layout.addWidget(btn_find_close)
        self._find_bar.setVisible(False)
        layout.addWidget(self._find_bar)
        QShortcut(
            QKeySequence(Qt.Key.Key_Escape), self._find_input, self._hide_find_bar,
            context=Qt.ShortcutContext.WidgetShortcut,
        )

        self._stack = QStackedWidget()
        self.editor = QPlainTextEdit()
        try:
            self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.editor.setPlainText(f"# Lesefehler\n{exc}")
        self.editor.textChanged.connect(self._on_text_changed)
        if self._is_markdown:
            self._btn_undo.clicked.connect(self.editor.undo)
            self._btn_redo.clicked.connect(self.editor.redo)
            self.editor.undoAvailable.connect(self._btn_undo.setEnabled)
            self.editor.redoAvailable.connect(self._btn_redo.setEnabled)
        self._stack.addWidget(self.editor)

        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(True)
        self._stack.addWidget(self._preview)

        if self._is_markdown:
            self._pdf_page = QWidget()
            pdf_layout = QVBoxLayout(self._pdf_page)
            pdf_layout.setContentsMargins(0, 0, 0, 0)
            pdf_layout.setSpacing(0)
            self._pdf_status_label = QLabel("")
            self._pdf_status_label.setStyleSheet(
                "padding: 6px 10px; background:#f1f5f9; color:#334155;"
            )
            self._pdf_status_label.setWordWrap(True)
            self._pdf_status_label.setVisible(False)
            pdf_layout.addWidget(self._pdf_status_label)
            self._pdf_document = QPdfDocument(self)
            self._pdf_document.statusChanged.connect(self._on_pdf_document_status_changed)
            self._pdf_view = QPdfView()
            self._pdf_view.setDocument(self._pdf_document)
            self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            pdf_layout.addWidget(self._pdf_view, stretch=1)
            self._stack.addWidget(self._pdf_page)
            self._pdf_worker: Optional[_PdfPreviewWorker] = None
            self._pdf_render_pending = False
            # Verzeichnis der zuletzt geladenen Einzelkapitel-PDF (siehe
            # PreviewRenderResult.cleanup_dir) — erst NACH dem Nachladen der
            # nächsten PDF entfernen (Windows sperrt offene Dateien).
            self._pdf_cleanup_dir: Optional[Path] = None

        layout.addWidget(self._stack)

        if self._yaml_toggle_host is not None:
            self._rebuild_yaml_toggles(force=True)
            self._sync_yaml_toggles()

        if initial_line and initial_line > 0:
            block = self.editor.document().findBlockByNumber(initial_line - 1)
            if block.isValid():
                cursor = self.editor.textCursor()
                cursor.setPosition(block.position())
                self.editor.setTextCursor(cursor)
                self.editor.centerCursor()

        status_row = QHBoxLayout()
        self._status = QLabel("Codeansicht aktiv")
        self._status.setStyleSheet("color: #64748b;")
        status_row.addWidget(self._status, stretch=1)
        layout.addLayout(status_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Schließen")
        save_as_btn = buttons.addButton("Speichern als…", QDialogButtonBox.ButtonRole.ActionRole)
        save_as_btn.setToolTip(
            "Speichert den aktuellen Inhalt zusätzlich unter einem neuen Dateinamen/Pfad "
            "(Kopie) - die hier bearbeitete Datei bleibt dieselbe. Ein stillschweigender "
            "Pfadwechsel würde die Zuordnung im Buchbaum/Skeleton-Sync durcheinanderbringen."
        )
        save_as_btn.clicked.connect(self._save_as)
        layout.addWidget(buttons)

        save_shortcut = QAction(self)
        save_shortcut.setShortcut(QKeySequence.StandardKey.Save)
        save_shortcut.triggered.connect(self._save)
        self.addAction(save_shortcut)

        find_shortcut = QAction(self)
        find_shortcut.setShortcut(QKeySequence.StandardKey.Find)
        find_shortcut.triggered.connect(self._show_find_bar)
        self.addAction(find_shortcut)

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Override
        worker = getattr(self, "_pdf_worker", None)
        if worker is not None and worker.isRunning():
            # Der Worker blockiert auf einem echten Quarto-Subprozess, den er
            # nicht auf Zuruf abbrechen kann — kurz warten, sonst statt
            # Absturz durch "Destroyed while thread is still running" den
            # Worker verwaisen lassen (kein Dialog-Widget mehr referenziert,
            # läuft im Hintergrund harmlos zu Ende).
            if not worker.wait(3000):
                worker.finished_ok.disconnect(self._on_pdf_render_ok)
                worker.finished_err.disconnect(self._on_pdf_render_err)
                worker.finished.disconnect(self._on_pdf_worker_finished)
                worker.setParent(None)
        cleanup_dir = getattr(self, "_pdf_cleanup_dir", None)
        if cleanup_dir is not None:
            pdf_document = getattr(self, "_pdf_document", None)
            if pdf_document is not None:
                pdf_document.load(str(_blank_pdf_path()))
            shutil.rmtree(cleanup_dir, ignore_errors=True)
            self._pdf_cleanup_dir = None
        super().closeEvent(event)

    @staticmethod
    def _add_toolbar_group_label(toolbar: QToolBar, text: str) -> None:
        """Kleine, dezente Beschriftung vor einer Button-Gruppe - reine
        Separatoren allein liest man bei so vielen Icons leicht als eine
        einzige lange Reihe; ein Wort pro Gruppe macht den Überblick sofort
        klarer, ohne viel Platz zu kosten."""
        label = QLabel(text)
        # Baseline vor dieser Vergrößerung war 10px - bei "Reset" hierher zurück.
        label.setStyleSheet("color: #8b8f98; font-size: 12px; padding: 0 3px;")
        toolbar.addWidget(label)

    def _add_wrap_buttons(
        self, toolbar: QToolBar, commands: tuple[tuple[str, str, str, str], ...], width: int = 34
    ) -> None:
        for icon, tooltip, before, after in commands:
            btn = QPushButton(icon)
            btn.setFixedWidth(width)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _c=False, b=before, a=after: self._wrap_selection(b, a))
            toolbar.addWidget(btn)

    def _build_formatting_toolbar_row1(self, toolbar: QToolBar) -> None:
        """Erste Toolbar-Zeile: Textformatierung -> Ausrichtung -> Schriftgröße
        -> Mathe. Reine Icons (Platzgründe), bisheriger Text steht als Tooltip;
        auf zwei Zeilen aufgeteilt, weil die volle Formatier-Toolbar in einer
        Zeile ~2300px bräuchte (siehe `_build_formatting_toolbar_row2`)."""
        self._add_toolbar_group_label(toolbar, "Format")
        self._add_wrap_buttons(toolbar, _TEXT_EMPHASIS_COMMANDS)
        toolbar.addSeparator()

        self._add_toolbar_group_label(toolbar, "Ausrichtung")
        self._add_wrap_buttons(toolbar, _ALIGNMENT_COMMANDS, width=38)
        toolbar.addSeparator()

        self._add_toolbar_group_label(toolbar, "Größe")
        self._add_wrap_buttons(toolbar, _SIZE_COMMANDS, width=34)
        toolbar.addSeparator()

        self._add_toolbar_group_label(toolbar, "Mathe")
        self._add_wrap_buttons(toolbar, (_MATH_INLINE_COMMAND,))
        math_block_btn = QPushButton("∫")
        math_block_btn.setFixedWidth(34)
        math_block_btn.setToolTip("Mathe-Block ($$Formel$$)")
        math_block_btn.clicked.connect(self._insert_math_block)
        toolbar.addWidget(math_block_btn)

    def _build_formatting_toolbar_row2(self, toolbar: QToolBar) -> None:
        """Zweite Toolbar-Zeile: Überschriften -> Listen/Zitat -> Einfügen."""
        self._add_toolbar_group_label(toolbar, "Überschrift")
        for icon, tooltip, level in _HEADING_COMMANDS:
            btn = QPushButton(icon)
            btn.setFixedWidth(34)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _c=False, lvl=level: self._set_heading_level(lvl))
            toolbar.addWidget(btn)
        toolbar.addSeparator()

        self._add_toolbar_group_label(toolbar, "Listen")
        for icon, tooltip, marker_for_index in _LINE_PREFIX_COMMANDS:
            btn = QPushButton(icon)
            btn.setFixedWidth(34)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _c=False, m=marker_for_index: self._apply_line_prefix(m))
            toolbar.addWidget(btn)
        toolbar.addSeparator()

        self._add_toolbar_group_label(toolbar, "Einfügen")
        insert_buttons = (
            ("―", "Trennlinie (---)", self._insert_horizontal_rule),
            ("{ }", "Codeblock (```)", self._insert_code_block),
            ("▦", "Tabelle (Pandoc-Pipe-Table)", self._insert_table),
            ("🔗", "Link ([Text](URL))", self._insert_link),
            ("🖼️", "Bild einfügen… (Datei wählen)", self._insert_image),
            ("¹", "Fußnote ([^n])", self._insert_footnote),
        )
        for icon, tooltip, handler in insert_buttons:
            btn = QPushButton(icon)
            btn.setFixedWidth(34)
            btn.setToolTip(tooltip)
            btn.clicked.connect(handler)
            toolbar.addWidget(btn)

    @staticmethod
    def _load_end_commands_from_config() -> list[dict[str, Any]]:
        try:
            import app_config as _app_config
            from ui_qt.book_workspace import repo_root

            cfg = _app_config.read_config(repo_root() / "app_config.json")
            commands = cfg.get("editor_end_commands") or []
            return [c for c in commands if isinstance(c, dict)]
        except (OSError, TypeError, ValueError, ImportError):
            return []

    def _set_status(self, message: str, level: str = "ok") -> None:
        colors = {
            "ok": "#0369a1",
            "warn": "#d97706",
            "error": "#b91c1c",
            "dim": "#64748b",
        }
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {colors.get(level, '#64748b')};")

    def _on_text_changed(self) -> None:
        self._preview_dirty = True
        self._pdf_preview_dirty = True
        if self._yaml_toggle_host is not None:
            self._rebuild_yaml_toggles(force=False)
            self._sync_yaml_toggles()

    def _rebuild_yaml_toggles(self, *, force: bool = False) -> None:
        """Baut YAML-Toggle-Buttons neu, wenn sich die Bool-Key-Menge ändert."""
        if self._yaml_toggle_host is None:
            return
        from frontmatter_bool_toggles import list_bool_toggle_specs, toggle_keys_signature

        text = self.editor.toPlainText() if hasattr(self, "editor") else ""
        sig = toggle_keys_signature(text)
        if not force and sig == self._yaml_toggle_keys_sig:
            return
        self._yaml_toggle_keys_sig = sig

        while self._yaml_toggle_layout.count():
            item = self._yaml_toggle_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._yaml_toggle_buttons.clear()

        for spec in list_bool_toggle_specs(text):
            btn = QPushButton(spec.button_label)
            btn.setCheckable(True)
            btn.setFlat(False)
            btn.setFixedWidth(40)
            btn.setToolTip(spec.tooltip)
            btn.clicked.connect(
                lambda _checked=False, key=spec.key: self._toggle_yaml_bool(key)
            )
            self._yaml_toggle_layout.addWidget(btn)
            self._yaml_toggle_buttons[spec.key] = btn

    def _sync_yaml_toggles(self) -> None:
        if not self._yaml_toggle_buttons:
            return
        from frontmatter_bool_toggles import effective_bool

        text = self.editor.toPlainText()
        for key, btn in self._yaml_toggle_buttons.items():
            blocked = btn.blockSignals(True)
            btn.setChecked(effective_bool(text, key))
            btn.blockSignals(blocked)

    def _toggle_yaml_bool(self, key: str) -> None:
        self._ensure_code_view()
        from frontmatter_bool_toggles import toggle_bool_in_content

        new_text, new_state = toggle_bool_in_content(self.editor.toPlainText(), key)
        self._apply_editor_text(new_text)
        self._rebuild_yaml_toggles(force=False)
        self._sync_yaml_toggles()
        state_word = "an" if new_state else "aus"
        self._set_status(
            f"YAML {key}: {state_word} — noch nicht gespeichert.",
            "ok" if new_state else "dim",
        )

    def _ensure_code_view(self) -> None:
        """Wechselt in die Codeansicht, falls gerade die Leservorschau aktiv
        ist - Formatier-Buttons bearbeiten den Rohtext, nicht das gerenderte
        HTML der Vorschau."""
        if self._stack.currentWidget() is not self.editor:
            if hasattr(self, "_btn_code"):
                self._btn_code.setChecked(True)
            self._show_code()

    def _show_find_bar(self) -> None:
        self._ensure_code_view()
        self._find_bar.setVisible(True)
        self._find_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._find_input.selectAll()

    def _hide_find_bar(self) -> None:
        self._find_bar.setVisible(False)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _find_next(self) -> None:
        self._find(backward=False)

    def _find_previous(self) -> None:
        self._find(backward=True)

    def _find(self, *, backward: bool) -> None:
        """Sucht ab der aktuellen Cursorposition, läuft am Dokumentende (bzw.
        -anfang bei Rückwärtssuche) einmal um, statt dort einfach aufzugeben -
        wie man es von Strg+F in Editoren/Browsern erwartet."""
        term = self._find_input.text()
        if not term:
            return
        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        if self.editor.find(term, flags):
            self._find_input.setStyleSheet("")
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start
        )
        self.editor.setTextCursor(cursor)
        if self.editor.find(term, flags):
            self._find_input.setStyleSheet("")
        else:
            self._find_input.setStyleSheet("background-color: #fde2e1;")

    def _open_gg_swap(self) -> None:
        from types import SimpleNamespace

        from ui_qt.dialogs.gg_content_swap_dialog import open_gg_content_swap_qt

        book = self.book_path
        if book is None:
            # Datei liegt oft unter <book>/content/...
            candidate = self.path.resolve().parent
            if candidate.name.lower() == "content":
                book = candidate.parent
            else:
                book = candidate
        if book is None or not (Path(book) / "_quarto.yml").is_file():
            # weiter hoch suchen
            cur = self.path.resolve().parent
            book = None
            for _ in range(6):
                if (cur / "_quarto.yml").is_file():
                    book = cur
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent
        if book is None:
            QMessageBox.information(
                self,
                "GrammarGraph",
                "Kein Buchprojekt (_quarto.yml) zur Datei gefunden.",
            )
            return

        parent_studio = self.parent()
        log = getattr(parent_studio, "log", None) if parent_studio is not None else None
        if not callable(log):
            # MainWindow-Facade oft über window()
            win = self.window()
            facade = getattr(win, "_facade", None)
            log = getattr(facade, "log", None) if facade is not None else None
        studio = SimpleNamespace(
            current_book=Path(book),
            log=log if callable(log) else (lambda *a, **k: None),
            root=self,
        )
        open_gg_content_swap_qt(studio, self)

    def _open_kdp_cover(self) -> None:
        """KDP-Wrap-Cover-Designer (separates Upload-PDF, nicht Deckblatt.md)."""
        from types import SimpleNamespace

        from ui_qt.dialogs.kdp_cover_dialog import open_kdp_cover_qt

        book = self.book_path
        if book is None or not Path(book).is_dir():
            cur = self.path.resolve().parent
            book = None
            for _ in range(6):
                if (cur / "_quarto.yml").is_file():
                    book = cur
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent
        if book is None:
            QMessageBox.information(
                self,
                "KDP-Wrap",
                "Kein Buchprojekt (_quarto.yml) zur Datei gefunden.\n"
                "Der Cover-Designer kann trotzdem geöffnet werden — "
                "Export-Pfad dann manuell wählen.",
            )

        parent_studio = self.parent()
        log = getattr(parent_studio, "log", None) if parent_studio is not None else None
        if not callable(log):
            win = self.window()
            facade = getattr(win, "_facade", None)
            log = getattr(facade, "log", None) if facade is not None else None
        studio = SimpleNamespace(
            current_book=Path(book) if book else None,
            log=log if callable(log) else (lambda *a, **k: None),
            root=self,
        )
        open_kdp_cover_qt(studio, self)

    def _find_skeleton_sync_targets(self) -> list:
        """Gleichnamige Datei in einer nicht-geschuetzten Skeleton-Bibliothek?

        Nur der Dateiname zaehlt (nicht der volle Pfad) — Skeleton-Pools
        spiegeln dieselbe flache ``content/``-Struktur wie echte Buecher.
        """
        try:
            from ui_qt.dialogs.skeleton_file_sync_dialog import (
                find_matching_skeleton_targets,
            )

            return find_matching_skeleton_targets(self.path.name)
        except (ImportError, OSError, ValueError):
            return []

    def _open_skeleton_sync(self) -> None:
        from ui_qt.dialogs.skeleton_file_sync_dialog import open_skeleton_file_sync_qt

        open_skeleton_file_sync_qt(
            self,
            book_file_name=self.path.name,
            book_content=self.editor.toPlainText(),
        )

    def _apply_editor_text(self, new_text: str) -> None:
        cursor = self.editor.textCursor()
        pos = cursor.position()
        self.editor.blockSignals(True)
        self.editor.setPlainText(new_text)
        self.editor.blockSignals(False)
        cursor = self.editor.textCursor()
        cursor.setPosition(min(pos, len(new_text)))
        self.editor.setTextCursor(cursor)
        self._preview_dirty = True

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

    def _insert_end_command(self, command: dict[str, Any]) -> None:
        self._ensure_code_view()
        new_content, message, level = insert_end_command_text(
            self.editor.toPlainText(),
            command,
        )
        self._set_status(message, level)
        if new_content is None:
            return
        self.editor.setPlainText(new_content)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self._pending_skeleton_command = dict(command)
        self._preview_dirty = True

    def _insert_hard_line_break(self) -> None:
        """Fügt „\\“ (Pandocs harter Zeilenumbruch) ans Ende der Zeile, in der
        der Cursor steht - unabhängig davon, wo in der Zeile der Cursor genau
        steht. Bewusst `EndOfBlock` statt `EndOfLine`: bei aktiviertem
        Zeilenumbruch (Word-Wrap, Standard für QPlainTextEdit) markiert
        `EndOfLine` nur das Ende der sichtbaren, umgebrochenen Zeile, nicht
        das Ende der tatsächlichen Quelltext-Zeile."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        if cursor.block().text().endswith("\\"):
            self._set_status("Zeile endet bereits mit einem harten Zeilenumbruch (\\).", "dim")
            return
        cursor.insertText("\\")
        self.editor.setTextCursor(cursor)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._set_status("Harter Zeilenumbruch (\\) am Zeilenende eingefügt — noch nicht gespeichert.", "ok")

    @staticmethod
    def _selected_text_normalized(cursor: QTextCursor) -> str:
        """`QTextCursor.selectedText()` liefert bei mehrzeiliger Auswahl den
        Unicode-Absatztrenner U+2029 statt "\\n" - für Markdown-Text normalisieren."""
        return cursor.selectedText().replace(" ", "\n")

    def _focus_editor(self) -> None:
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._set_status("Formatierung eingefügt — noch nicht gespeichert.", "ok")

    def _wrap_selection(self, before: str, after: str, placeholder: str = "Text") -> None:
        """Umschließt die Auswahl mit `before`/`after` (z. B. fett/kursiv).
        Ohne Auswahl wird ein Platzhalter eingefügt und markiert.

        Typst-Wraps + Markdown-Bild: konvertiert nach ``#image`` und nutzt
        einen Fence-Block (sonst Klartext im PDF).
        """
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        start = cursor.selectionStart()
        selected = self._selected_text_normalized(cursor)
        if "{=typst}" in after and selected:
            from ui_qt.editor_image import (
                contains_markdown_image,
                convert_markdown_images_to_typst,
            )

            if contains_markdown_image(selected):
                open_cmd = before[1:] if before.startswith("`") else before
                body = convert_markdown_images_to_typst(selected).strip()
                if open_cmd.endswith("["):
                    inner = f"{open_cmd}\n  {body}\n]"
                else:
                    inner = f"{open_cmd}{body}]"
                replacement = f"```{{=typst}}\n{inner}\n```\n"
                cursor.insertText(replacement)
                body_start = replacement.find(body)
                new_cursor = self.editor.textCursor()
                if body_start >= 0:
                    new_cursor.setPosition(start + body_start)
                    new_cursor.setPosition(
                        start + body_start + len(body), QTextCursor.MoveMode.KeepAnchor
                    )
                    self.editor.setTextCursor(new_cursor)
                self._preview_dirty = True
                self._focus_editor()
                return

        result = markdown_formatting.wrap_selection(selected, before, after, placeholder)
        cursor.insertText(result.replacement)
        new_cursor = self.editor.textCursor()
        new_cursor.setPosition(start + result.select_from)
        new_cursor.setPosition(start + result.select_to, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(new_cursor)
        self._focus_editor()

    def _set_heading_level(self, level: int) -> None:
        """Setzt die führenden '#' der aktuellen Zeile auf `level` (1-6)."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        new_line = markdown_formatting.set_heading_level(cursor.selectedText(), level)
        cursor.insertText(new_line)
        self.editor.setTextCursor(cursor)
        self._focus_editor()

    def _apply_line_prefix(self, marker_for_index: Callable[[int], str]) -> None:
        """Setzt ein Zeilen-Präfix (Zitat/Liste) auf die aktuelle Zeile oder,
        bei Mehrfachauswahl, auf jede betroffene Zeile."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        doc = self.editor.document()
        start_block = doc.findBlock(cursor.selectionStart())
        end_block = doc.findBlock(cursor.selectionEnd())
        span = QTextCursor(doc)
        span.setPosition(start_block.position())
        span.setPosition(end_block.position() + end_block.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        lines = self._selected_text_normalized(span).split("\n")
        new_lines = markdown_formatting.apply_line_prefix(lines, marker_for_index)
        span.insertText("\n".join(new_lines))
        self.editor.setTextCursor(span)
        self._focus_editor()

    def _insert_horizontal_rule(self) -> None:
        """Fügt eine Trennlinie (---) als eigenen Block ein - mit Leerzeilen
        davor UND danach, sonst würde Pandoc "Text\\n---" als Setext-
        Überschrift lesen statt als Trennlinie."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText("\n\n---\n\n")
        self.editor.setTextCursor(cursor)
        self._focus_editor()

    def _insert_code_block(self) -> None:
        """Umschließt die Auswahl (oder eine leere Zeile) mit einem Pandoc-
        Codefence - eigener Block, daher mit Leerzeilen umgeben."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        start = cursor.selectionStart()
        selected = self._selected_text_normalized(cursor)
        cursor.insertText(f"\n```\n{selected}\n```\n")
        new_cursor = self.editor.textCursor()
        new_cursor.setPosition(start + len("\n```\n") + len(selected))
        self.editor.setTextCursor(new_cursor)
        self._focus_editor()

    def _insert_table(self) -> None:
        """Fügt ein Pandoc-Pipe-Table-Grundgerüst als eigenen Block ein."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText(f"\n\n{markdown_formatting.table_skeleton()}\n\n")
        self.editor.setTextCursor(cursor)
        self._focus_editor()

    def _insert_link(self) -> None:
        """Fügt `[Text](URL)` ein; der Linktext ist die Auswahl (oder ein
        Platzhalter), danach ist „URL“ zum Überschreiben markiert."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        start = cursor.selectionStart()
        text_part = self._selected_text_normalized(cursor) or "Linktext"
        prefix = f"[{text_part}]("
        cursor.insertText(f"{prefix}URL)")
        new_cursor = self.editor.textCursor()
        new_cursor.setPosition(start + len(prefix))
        new_cursor.setPosition(start + len(prefix) + len("URL"), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(new_cursor)
        self._focus_editor()

    def _insert_image(self) -> None:
        """Öffnet den Bild-Dialog und fügt ``![Alt](/img/…)`` ein."""
        self._ensure_code_view()
        book_root = self.book_path
        if book_root is None and self.path is not None:
            from ui_qt.editor_image import infer_book_root_from_markdown

            book_root = infer_book_root_from_markdown(Path(self.path))
        if book_root is None:
            QMessageBox.warning(
                self,
                "Bild einfügen",
                "Buchprojekt nicht bekannt — Bild kann nicht eingebunden werden.",
            )
            return

        from ui_qt.dialogs.insert_image_dialog import InsertImageDialog
        from ui_qt.editor_image import suggested_image_start_dir

        default_alt = self._selected_text_normalized(self.editor.textCursor())
        dialog = InsertImageDialog(
            self,
            book_root=book_root,
            start_dir=suggested_image_start_dir(book_root),
            default_alt=default_alt,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        snippet = dialog.markdown_snippet()
        if not snippet:
            return
        cursor = self.editor.textCursor()
        cursor.insertText(snippet)
        self._preview_dirty = True
        self._focus_editor()

    def _insert_footnote(self) -> None:
        """Fügt an der Cursorposition `[^n]` ein (n = nächste freie Nummer)
        und die zugehörige Definition `[^n]: ` ans Dateiende - Cursor landet
        dort zum sofortigen Ausfüllen."""
        self._ensure_code_view()
        full_text = self.editor.toPlainText()
        idx = markdown_formatting.next_footnote_index(full_text)
        cursor = self.editor.textCursor()
        cursor.insertText(f"[^{idx}]")
        end_cursor = self.editor.textCursor()
        end_cursor.movePosition(QTextCursor.MoveOperation.End)
        end_cursor.insertText(f"\n\n[^{idx}]: ")
        self.editor.setTextCursor(end_cursor)
        self._focus_editor()

    def _insert_math_block(self) -> None:
        """Umschließt die Auswahl (oder eine leere Zeile) mit einem Mathe-
        Block ($$...$$) - eigener Block, daher mit Leerzeilen umgeben."""
        self._ensure_code_view()
        cursor = self.editor.textCursor()
        start = cursor.selectionStart()
        selected = self._selected_text_normalized(cursor)
        cursor.insertText(f"\n$$\n{selected}\n$$\n")
        new_cursor = self.editor.textCursor()
        new_cursor.setPosition(start + len("\n$$\n") + len(selected))
        self.editor.setTextCursor(new_cursor)
        self._focus_editor()

    def _offer_skeleton_sync(self) -> None:
        command = self._pending_skeleton_command
        self._pending_skeleton_command = None
        if command is None or self.book_path is None:
            return
        try:
            from ui_qt.book_workspace import repo_root
            from ui_qt.skeleton_sync import (
                apply_end_command_to_skeleton_file,
                resolve_skeleton_counterpart,
            )

            counterpart = resolve_skeleton_counterpart(
                self.book_path,
                self.path,
                repo_root(),
            )
        except (OSError, ImportError, TypeError, ValueError):
            return
        if counterpart is None:
            return

        label = str(command.get("label") or "End-Befehl")
        reply = QMessageBox.question(
            self,
            "In Skeleton-Vorlage übernehmen?",
            (
                f"„{label}“ auch in die Skeleton-Vorlage schreiben?\n\n"
                f"Profil: {counterpart.profile}\n"
                f"Datei: {counterpart.rel_path}\n\n"
                "Skeleton ist profilweit (nicht buchspezifisch).\n"
                "Es wird nur der End-Befehl ergänzt — der restliche Vorlageninhalt bleibt."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, message = apply_end_command_to_skeleton_file(counterpart.library_path, command)
        if ok:
            QMessageBox.information(
                self,
                "Skeleton aktualisiert",
                f"End-Befehl in die Vorlage übernommen.\n\n{counterpart.rel_path}\n\n{message}",
            )
        else:
            QMessageBox.warning(
                self,
                "Skeleton nicht aktualisiert",
                message,
            )

    def _save(self) -> None:
        """Schreibt die Datei; der Dialog bleibt offen (Schließen separat)."""
        try:
            self.path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._offer_skeleton_sync()
        if self._on_save is not None:
            try:
                self._on_save()
            except Exception:  # noqa: BLE001 — Speichern soll nicht wegen Refresh scheitern
                pass
        self._set_status("Gespeichert.", level="ok")

    def _save_as(self) -> None:
        """Speichert eine Kopie unter einem neuen Pfad; `self.path` (die hier
        bearbeitete Datei) bleibt unverändert - andere Teile der App
        (Buchbaum, Skeleton-Sync) sind an genau diesen Pfad gebunden, ein
        stiller Wechsel würde diese Zuordnung durcheinanderbringen. Der Dialog
        bleibt offen, die Bearbeitung geht am Original weiter."""
        target, _ = QFileDialog.getSaveFileName(
            self, "Speichern als", str(self.path), "Markdown (*.md);;Alle Dateien (*.*)"
        )
        if not target:
            return
        try:
            Path(target).write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Speichern als fehlgeschlagen", str(exc))
            return
        self._set_status(f"Zusätzlich gespeichert unter: {target}", "ok")


def save_json_file(
    parent: QWidget,
    data: Any,
    *,
    suggested_name: str = "buchstruktur.json",
    start_dir: Optional[Path] = None,
) -> bool:
    initial = suggested_name
    if start_dir is not None:
        try:
            dest_dir = Path(start_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            initial = str(dest_dir / Path(suggested_name).name)
        except OSError:
            initial = suggested_name
    path, _ = QFileDialog.getSaveFileName(
        parent, "Buchstruktur speichern", initial, "JSON (*.json)"
    )
    if not path:
        return False
    try:
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except (OSError, TypeError, ValueError) as exc:
        QMessageBox.critical(parent, "Speichern fehlgeschlagen", str(exc))
        return False


def load_json_file(
    parent: QWidget,
    *,
    start_dir: Optional[Path] = None,
) -> Optional[Any]:
    initial = str(start_dir) if start_dir is not None else ""
    if start_dir is not None:
        try:
            Path(start_dir).mkdir(parents=True, exist_ok=True)
            initial = str(Path(start_dir))
        except OSError:
            initial = ""
    path, _ = QFileDialog.getOpenFileName(
        parent, "Buchstruktur laden (JSON)", initial, "JSON (*.json);;Alle Dateien (*.*)"
    )
    if not path:
        return None
    chosen = Path(path)
    name = chosen.name.casefold()
    if name in ("_quarto.yml", "_quarto.yaml") or chosen.suffix.lower() in (".yml", ".yaml"):
        QMessageBox.warning(
            parent,
            "Falsche Dateiart",
            "Das Menü lädt nur eine JSON-Buchstruktur-Sicherung — nicht _quarto.yml.\n\n"
            "• Projekt wechseln: Dropdown „Buchprojekt“ oben\n"
            "• Struktur aus Quarto laden: Projekt wählen (liest _quarto.yml automatisch)\n"
            "• In Quarto schreiben: Datei → In Quarto speichern\n\n"
            f"Gewählt: {chosen.name}",
        )
        return None
    try:
        return json.loads(chosen.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        QMessageBox.critical(
            parent,
            "Laden fehlgeschlagen",
            "Die Datei ist kein gültiges JSON.\n\n"
            "Hinweis: _quarto.yml ist YAML und gehört nicht in dieses Menü.\n\n"
            f"{exc}",
        )
        return None
    except OSError as exc:
        QMessageBox.critical(parent, "Laden fehlgeschlagen", str(exc))
        return None
