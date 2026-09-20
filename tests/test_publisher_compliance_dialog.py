"""Tests für PublisherComplianceQtDialog / open_publisher_compliance_qt."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _make_book_with_pdf(tmp_path: Path, *, page_count: int = 1) -> Path:
    book = tmp_path / "Band"
    (book / "export" / "_book").mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        'isbn: "978-3-000000-00-0"\nproject:\n  type: book\n', encoding="utf-8"
    )

    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page()
    doc.save(book / "export" / "_book" / "out.pdf")
    doc.close()
    return book


def test_open_shows_warning_without_current_book():
    _app()
    from ui_qt.dialogs.publisher_compliance_dialog import open_publisher_compliance_qt

    class FakeStudio:
        current_book = None

    with patch("ui_qt.work_path_guidance.warn_need_book") as mock_warn:
        open_publisher_compliance_qt(FakeStudio(), None)
    assert mock_warn.called


def test_open_shows_info_when_no_pdf_rendered(tmp_path):
    _app()
    from ui_qt.dialogs.publisher_compliance_dialog import open_publisher_compliance_qt

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")

    class FakeStudio:
        current_book = book

    with patch(
        "ui_qt.work_path_guidance.prompt_redirect_stage", return_value=False
    ) as mock_redirect:
        open_publisher_compliance_qt(FakeStudio(), None)
    assert mock_redirect.called
    assert "PDF erzeugen" in mock_redirect.call_args.kwargs["go_label"]


def test_open_shows_warning_when_pymupdf_missing(tmp_path, monkeypatch):
    _app()
    from ui_qt.dialogs import publisher_compliance_dialog as mod

    book = tmp_path / "Band"
    (book / "export" / "_book").mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "export" / "_book" / "out.pdf").write_bytes(b"%PDF-1.4\n")

    class FakeStudio:
        current_book = book

    monkeypatch.setattr(
        "tools.live_preview.preview_render.newest_output_pdf",
        lambda _book: book / "export" / "_book" / "out.pdf",
    )

    import builtins
    import sys

    real_import = builtins.__import__

    def _block_fitz(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fitz":
            raise ImportError("No module named 'fitz'")
        return real_import(name, globals, locals, fromlist, level)

    # Cached module would skip __import__; remove so the guard runs again.
    monkeypatch.delitem(sys.modules, "fitz", raising=False)
    monkeypatch.setattr(builtins, "__import__", _block_fitz)

    marked: list[object] = []
    monkeypatch.setattr(
        "services.work_path.mark_freigabe_seen",
        lambda *a, **k: marked.append((a, k)),
    )

    messages: list[str] = []

    def _warn(parent, title, text):  # noqa: ANN001
        messages.append(text)
        return 0

    with patch("PySide6.QtWidgets.QMessageBox.warning", side_effect=_warn):
        mod.open_publisher_compliance_qt(FakeStudio(), None)

    assert messages, "fehlendes PyMuPDF muss eine Warnung zeigen"
    assert "PyMuPDF" in messages[0]
    assert marked == [], "Gate I darf ohne geöffneten Dialog nicht als gesehen gelten"


def test_open_builds_dialog_with_issue_rows(tmp_path, monkeypatch):
    _app()
    from ui_qt.dialogs import publisher_compliance_dialog as mod

    book = _make_book_with_pdf(tmp_path)  # ISBN-SSOT gesetzt, aber leere PDF ohne Text -> Mismatch

    class FakeStudio:
        current_book = book

    captured = {}
    marked: list[object] = []
    monkeypatch.setattr(
        "services.work_path.mark_freigabe_seen",
        lambda *a, **k: marked.append((a, k)),
    )

    def fake_show(dlg, registry):
        captured["rows"] = dlg.table.rowCount()
        captured["ids"] = [
            dlg.table.item(r, 1).text() for r in range(dlg.table.rowCount())
        ]
        assert dlg.parent() is None
        assert dlg.isModal() is False
        return dlg

    with patch.object(mod, "show_autonomous_window", fake_show):
        mod.open_publisher_compliance_qt(FakeStudio(), None)

    assert "isbn-consistency" in captured["ids"]
    assert len(marked) == 1, "Gate I nach erfolgreichem Öffnen als gesehen markieren"
