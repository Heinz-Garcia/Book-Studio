"""Tests für Publish-Readiness-Navigation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.publish_readiness.navigation import jump_to_issue, resolve_issue_line


def test_resolve_issue_line_prefers_issue_detail():
    studio = SimpleNamespace(doctor_issue_line_registry={"kap.md": 99})
    issue = {"path": "kap.md", "line_number": 5}
    assert resolve_issue_line(studio, issue) == 5


def test_resolve_issue_line_falls_back_to_registry():
    studio = SimpleNamespace(doctor_issue_line_registry={"kap.md": 12})
    issue = {"path": "kap.md"}
    assert resolve_issue_line(studio, issue) == 12


def test_jump_to_issue_calls_open_log_target(tmp_path):
    book = tmp_path / "Band"
    book.mkdir()
    md = book / "kap.md"
    md.write_text("# Test\n", encoding="utf-8")

    calls: list[tuple[str, int | None]] = []

    def fake_open(rel_path, target_line=None):
        calls.append((rel_path, target_line))
        return "break"

    studio = SimpleNamespace(
        current_book=book,
        doctor_issue_line_registry={"kap.md": 3},
        open_log_target=fake_open,
    )
    ok = jump_to_issue(studio, {"path": "kap.md", "line_number": 7})
    assert ok is True
    assert calls == [("kap.md", 7)]


def test_jump_to_issue_without_path_returns_false(monkeypatch):
    import ui_hooks
    monkeypatch.setattr(ui_hooks.messagebox, "showinfo", lambda *a, **k: None)
    studio = SimpleNamespace(current_book=Path("."), open_log_target=lambda *a, **k: None)
    assert jump_to_issue(studio, {"path": "—", "message": "Pool"}) is False


def test_dialog_wires_jump_on_double_click(monkeypatch, tmp_path):
    """Doppelklick / Zur Stelle… muss jump_to_issue aufrufen."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QTableWidgetItem

    from ui_qt.dialogs.publish_readiness_dialog import PublishReadinessQtDialog

    QApplication.instance() or QApplication([])
    book = tmp_path / "Band"
    book.mkdir()
    (book / "kap.md").write_text("# x\n", encoding="utf-8")
    calls: list[dict] = []
    monkeypatch.setattr(
        "ui_qt.dialogs.publish_readiness_dialog.jump_to_issue",
        lambda studio, issue, parent=None: calls.append(issue) or True,
    )
    studio = SimpleNamespace(current_book=book)
    issues = [{"severity": "blocker", "path": "kap.md", "message": "Fehler", "owner": "GG"}]
    dlg = PublishReadinessQtDialog(
        None, studio, analysis={"is_healthy": False}, issues=issues
    )
    dlg.table.setCurrentCell(0, 0)
    dlg._zur_stelle()
    assert calls == [issues[0]]
    dlg.table.setItem(0, 0, QTableWidgetItem("blocker"))
    dlg.table.itemDoubleClicked.emit(dlg.table.item(0, 0))
    assert len(calls) == 2
    dlg.close()
