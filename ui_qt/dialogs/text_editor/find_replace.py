"""Suchen und Ersetzen.

Mixin von ``TextEditorDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument


class FindReplaceMixin:
    """Suchen und Ersetzen."""

    def _show_find_bar(self) -> None:
        self._ensure_code_view()
        self._find_bar.setVisible(True)
        self._set_find_replace_status("")
        self._find_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._find_input.selectAll()

    def _show_replace_bar(self) -> None:
        """Strg+H: Suchleiste öffnen und Fokus auf Ersetzen-Feld."""
        if self._replace_input is None:
            self._show_find_bar()
            return
        self._ensure_code_view()
        self._find_bar.setVisible(True)
        self._set_find_replace_status("")
        self._replace_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._replace_input.selectAll()

    def _apply_initial_find(self, term: str) -> None:
        """Open find bar with ``term`` and jump to the first match (from structure search)."""
        self._ensure_code_view()
        self._find_bar.setVisible(True)
        self._set_find_replace_status("")
        self._find_input.setText(term)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        self._find_next()
        self._find_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._find_input.selectAll()

    def _hide_find_bar(self) -> None:
        self._find_bar.setVisible(False)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_find_replace_status(self, message: str) -> None:
        if self._find_replace_status is not None:
            self._find_replace_status.setText(message)

    def _find_next(self) -> None:
        self._find(backward=False)

    def _find_previous(self) -> None:
        self._find(backward=True)

    def _find_flags(self, *, backward: bool) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        if self._find_whole_word:
            flags |= QTextDocument.FindFlag.FindWholeWords
        if self._find_case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        return flags

    def _find(self, *, backward: bool) -> bool:
        """Sucht ab der aktuellen Cursorposition, läuft am Dokumentende (bzw.
        -anfang bei Rückwärtssuche) einmal um, statt dort einfach aufzugeben -
        wie man es von Strg+F in Editoren/Browsern erwartet.

        Returns True if a match was selected.
        """
        term = self._find_input.text()
        if not term:
            return False
        flags = self._find_flags(backward=backward)
        if self.editor.find(term, flags):
            self._find_input.setStyleSheet("")
            return True
        cursor = self.editor.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start
        )
        self.editor.setTextCursor(cursor)
        if self.editor.find(term, flags):
            self._find_input.setStyleSheet("")
            return True
        self._find_input.setStyleSheet("background-color: #fde2e1;")
        return False

    def _selection_matches_find_term(self) -> bool:
        term = self._find_input.text()
        if not term:
            return False
        selected = self.editor.textCursor().selectedText()
        if not selected:
            return False
        if self._find_case_sensitive:
            if selected != term:
                return False
        elif selected.casefold() != term.casefold():
            return False
        if not self._find_whole_word:
            return True
        # Re-validate via document find at selection start (honours FindWholeWords).
        cursor = self.editor.textCursor()
        start = min(cursor.selectionStart(), cursor.selectionEnd())
        flags = self._find_flags(backward=False)
        found = self.editor.document().find(term, start, flags)
        return (
            not found.isNull()
            and found.selectionStart() == start
            and found.selectedText() == selected
        )

    def _replace_current(self) -> bool:
        """Replace the current selection if it matches the find term."""
        if self._replace_input is None:
            return False
        term = self._find_input.text()
        if not term:
            self._set_find_replace_status("kein Suchbegriff")
            return False
        if not self._selection_matches_find_term():
            if not self._find(backward=False):
                self._set_find_replace_status("keine Treffer")
                return False
            if not self._selection_matches_find_term():
                self._set_find_replace_status("keine Treffer")
                return False
        cursor = self.editor.textCursor()
        cursor.insertText(self._replace_input.text())
        self._set_find_replace_status("1 ersetzt")
        return True

    def _replace_and_find_next(self) -> None:
        if self._replace_current():
            self._find(backward=False)

    def _replace_all(self) -> None:
        if self._replace_input is None:
            return
        term = self._find_input.text()
        if not term:
            self._set_find_replace_status("kein Suchbegriff")
            return
        replacement = self._replace_input.text()
        flags = self._find_flags(backward=False)
        doc = self.editor.document()
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        count = 0
        pos = 0
        while True:
            found = doc.find(term, pos, flags)
            if found.isNull():
                break
            found.insertText(replacement)
            count += 1
            pos = found.position()
        cursor.endEditBlock()
        if count == 0:
            self._find_input.setStyleSheet("background-color: #fde2e1;")
            self._set_find_replace_status("keine Treffer")
        else:
            self._find_input.setStyleSheet("")
            self._set_find_replace_status(
                f"{count} ersetzt" if count != 1 else "1 ersetzt"
            )
