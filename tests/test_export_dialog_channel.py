"""Tests für den Ziel-Kanal-Dropdown im Qt-Export-Dialog (KDP-Interior)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.distribution.book_store import (
    CHANNEL_KDP_PAPERBACK,
    set_chapter_excluded,
    set_kdp_paperback,
)


def _make_dialog(monkeypatch, book_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.export_dialog import ExportDialog

    QApplication.instance() or QApplication([])
    return ExportDialog(None, ["Standard"], book_path=book_path)


def test_channel_combo_hides_kdp_option_when_channel_disabled(monkeypatch, tmp_path: Path):
    book = tmp_path / "book"
    book.mkdir()
    dialog = _make_dialog(monkeypatch, book)
    labels = [dialog.channel_combo.itemText(i) for i in range(dialog.channel_combo.count())]
    assert labels == ["Standard"]
    assert dialog._selected_render_channel_id() == ""


def test_channel_combo_offers_kdp_option_when_channel_enabled(monkeypatch, tmp_path: Path):
    book = tmp_path / "book"
    book.mkdir()
    set_kdp_paperback(book, True)
    dialog = _make_dialog(monkeypatch, book)
    labels = [dialog.channel_combo.itemText(i) for i in range(dialog.channel_combo.count())]
    assert "Amazon KDP (Interior, ohne Cover-Seiten)" in labels

    dialog.channel_combo.setCurrentText("Amazon KDP (Interior, ohne Cover-Seiten)")
    assert dialog._selected_render_channel_id() == CHANNEL_KDP_PAPERBACK


def test_channel_hint_shows_excluded_chapters(monkeypatch, tmp_path: Path):
    book = tmp_path / "book"
    book.mkdir()
    set_kdp_paperback(book, True)
    set_chapter_excluded(book, CHANNEL_KDP_PAPERBACK, "content/Deckblatt.md", True)
    dialog = _make_dialog(monkeypatch, book)

    dialog.channel_combo.setCurrentText("Amazon KDP (Interior, ohne Cover-Seiten)")
    assert "content/Deckblatt.md" in dialog.channel_hint.text()


def test_channel_hint_prompts_when_nothing_excluded(monkeypatch, tmp_path: Path):
    book = tmp_path / "book"
    book.mkdir()
    set_kdp_paperback(book, True)
    dialog = _make_dialog(monkeypatch, book)

    dialog.channel_combo.setCurrentText("Amazon KDP (Interior, ohne Cover-Seiten)")
    assert "Rechtsklick" in dialog.channel_hint.text()


def test_out_dir_gets_channel_suffix(monkeypatch, tmp_path: Path):
    book = tmp_path / "book"
    book.mkdir()
    set_kdp_paperback(book, True)
    dialog = _make_dialog(monkeypatch, book)

    standard_dir = dialog._out_dir()
    dialog.channel_combo.setCurrentText("Amazon KDP (Interior, ohne Cover-Seiten)")
    kdp_dir = dialog._out_dir()

    assert standard_dir != kdp_dir
    assert kdp_dir is not None and kdp_dir.name.endswith(f"_{CHANNEL_KDP_PAPERBACK}")


def test_confirm_result_includes_render_channel(monkeypatch, tmp_path: Path):
    book = tmp_path / "book"
    book.mkdir()
    set_kdp_paperback(book, True)
    dialog = _make_dialog(monkeypatch, book)
    dialog.channel_combo.setCurrentText("Amazon KDP (Interior, ohne Cover-Seiten)")
    dialog._confirm()
    assert dialog.result["render_channel"] == CHANNEL_KDP_PAPERBACK
