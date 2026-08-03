"""Tests für BookProjectsQtDialog — insbesondere die ISBN-Spalte/den
"ISBN…"-Button (Top-Level-`isbn:`-Feld in `_quarto.yml`, siehe
tools.publisher_compliance.metadata)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


def _make_book(tmp_path: Path, name: str, *, isbn: str | None = None) -> Path:
    book = tmp_path / name
    book.mkdir(parents=True)
    text = "project:\n  type: book\n"
    if isbn:
        text = f'isbn: "{isbn}"\n' + text
    (book / "_quarto.yml").write_text(text, encoding="utf-8")
    return book


def _make_dialog(monkeypatch, tmp_path, books):
    """`books`: Liste von (name, isbn_or_None) -- baut BookInfo-Fixtures und
    patcht list_books/list_content_roots direkt im Dialogmodul, ohne echte
    app_config/Content-Root-Discovery zu brauchen."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import book_projects_dialog as mod

    root = tmp_path / "root"
    root.mkdir()
    infos = []
    for name, isbn in books:
        book_path = _make_book(root, name, isbn=isbn)
        infos.append(mod.BookInfo(path=book_path, name=name, root=root))

    monkeypatch.setattr(mod, "list_books", lambda repo=None: infos)
    monkeypatch.setattr(mod, "list_content_roots", lambda repo=None: [root])

    app = QApplication.instance() or QApplication([])
    dlg = mod.BookProjectsQtDialog(None, None)
    return app, dlg, mod, infos


def _find_book_item(dlg, name: str):
    for i in range(dlg.books_tree.topLevelItemCount()):
        group = dlg.books_tree.topLevelItem(i)
        for j in range(group.childCount()):
            child = group.child(j)
            if child.text(0) == name or child.text(1) == name:
                return child
    return None


def test_isbn_column_shows_value_when_set(monkeypatch, tmp_path):
    from ui_qt.dialogs.book_projects_dialog import _COL_ISBN

    _app, dlg, _mod, _infos = _make_dialog(
        monkeypatch, tmp_path, [("BandA", "978-3-000000-00-0")]
    )
    item = _find_book_item(dlg, "BandA")
    assert item is not None
    assert item.text(_COL_ISBN) == "978-3-000000-00-0"
    dlg.close()


def test_isbn_column_shows_placeholder_when_missing(monkeypatch, tmp_path):
    from ui_qt.dialogs.book_projects_dialog import _COL_ISBN, _NO_ISBN_PLACEHOLDER

    _app, dlg, _mod, _infos = _make_dialog(monkeypatch, tmp_path, [("BandB", None)])
    item = _find_book_item(dlg, "BandB")
    assert item is not None
    assert item.text(_COL_ISBN) == _NO_ISBN_PLACEHOLDER
    dlg.close()


def test_edit_isbn_requires_selection(monkeypatch, tmp_path):
    _app, dlg, mod, _infos = _make_dialog(monkeypatch, tmp_path, [("BandC", None)])

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._edit_isbn()
        mock_box.information.assert_called_once()
        args = mock_box.information.call_args[0]
        assert "Bitte ein Buch" in args[2]
    dlg.close()


def test_edit_isbn_writes_new_value(monkeypatch, tmp_path):
    from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml

    _app, dlg, mod, infos = _make_dialog(monkeypatch, tmp_path, [("BandD", None)])
    item = _find_book_item(dlg, "BandD")
    dlg.books_tree.setCurrentItem(item)

    with patch.object(mod, "QInputDialog") as mock_input:
        mock_input.getText.return_value = ("978-3-444444-44-4", True)
        dlg._edit_isbn()

    assert read_isbn_from_quarto_yml(infos[0].path / "_quarto.yml") == "978-3-444444-44-4"
    dlg.close()


def test_edit_isbn_clears_existing_value(monkeypatch, tmp_path):
    from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml

    _app, dlg, mod, infos = _make_dialog(
        monkeypatch, tmp_path, [("BandE", "978-3-555555-55-5")]
    )
    item = _find_book_item(dlg, "BandE")
    dlg.books_tree.setCurrentItem(item)

    with patch.object(mod, "QInputDialog") as mock_input:
        mock_input.getText.return_value = ("", True)
        dlg._edit_isbn()

    assert read_isbn_from_quarto_yml(infos[0].path / "_quarto.yml") is None
    dlg.close()


def test_edit_isbn_cancelled_leaves_value_untouched(monkeypatch, tmp_path):
    from tools.publisher_compliance.metadata import read_isbn_from_quarto_yml

    _app, dlg, mod, infos = _make_dialog(
        monkeypatch, tmp_path, [("BandF", "978-3-666666-66-6")]
    )
    item = _find_book_item(dlg, "BandF")
    dlg.books_tree.setCurrentItem(item)

    with patch.object(mod, "QInputDialog") as mock_input:
        mock_input.getText.return_value = ("978-3-000000-00-0", False)  # ok=False
        dlg._edit_isbn()

    assert read_isbn_from_quarto_yml(infos[0].path / "_quarto.yml") == "978-3-666666-66-6"
    dlg.close()
