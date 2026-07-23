"""Tests für Publish-Readiness-Navigation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
