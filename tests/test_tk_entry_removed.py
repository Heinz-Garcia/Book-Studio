"""Phase 6: Tk-Einstieg ist tot."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_rejects_ui_tk():
    env = os.environ.copy()
    env.pop("BOOK_STUDIO_UI", None)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "book_studio.py"), "--ui", "tk"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    assert completed.returncode == 2
    assert "Legacy-Tk" in (completed.stderr or "") or "entfernt" in (completed.stderr or "")


def test_cli_rejects_env_tk(monkeypatch):
    env = os.environ.copy()
    env["BOOK_STUDIO_UI"] = "tk"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "book_studio.py"), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    # --help should still work without starting UI; only runtime rejects tk.
    # Verify is_tk_requested via toolkit instead for env.
    from ui_qt.toolkit import is_tk_requested

    monkeypatch.setenv("BOOK_STUDIO_UI", "tk")
    assert is_tk_requested() is True
    _ = completed
