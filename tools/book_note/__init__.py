"""Buchnotiz: ein Textzettel, der an einem Buchprojekt hängt.

Nicht zu verwechseln mit ``tools/memo_pad`` — der ist absichtlich projektlos.
Diese Notiz gehört zu genau einem Buch, liegt in dessen ``bookconfig/`` und ist
deshalb auch für GrammarGraph erreichbar, das denselben Ordner schon für
``generator_classes.json`` benutzt.

    <Buch>/bookconfig/notiz.md      (reiner UTF-8-Text)

GUI-frei; der Qt-Dialog liegt in ``ui_qt/dialogs/book_note_dialog.py``.
"""

from __future__ import annotations

from tools.book_note.store import (
    BookNote,
    NOTE_RELATIVE_PATH,
    find_books,
    has_note,
    is_book_project,
    load,
    note_path,
    save,
)

__all__ = [
    "BookNote",
    "NOTE_RELATIVE_PATH",
    "find_books",
    "has_note",
    "is_book_project",
    "load",
    "note_path",
    "save",
]
