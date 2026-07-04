"""Regression: echte BookStudio↔DiagnosticsService-Verdrahtung.

Die Default-Suite hatte ~600 grüne Tests, obwohl `run_quarto_render` nach
einem grünen Vorabcheck crashte: `DiagnosticsService` ruft
`on_status(text, fg_key)` auf, aber BookStudio übergab die Werte falsch an
`status.config()`.

Unit-Tests für `DiagnosticsService` mocken `on_status` nur als Recorder.
`ExportManager`-Tests mocken `run_doctor_preflight` komplett weg. Beides
testet nie den produktiven Tkinter-Pfad.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest

from book_doctor import BookDoctor
from book_studio import BookStudio
from services.diagnostics_service import DiagnosticsService


@pytest.fixture
def tk_label():
    root = tk.Tk()
    root.withdraw()
    label = tk.Label(root)
    yield label
    root.destroy()


def test_bookstudio_on_diagnostics_status_updates_real_tk_label(tk_label) -> None:
    studio = SimpleNamespace(status=tk_label)

    BookStudio._on_diagnostics_status(
        studio,
        "Render-Vorabcheck: keine kritischen Befunde",
        "success",
    )

    assert "keine kritischen Befunde" in tk_label.cget("text")
    assert tk_label.cget("fg")


def test_run_full_health_check_with_production_status_callback(tk_label, tmp_path: Path) -> None:
    """End-to-End durch den Service mit dem echten BookStudio-Status-Callback."""
    book = tmp_path / "book"
    book.mkdir()
    (book / "index.md").write_text(
        '---\ntitle: "Start"\ndescription: "Start"\nstatus: "bookstudio"\n---\n\n',
        encoding="utf-8",
    )

    studio = SimpleNamespace(
        current_book=book,
        doctor=BookDoctor(book, {"index.md": "Start"}),
        title_registry={"index.md": "Start"},
        doctor_issue_registry={},
        doctor_issue_line_registry={},
        status=tk_label,
        tree_refreshed=False,
    )
    studio._on_diagnostics_status = BookStudio._on_diagnostics_status.__get__(
        studio, BookStudio
    )

    svc = DiagnosticsService(
        studio,
        on_status=studio._on_diagnostics_status,
        on_refresh_tree=lambda: setattr(studio, "tree_refreshed", True),
        on_select_first_issue=lambda: None,
        on_log_analysis=lambda *_args: None,
    )

    is_healthy, analysis = svc.run_full_health_check(
        "Render-Vorabcheck",
        all_paths=[],
        tree_child_count=20,
        emit_success_log=False,
    )

    assert is_healthy is True
    assert analysis["warning_count"] == 1
    assert "keine kritischen Befunde" in tk_label.cget("text")
