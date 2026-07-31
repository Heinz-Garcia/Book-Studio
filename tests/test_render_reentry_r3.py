"""Tests für R3: Re-Entrancy-Sperre in `export_manager.py::run_quarto_render()`.

Quelle: implementation_plan.md, Abschnitt 3.3 (R3).

Diese Tests validieren, dass:
1. `run_quarto_render()` einen zweiten Aufruf während eines laufenden
   Render-Prozesses abweist (Guard mit messagebox).
2. Das `_render_running`-Flag korrekt zurückgesetzt wird, auch wenn der
   Preflight fehlschlägt (vor Thread-Start).
3. Das `_render_running`-Flag im finally-Block des Worker-Threads
   zurückgesetzt wird (nach erfolgreichem Lauf).

Folgt dem Muster aus test_export_manager_regression.py (_FakeStudio).
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from export_manager import ExportManager


class _FakeStatus:
    def __init__(self):
        self.last = None

    def config(self, **kwargs):
        self.last = kwargs


class _FakeStudio:
    """Minimales Fake-Studio für ExportManager-Tests."""

    def __init__(self):
        self.current_book = object()
        self.root = mock.Mock()
        self.available_templates = ["Standard"]
        self.last_export_options = {}
        self.status = _FakeStatus()
        self.logged = []
        self.preflight_calls = []

    def run_doctor_preflight(self, context_label, emit_success_log=False):
        self.preflight_calls.append((context_label, emit_success_log))
        return False, {"error_count": 1}

    def log(self, message, level="info"):
        self.logged.append((message, level))

    def persist_app_state(self):
        pass


# --- Test 1: Guard stoppt bei _render_running=True -------------------


def test_run_quarto_render_guards_against_reentrancy(monkeypatch) -> None:
    """R3-Test 1: Guard greift bei _render_running=True.

    Wenn `_render_running` bereits True ist, sollte die Methode sofort
    mit messagebox.showinfo() abbrechen, ohne bis zur Preflight vorzudringen.
    """
    studio = _FakeStudio()
    manager = ExportManager(studio)
    manager._render_running = True  # <-- Already running!

    # Mock messagebox.showinfo
    mock_showinfo = mock.Mock()
    monkeypatch.setattr("export_manager.messagebox.showinfo", mock_showinfo)

    manager.run_quarto_render()

    # Verification:
    # 1. messagebox.showinfo should have been called
    assert mock_showinfo.called, "messagebox.showinfo sollte aufgerufen worden sein"

    # 2. preflight should NOT have been called (Guard abfangen vor Preflight)
    assert (
        studio.preflight_calls == []
    ), "Preflight sollte NICHT aufgerufen werden, wenn Guard greift"

    # 3. Flag should still be True
    assert manager._render_running is True


# --- Test 2: Flag reset on preflight failure ----------------------------


def test_render_flag_reset_on_preflight_failure(monkeypatch) -> None:
    """R3-Test 2: Flag wird zurückgesetzt, wenn Preflight fehlschlägt.

    Wenn `run_doctor_preflight()` False zurückgibt, muss `_render_running`
    auf False zurückgesetzt werden (dispatched bleibt False im try/finally).
    """
    studio = _FakeStudio()
    manager = ExportManager(studio)

    # ExportDialog wurde entfernt; export_manager nutzt jetzt ui_hooks.ask_export_options.
    # Bei Preflight-Fehler wird ask_export_options nie erreicht — kein Mock nötig.
    # Sicherheits-Patch für den Fall, dass er doch erreicht wird:
    monkeypatch.setattr("ui_hooks.ask_export_options", lambda *_a, **_k: None)

    # Mock threading.Thread to NOT actually start
    mock_thread_class = mock.Mock()
    monkeypatch.setattr("export_manager.threading.Thread", mock_thread_class)

    manager.run_quarto_render()

    # Verification: Flag should be False (reset in finally because dispatched=False)
    assert (
        manager._render_running is False
    ), "Flag sollte False sein nach Preflight-Fehlschlag (try/finally)"

    # threading.Thread should NOT have been started
    assert not mock_thread_class.called, "Thread sollte NICHT gestartet werden bei Preflight-Fehler"


# --- Test 3: Flag reset after successful run ---------------------------


def test_render_flag_reset_after_successful_run(tmp_path: Path, monkeypatch) -> None:
    """R3-Test 3: Flag wird im finally zurückgesetzt nach erfolgreichem Lauf.

    Wenn der Render erfolgreich läuft und beendet wird, muss
    `_render_running` im finally-Block der render_thread() zurückgesetzt werden.
    """
    book = tmp_path / "book"
    book.mkdir()
    (book / "processed" / "content").mkdir(parents=True, exist_ok=True)

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

        def extract_title_from_md(self, _path):
            return "Dummy Titel"

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0}

        def persist_app_state(self):
            pass

        def save_project(self, **_kwargs):
            pass

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    # Mock threading.Thread to execute target immediately
    class FakeThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    # ExportDialog wurde entfernt; export_manager nutzt jetzt ui_hooks.ask_export_options.
    monkeypatch.setattr(
        "ui_hooks.ask_export_options",
        lambda *_a, **_k: {"format": "typst", "template": "Standard"},
    )

    # Mock PreProcessor
    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            pass

        def prepare_render_environment(self, tree):
            return tree

    monkeypatch.setattr("export_manager.PreProcessor", FakePreProcessor)

    # Mock subprocess.Popen
    class FakePopen:
        def __init__(self, *_args, **_kwargs):
            self.stdout = []
            self.returncode = 0

        def wait(self):
            return self.returncode

    monkeypatch.setattr("export_manager.subprocess.Popen", FakePopen)

    # Mock RenderService.execute_render
    mock_render_service = mock.Mock()
    monkeypatch.setattr("export_manager._RenderService.execute_render", mock_render_service)

    # Mock threading
    monkeypatch.setattr("export_manager.threading.Thread", FakeThread)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    # Verification: Flag should be False (reset in finally block of render_thread)
    assert (
        manager._render_running is False
    ), "Flag sollte False sein nach erfolgreichem Render (finally im render_thread)"


# --- Test 4: Flag reset on dialog cancellation ----


def test_render_flag_reset_on_dialog_cancel(monkeypatch) -> None:
    """R3-Test 4: Flag wird zurückgesetzt wenn Dialog abgebrochen wird.

    Wenn der ExportDialog None zurückgibt (abgebrochen), muss
    `_render_running` False bleiben (dispatched=False in try/finally).
    """
    studio = _FakeStudio()
    manager = ExportManager(studio)

    # ExportDialog wurde entfernt; export_manager nutzt jetzt ui_hooks.ask_export_options.
    # Abbruch = None zurückgeben.
    monkeypatch.setattr("ui_hooks.ask_export_options", lambda *_a, **_k: None)

    # Mock threading to ensure it's not started
    mock_thread_class = mock.Mock()
    monkeypatch.setattr("export_manager.threading.Thread", mock_thread_class)

    manager.run_quarto_render()

    # Verification: Flag should be False
    assert (
        manager._render_running is False
    ), "Flag sollte False sein nach Dialog-Abbruch"

    # Thread should NOT have been started
    assert not mock_thread_class.called


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
