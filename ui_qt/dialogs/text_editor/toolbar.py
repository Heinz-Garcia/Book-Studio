"""Formatierungsleiste und Einfüge-Aktionen (Überschrift, Tabelle, Bild, Fußnote, End-Befehle).

Mixin von ``TextEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolBar,
)

from ui_qt import markdown_formatting
from ui_qt.dialogs.text_editor.common import (
    _ALIGNMENT_COMMANDS,
    _HEADING_COMMANDS,
    _LINE_PREFIX_COMMANDS,
    _MATH_INLINE_COMMAND,
    _SIZE_COMMANDS,
    _TEXT_EMPHASIS_COMMANDS,
)
from ui_qt.end_commands import insert_end_command_text


class FormattingMixin:
    """Formatierungsleiste und Einfüge-Aktionen (Überschrift, Tabelle, Bild, Fußnote, End-Befehle)."""

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

    @staticmethod
    def _fit_toolbar_button(
        btn: QPushButton, *, min_width: int = 34, fit_text: bool = False
    ) -> None:
        """Kompaktes Padding (Theme hat 8+12px — das schnitt H1 bei 34px ab)."""
        btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  padding: 2px 5px;"
            "  margin: 0px;"
            "  min-height: 26px;"
            "  border-radius: 6px;"
            "}"
        )
        if fit_text:
            text_w = btn.fontMetrics().horizontalAdvance(btn.text())
            btn.setFixedWidth(max(min_width, text_w + 14))
        else:
            btn.setFixedWidth(min_width)
        btn.setMinimumHeight(26)

    def _add_wrap_buttons(
        self, toolbar: QToolBar, commands: tuple[tuple[str, str, str, str], ...], width: int = 34
    ) -> None:
        for icon, tooltip, before, after in commands:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            # Mehrzeichen-Labels (A+, H1, …) an Textbreite; reine Icons fest
            fit = len(icon) >= 2 and icon.isascii()
            self._fit_toolbar_button(btn, min_width=width, fit_text=fit)
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
        math_block_btn.setToolTip("Mathe-Block ($$Formel$$)")
        self._fit_toolbar_button(math_block_btn, min_width=34)
        math_block_btn.clicked.connect(self._insert_math_block)
        toolbar.addWidget(math_block_btn)

    def _build_formatting_toolbar_row2(self, toolbar: QToolBar) -> None:
        """Zweite Toolbar-Zeile: Überschriften -> Listen/Zitat -> Einfügen."""
        self._add_toolbar_group_label(toolbar, "Überschrift")
        for icon, tooltip, level in _HEADING_COMMANDS:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            self._fit_toolbar_button(btn, min_width=40, fit_text=True)
            btn.clicked.connect(lambda _c=False, lvl=level: self._set_heading_level(lvl))
            toolbar.addWidget(btn)
        toolbar.addSeparator()

        self._add_toolbar_group_label(toolbar, "Listen")
        for icon, tooltip, marker_for_index in _LINE_PREFIX_COMMANDS:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            self._fit_toolbar_button(
                btn, min_width=36, fit_text=icon.isascii() and len(icon) >= 2
            )
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
            btn.setToolTip(tooltip)
            self._fit_toolbar_button(
                btn, min_width=36, fit_text=icon.isascii() and len(icon) >= 2
            )
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
