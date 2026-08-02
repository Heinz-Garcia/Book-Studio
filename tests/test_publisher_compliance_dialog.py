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
    (book / "_quarto.yml").write_text('isbn: "978-3-000000-00-0"\nproject:\n  type: book\n', encoding="utf-8")

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

    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
        open_publisher_compliance_qt(FakeStudio(), None)
    assert mock_warning.called


def test_open_shows_info_when_no_pdf_rendered(tmp_path):
    _app()
    from ui_qt.dialogs.publisher_compliance_dialog import open_publisher_compliance_qt

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")

    class FakeStudio:
        current_book = book

    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        open_publisher_compliance_qt(FakeStudio(), None)
    assert mock_info.called


def test_open_builds_dialog_with_issue_rows(tmp_path):
    _app()
    from ui_qt.dialogs.publisher_compliance_dialog import (
        PublisherComplianceQtDialog,
        open_publisher_compliance_qt,
    )

    book = _make_book_with_pdf(tmp_path)  # ISBN-SSOT gesetzt, aber leere PDF ohne Text -> Mismatch

    class FakeStudio:
        current_book = book

    captured = {}

    def fake_exec(self):
        captured["rows"] = self.table.rowCount()
        captured["ids"] = [self.table.item(r, 1).text() for r in range(self.table.rowCount())]
        return 0

    with patch.object(PublisherComplianceQtDialog, "exec", fake_exec):
        open_publisher_compliance_qt(FakeStudio(), None)

    assert "isbn-consistency" in captured["ids"]
