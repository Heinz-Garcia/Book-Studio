"""Read-only Preview-Dialoge und einfache Text-/JSON-Editoren."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
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

from ui_qt.end_commands import DEFAULT_PAGEBREAK_COMMAND

# Eigenständiges Tool (tools/live_preview) — kein PySide6-Import dort, damit
# die Render-Logik ohne GUI testbar/aufrufbar bleibt (siehe dortiger Modul-
# Docstring). Diese Datei ruft nur render_single_chapter_preview() auf und
# zeigt das Ergebnis an.
from ui_qt.dialogs.text_editor.common import (  # noqa: F401
    _ALIGNMENT_COMMANDS,
    _HEADING_COMMANDS,
    _LINE_PREFIX_COMMANDS,
    _MATH_INLINE_COMMAND,
    _PdfPreviewWorker,
    _SIZE_COMMANDS,
    _TEXT_EMPHASIS_COMMANDS,
)
from ui_qt.dialogs.text_editor.toolbar import FormattingMixin
from ui_qt.dialogs.text_editor.find_replace import FindReplaceMixin
from ui_qt.dialogs.text_editor.preview import PreviewMixin
from ui_qt.dialogs.text_editor.saving import SavingMixin
from ui_qt.dialogs.text_editor.extras import ExtrasMixin


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


# Alle folgenden (Icon, Tooltip, Marker davor, Marker danach)-Tupel wickeln die
# Auswahl ein bzw. fügen bei leerer Auswahl einen selektierten Platzhalter ein
# (siehe `_wrap_selection`). Sieben klar getrennte Gruppen (je eigener
# Toolbar-Abschnitt), damit man bei so vielen Buttons noch durchblickt:
# Textformatierung -> Ausrichtung -> Schriftgröße -> Mathe -> Überschriften ->
# Listen/Zitat -> Einfügen.

# Typst-Raw-Passthrough (`center`/`horizon`): Pandoc-Markdown kennt keine
# Ausrichtung nativ, das ist reine Typst-Fähigkeit.
# Ebenfalls Typst-Raw-Passthrough: `em` ist relativ zur aktuellen Schriftgröße,
# funktioniert also unabhängig davon, welche Basisgröße gerade gilt.
# (Icon, Tooltip, Überschrift-Ebene)
# (Icon, Tooltip, Marker-Fabrik pro Zeilenindex)
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


class TextEditorDialog(
    FormattingMixin, FindReplaceMixin, PreviewMixin, SavingMixin, ExtrasMixin,
    QDialog,
):
    def __init__(
        self,
        parent: Optional[QWidget],
        path: Path,
        *,
        title: str = "Editor",
        end_commands: Optional[Sequence[dict[str, Any]]] = None,
        on_save: Optional[Callable[[], None]] = None,
        initial_line: Optional[int] = None,
        initial_find_term: Optional[str] = None,
        initial_find_whole_word: bool = False,
        initial_find_case_sensitive: bool = False,
        book_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.book_path = Path(book_path) if book_path else None
        # Mehrere Aufrufer können dasselbe Fenster nutzen (open_text_editor).
        self._on_save_callbacks: list[Callable[[], None]] = [on_save] if on_save else []
        self._on_finished_callbacks: list[Callable[[], None]] = []
        self.finished.connect(self._run_finished_callbacks)
        self._pending_skeleton_command: Optional[dict[str, Any]] = None
        self._is_markdown = self.path.suffix.lower() == ".md"
        self._is_quarto_yml = self.path.name.lower() in {"_quarto.yml", "_quarto.yaml"}
        self._is_rahmen_page = False
        self._rahmen_rel_path: Optional[str] = None
        if self._is_markdown and self.book_path is not None:
            try:
                rel = self.path.resolve().relative_to(self.book_path.resolve()).as_posix()
            except ValueError:
                rel = None
            if rel is not None:
                from page_required import is_page_required

                try:
                    content = self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
                except OSError:
                    content = ""
                if is_page_required(rel_path=rel, content=content):
                    self._is_rahmen_page = True
                    self._rahmen_rel_path = rel
        self._preview_dirty = True
        self._pdf_preview_dirty = True
        # Inherited from book-global structure search (no duplicate UI here).
        self._find_whole_word = bool(initial_find_whole_word)
        self._find_case_sensitive = bool(initial_find_case_sensitive)
        self.setWindowTitle(f"{title} — {self.path.name}")
        self.resize(1600, 720)
        layout = QVBoxLayout(self)

        # Zwei Zeilen statt einer: die volle Formatier-Toolbar braucht in einer
        # einzigen Zeile ~2300px, weit über eine praktikable Dialogbreite hinaus
        # (und QToolBar würde den Rest sonst hinter einem "»"-Overflow-Button
        # verstecken). Zeile 1: Ansicht/Seite + Text-Format/Ausrichtung/Größe/
        # Mathe. Zeile 2: Struktur (Überschrift/Listen/Einfügen) + Umbruch/Ende/Verlauf.
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar QPushButton {"
            "  font-size: 13px;"
            "  padding: 2px 6px;"
            "  margin: 0px;"
            "  min-height: 26px;"
            "}"
        )
        layout.addWidget(toolbar)

        toolbar2 = QToolBar()
        toolbar2.setMovable(False)
        toolbar2.setStyleSheet(
            "QToolBar QPushButton {"
            "  font-size: 13px;"
            "  padding: 2px 6px;"
            "  margin: 0px;"
            "  min-height: 26px;"
            "}"
        )
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
            btn_find.setToolTip(
                "Suchen / Ersetzen (Strg+F / Strg+H)\n"
                "Enter: nächster Treffer, Esc: schließen"
            )
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
        find_layout.setSpacing(4)
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

        self._replace_input: Optional[QLineEdit] = None
        self._find_replace_status: Optional[QLabel] = None
        if self._is_markdown:
            find_layout.addWidget(QLabel("→"))
            self._replace_input = QLineEdit()
            self._replace_input.setPlaceholderText("Ersetzen durch…")
            self._replace_input.returnPressed.connect(self._replace_and_find_next)
            find_layout.addWidget(self._replace_input, stretch=1)

            btn_replace = QPushButton("Ersetzen")
            btn_replace.setToolTip("Aktuellen Treffer ersetzen")
            btn_replace.clicked.connect(self._replace_current)
            find_layout.addWidget(btn_replace)

            btn_replace_next = QPushButton("Ersetzen & weiter")
            btn_replace_next.setToolTip("Ersetzen und zum nächsten Treffer springen")
            btn_replace_next.clicked.connect(self._replace_and_find_next)
            find_layout.addWidget(btn_replace_next)

            btn_replace_all = QPushButton("Alle ersetzen")
            btn_replace_all.setToolTip("Alle Treffer in dieser Datei ersetzen")
            btn_replace_all.clicked.connect(self._replace_all)
            find_layout.addWidget(btn_replace_all)

            self._find_replace_status = QLabel("")
            self._find_replace_status.setStyleSheet("color:#5b6573; min-width: 5em;")
            find_layout.addWidget(self._find_replace_status)

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
        if self._replace_input is not None:
            QShortcut(
                QKeySequence(Qt.Key.Key_Escape),
                self._replace_input,
                self._hide_find_bar,
                context=Qt.ShortcutContext.WidgetShortcut,
            )

        self._stack = QStackedWidget()
        self.editor = QPlainTextEdit()
        try:
            self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.editor.setPlainText(f"# Lesefehler\n{exc}")
        self._saved_snapshot = self.editor.toPlainText()
        self._content_dirty = False
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

        self._apply_initial_position(initial_line, initial_find_term)

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
        if self._is_markdown:
            save_pool_btn = buttons.addButton(
                "Speichern als und in Skeleton-Pool…",
                QDialogButtonBox.ButtonRole.ActionRole,
            )
            save_pool_btn.setToolTip(
                "Wie „Speichern als…“, und legt dieselbe Markdown-Datei zusätzlich im "
                "Skeleton-Pool ab (Standard-Profil, Manifest-Eintrag) — damit die Vorlage "
                "für andere Bücher erhalten bleibt, ohne den Skeleton-Editor zu öffnen."
            )
            save_pool_btn.clicked.connect(self._save_as_and_to_skeleton)
        if self._is_quarto_yml:
            restore_btn = buttons.addButton(
                "Sicherung wiederherstellen…",
                QDialogButtonBox.ButtonRole.ActionRole,
            )
            restore_btn.setToolTip(
                "Letzte Backup-Kopie von _quarto.yml unter .backups/quarto_yml/ einspielen."
            )
            restore_btn.clicked.connect(lambda: self._restore_quarto_yml_backup())
            # Ausgangsstand sichern, bevor der Nutzer etwas kaputt speichert
            try:
                from services.quarto_yml_guard import create_backup

                create_backup(self.path)
            except OSError:
                pass
        elif self._is_rahmen_page and self.book_path is not None:
            restore_btn = buttons.addButton(
                "Sicherung wiederherstellen…",
                QDialogButtonBox.ButtonRole.ActionRole,
            )
            restore_btn.setToolTip(
                "Letzte Backup-Kopie dieser Rahmenseite unter .backups/rahmen/ einspielen."
            )
            restore_btn.clicked.connect(lambda: self._restore_rahmen_backup())
            try:
                from services.rahmen_pages import create_backup

                create_backup(self.path, book_path=self.book_path)
            except OSError:
                pass
        layout.addWidget(buttons)

        save_shortcut = QAction(self)
        save_shortcut.setShortcut(QKeySequence.StandardKey.Save)
        save_shortcut.triggered.connect(self._save)
        self.addAction(save_shortcut)

        find_shortcut = QAction(self)
        find_shortcut.setShortcut(QKeySequence.StandardKey.Find)
        find_shortcut.triggered.connect(self._show_find_bar)
        self.addAction(find_shortcut)
        if self._is_markdown:
            replace_shortcut = QAction(self)
            replace_shortcut.setShortcut(QKeySequence.StandardKey.Replace)
            replace_shortcut.triggered.connect(self._show_replace_bar)
            self.addAction(replace_shortcut)

    def reject(self) -> None:  # Esc / Schließen-Knopf
        if not self._confirm_close_unsaved():
            return
        super().reject()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Override
        if not self._confirm_close_unsaved():
            event.ignore()
            return
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
        if getattr(self, "_loaded_size", None) is not None:
            from ui_qt.autonomous_window import persist_window_size

            persist_window_size(self, "text_editor_size")
        super().closeEvent(event)

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
        self._refresh_content_dirty_status()

    def _apply_initial_position(
        self, initial_line: Optional[int], initial_find_term: Optional[str]
    ) -> None:
        if initial_line and initial_line > 0:
            block = self.editor.document().findBlockByNumber(initial_line - 1)
            if block.isValid():
                cursor = self.editor.textCursor()
                cursor.setPosition(block.position())
                self.editor.setTextCursor(cursor)
                self.editor.centerCursor()

        find_seed = str(initial_find_term or "").strip()
        if find_seed and self._is_markdown:
            self._apply_initial_find(find_seed)

    def attach_caller(
        self,
        *,
        on_save: Optional[Callable[[], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        initial_line: Optional[int] = None,
        initial_find_term: Optional[str] = None,
        initial_find_whole_word: bool = False,
        initial_find_case_sensitive: bool = False,
    ) -> None:
        """Weiterer Aufrufer für das schon offene Fenster derselben Datei.

        Seine Callbacks laufen zusätzlich (nicht statt) den bisherigen; ein
        mitgegebenes Sprungziel / Suchwort wird angewendet.
        """
        # Gleiche Callbacks (z. B. gebundene Methode desselben Aufrufers)
        # nur einmal — sonst läuft ein Refresh pro erneutem Öffnen.
        if on_save is not None and on_save not in self._on_save_callbacks:
            self._on_save_callbacks.append(on_save)
        if on_finished is not None and on_finished not in self._on_finished_callbacks:
            self._on_finished_callbacks.append(on_finished)
        if initial_find_term:
            self._find_whole_word = bool(initial_find_whole_word)
            self._find_case_sensitive = bool(initial_find_case_sensitive)
        self._apply_initial_position(initial_line, initial_find_term)

    def _run_finished_callbacks(self, *_args: object) -> None:
        for callback in list(self._on_finished_callbacks):
            callback()

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
        self._refresh_content_dirty_status()

_active_text_editors: list[TextEditorDialog] = []


def open_text_editor(
    host: Optional[QWidget],
    path: Path,
    *,
    title: str = "Editor",
    end_commands: Optional[Sequence[dict[str, Any]]] = None,
    on_save: Optional[Callable[[], None]] = None,
    on_finished: Optional[Callable[[], None]] = None,
    initial_line: Optional[int] = None,
    initial_find_term: Optional[str] = None,
    initial_find_whole_word: bool = False,
    initial_find_case_sensitive: bool = False,
    book_path: Optional[Path] = None,
) -> TextEditorDialog:
    """Öffnet den Text-/Markdown-Editor **nicht-modal** (Hauptfenster bleibt bedienbar).

    Pro Dateipfad höchstens ein Fenster — ein zweiter Aufruf bringt das
    bestehende nach vorne. Verschachteltes ``.exec()`` ist applikationsweit
    unerwünscht (Windows: Kind-Dialog blockiert und minimiert mit dem Parent).
    """
    from ui_qt.autonomous_window import (
        apply_persisted_size,
        prepare_autonomous_window,
        raise_if_open,
        show_autonomous_window,
    )

    resolved = Path(path).resolve()
    found = raise_if_open(
        _active_text_editors,
        lambda d: Path(d.path).resolve() == resolved,
    )
    if found is not None:
        # Callbacks/Sprungziel des neuen Aufrufers nicht verwerfen.
        found.attach_caller(
            on_save=on_save,
            on_finished=on_finished,
            initial_line=initial_line,
            initial_find_term=initial_find_term,
            initial_find_whole_word=initial_find_whole_word,
            initial_find_case_sensitive=initial_find_case_sensitive,
        )
        return found

    dlg = TextEditorDialog(
        None,
        resolved,
        title=title,
        end_commands=end_commands,
        on_save=on_save,
        initial_line=initial_line,
        initial_find_term=initial_find_term,
        initial_find_whole_word=initial_find_whole_word,
        initial_find_case_sensitive=initial_find_case_sensitive,
        book_path=book_path,
    )
    prepare_autonomous_window(dlg, host)
    apply_persisted_size(
        dlg,
        "text_editor_size",
        default=(1600, 720),
        min_size=(800, 500),
    )
    if on_finished is not None:
        dlg.attach_caller(on_finished=on_finished)
    return show_autonomous_window(dlg, _active_text_editors)


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
