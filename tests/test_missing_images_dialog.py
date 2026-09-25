"""Fehlende-Bilder-Dialog: nicht-modal, Editor springt zur Zeile."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_missing_images_dialog_is_non_modal_and_opens_editor_at_line(
    tmp_path: Path, monkeypatch
):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import missing_images_dialog as mid
    from ui_qt.dialogs import text_dialogs as td

    app = QApplication.instance() or QApplication([])
    book = tmp_path / "Book"
    (book / "content").mkdir(parents=True)
    md = book / "content" / "Kap.md"
    md.write_text("# Kap\n\nText\n\n![](img/fehlt.png)\n", encoding="utf-8")

    mid._active_missing_images.clear()
    mid.show_missing_images_for_path(None, book, "content/Kap.md")
    assert len(mid._active_missing_images) == 1
    dlg = mid._active_missing_images[0]
    assert dlg.isModal() is False
    assert dlg.isVisible() is True

    seen: dict = {}
    monkeypatch.setattr(td, "open_text_editor", lambda *a, **k: seen.update(k))
    dlg._list.setCurrentRow(0)
    dlg._open_editor()
    assert seen["initial_line"] == 5
    dlg.close()
    _ = app
