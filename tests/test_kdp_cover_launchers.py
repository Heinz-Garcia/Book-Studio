"""Phase-4 Launcher: Asset Manager + MD-Editor → KDP Cover-Designer."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def test_asset_manager_has_kdp_cover_launcher(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.asset_manager_dialog import AssetManagerQtDialog

    book = tmp_path / "book"
    book.mkdir()
    (book / "img").mkdir()
    (book / "content").mkdir()
    (book / "_quarto.yml").write_text("title: T\n", encoding="utf-8")

    class _Studio:
        current_book = str(book)

        def log(self, *a, **k):
            pass

    app = QApplication.instance() or QApplication([])
    dlg = AssetManagerQtDialog(None, _Studio())
    assert hasattr(dlg, "_btn_kdp_cover")
    assert dlg._btn_kdp_cover.text() == "KDP-Wrap…"
    assert "separat" in dlg._btn_kdp_cover.toolTip().lower() or "Upload" in dlg._btn_kdp_cover.toolTip()

    opened: list[object] = []

    def _fake_open(studio, parent, **kwargs):
        opened.append((studio, parent))
        return 0

    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover_dialog.open_kdp_cover_qt",
        _fake_open,
    )
    dlg._open_kdp_cover()
    assert len(opened) == 1
    assert opened[0][1] is dlg
    dlg.close()
    _ = app


def test_text_editor_has_kdp_cover_launcher(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.text_dialogs import TextEditorDialog

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "Deckblatt.md"
    path.write_text("---\ntitle: Deckblatt\n---\n\n# x\n", encoding="utf-8")
    (tmp_path / "_quarto.yml").write_text("title: Buch\n", encoding="utf-8")
    dlg = TextEditorDialog(None, path, book_path=tmp_path)
    assert hasattr(dlg, "_btn_kdp_cover")
    assert "KDP-Wrap" in dlg._btn_kdp_cover.text()
    tip = dlg._btn_kdp_cover.toolTip()
    assert "separat" in tip.lower() or "Deckblatt.md" in tip

    opened: list[object] = []

    def _fake_open(studio, parent, **kwargs):
        opened.append(studio)
        return 0

    monkeypatch.setattr(
        "ui_qt.dialogs.kdp_cover_dialog.open_kdp_cover_qt",
        _fake_open,
    )
    dlg._open_kdp_cover()
    assert len(opened) == 1
    assert isinstance(opened[0], SimpleNamespace)
    assert Path(opened[0].current_book) == tmp_path.resolve() or Path(
        opened[0].current_book
    ) == tmp_path
    dlg.close()
    _ = app


def test_asset_manager_pick_mode_accepts_selection(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.asset_manager_dialog import AssetManagerQtDialog

    book = tmp_path / "book"
    img = book / "img"
    img.mkdir(parents=True)
    cover = img / "cover.png"
    cover.write_bytes(b"\x89PNG\r\n\x1a\n")
    (book / "_quarto.yml").write_text("title: T\n", encoding="utf-8")

    class _Studio:
        current_book = str(book)

        def log(self, *a, **k):
            pass

    app = QApplication.instance() or QApplication([])
    dlg = AssetManagerQtDialog(
        None, _Studio(), pick_mode=True, pick_prompt="Cover wählen"
    )
    assert dlg._pick_mode is True
    assert dlg._btn_kdp_cover.isHidden()
    assert dlg._pick_accept_btn.isEnabled() is False

    dlg._selected_path = cover
    dlg._sync_pick_accept_enabled()
    assert dlg._pick_accept_btn.isEnabled() is True
    dlg._accept_pick()
    assert dlg.chosen_path == cover.resolve()
    dlg.close()
    _ = app
    _ = Qt
