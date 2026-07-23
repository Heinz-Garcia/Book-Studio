"""Phase-5-Tests: Plugin-Dispatch und Qt-Dialog-Konstruktion."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_plugin_dispatch_known_names():
    from ui_qt import plugin_dispatch as pd

    # Nur prüfen, dass Runner-Tabelle die Haupt-Plugins kennt
    import inspect

    src = inspect.getsource(pd.run_plugin_qt)
    for name in (
        "mapping_manager",
        "generated_books",
        "publish_readiness",
        "skeleton_populate",
        "skeleton_editor",
    ):
        assert name in src


def test_mapping_manager_qt_constructs(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    book = tmp_path / "B"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "bookconfig").mkdir()

    app = QApplication.instance() or QApplication([])
    studio = SimpleNamespace(current_book=book, log=lambda *_a, **_k: None)
    dlg = MappingManagerQtDialog(None, studio)
    assert "Mapping Manager" in dlg.windowTitle()
    dlg.close()
    _ = app


def test_generated_books_qt_constructs(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.generated_books_dialog import GeneratedBooksQtDialog

    app = QApplication.instance() or QApplication([])
    studio = SimpleNamespace(current_book=None, books=[], get_recent_books=lambda: [])
    dlg = GeneratedBooksQtDialog(None, studio)
    assert "Generierte" in dlg.windowTitle()
    dlg.close()
    _ = app
