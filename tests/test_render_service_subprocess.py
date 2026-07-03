"""Tests fuer Phase 2 / Schritt 2.3c: RenderService.run_safe_render.

Deckt die Subprocess-Kapselung im Service ab:

- Service delegiert an `popen_factory` (Default `subprocess.Popen`)
- `on_log_line` wird fuer jede nicht-leere stdout-Zeile aufgerufen
- `on_colon_warning + should_abort + has_structural_colons` fuehrt
  zu `on_abort_requested` + `popen_killer(proc)` + Rueckgabe
  `(rc, True)`
- Bei fehlendem `safe_script`: `(SAFE_RENDER_RC_MISSING_SCRIPT, False)`
- `proc.wait()` wird aufgerufen; `returncode` wird zurueckgegeben
- Stream ohne `.stdout` (None) ist ok
- `on_safe_command_built` wird nach argv-Bau aufgerufen
- `book` und `profile_name` fliessen in `build_safe_render_command`
  ein (smoke-check ueber `on_safe_command_built`)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.render_service import (
    SAFE_RENDER_RC_MISSING_SCRIPT,
    SAFE_RENDER_RC_STREAM_ERROR,
    RenderService,
)


# --- Mock-Subprocess --------------------------------------------------------


class _MockPopen:
    """Minimaler Popen-Stub.

    - `stdout`: Iterable von Strings (raw, mit Newline)
    - `returncode`: Integer
    - `terminate()`: setzt `terminated = True`
    - `wait()`: setzt `waited = True`
    """

    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self.returncode = returncode
        self.terminated = False
        self.waited = False

    def terminate(self):
        self.terminated = True

    def wait(self):
        self.waited = True


def _popen_factory_for(lines, returncode=0):
    """Factory, die _MockPopen mit den gegebenen lines baut."""
    instances = []

    def _factory(*args, **kwargs):
        proc = _MockPopen(lines, returncode=returncode)
        instances.append(proc)
        return proc

    _factory.instances = instances  # type: ignore[attr-defined]
    return _factory


# --- Tests ------------------------------------------------------------------


def test_run_safe_render_missing_script(tmp_path):
    """Wenn safe_script nicht existiert: Returncode 2, aborted=False."""
    log_lines = []

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=tmp_path / "does_not_exist.py",
        on_log_line=log_lines.append,
    )

    assert rc == SAFE_RENDER_RC_MISSING_SCRIPT
    assert aborted is False
    assert len(log_lines) == 1
    assert "Fallback-Skript" in log_lines[0]


def test_run_safe_render_streams_lines(tmp_path):
    """Jede nicht-leere stdout-Zeile landet in `on_log_line`."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    popen = _popen_factory_for(
        ["line 1\n", "   \n", "line 2\n", ""],
        returncode=0,
    )
    log_lines = []

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=safe_script,
        on_log_line=log_lines.append,
        popen_factory=popen,
    )

    assert rc == 0
    assert aborted is False
    # Leere Zeilen und Whitespace-only werden gefiltert.
    assert log_lines == ["line 1", "line 2"]
    assert popen.instances[0].waited is True


def test_run_safe_render_aborts_on_colon_warning(tmp_path):
    """on_colon_warning + should_abort + has_structural -> Abbruch."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    popen = _popen_factory_for(
        ["warning: ::: hint\n", "more output\n"],
        returncode=99,
    )
    log_lines = []
    abort_called = []

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=safe_script,
        on_log_line=log_lines.append,
        on_colon_warning=lambda line: ":::" in line,
        should_abort_on_colon_warning=lambda: True,
        has_structural_colon_occurrences=lambda: True,
        on_abort_requested=lambda: abort_called.append(True),
        popen_factory=popen,
    )

    assert aborted is True
    assert rc == 99
    assert popen.instances[0].terminated is True
    assert abort_called == [True]
    # Nach Abbruch werden keine weiteren Zeilen verarbeitet.
    assert log_lines == ["warning: ::: hint"]


def test_run_safe_render_no_abort_when_conditions_not_met(tmp_path):
    """on_colon_warning True, aber should_abort False -> kein Abbruch."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    popen = _popen_factory_for(
        ["warning: ::: hint\n", "ok\n"],
        returncode=0,
    )
    log_lines = []
    abort_called = []

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=safe_script,
        on_log_line=log_lines.append,
        on_colon_warning=lambda line: ":::" in line,
        should_abort_on_colon_warning=lambda: False,
        has_structural_colon_occurrences=lambda: True,
        on_abort_requested=lambda: abort_called.append(True),
        popen_factory=popen,
    )

    assert aborted is False
    assert rc == 0
    assert abort_called == []
    assert log_lines == ["warning: ::: hint", "ok"]


def test_run_safe_render_handles_none_stdout(tmp_path):
    """Subprocess ohne .stdout wird ohne Crash akzeptiert."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    proc = SimpleNamespace(stdout=None, returncode=0, waited=False)
    proc.wait = lambda: setattr(proc, "waited", True)

    def _factory(*args, **kwargs):
        return proc

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=safe_script,
        popen_factory=_factory,
    )

    assert rc == 0
    assert aborted is False
    assert proc.waited is True


def test_run_safe_render_safe_command_callback_receives_argv(tmp_path):
    """on_safe_command_built erhaelt die volle argv-Liste."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    popen = _popen_factory_for([], returncode=0)
    captured = []

    def _on_cmd(cmd):
        captured.append(list(cmd))

    RenderService().run_safe_render(
        target_fmt="typst-pdf",
        profile_name="buch-profil",
        extra_format_options={"typst-pdf": {"toc": True}},
        book=tmp_path,
        safe_script=safe_script,
        executable=tmp_path / "python.exe",
        on_safe_command_built=_on_cmd,
        popen_factory=popen,
    )

    assert len(captured) == 1
    argv = captured[0]
    assert "--to" in argv
    assert "typst-pdf" in argv
    assert "--profile-name" in argv
    assert "buch-profil" in argv
    assert "--extra-format-options-json" in argv


def test_run_safe_render_killer_oserror_swallowed(tmp_path):
    """OSError beim Killen wird verschluckt, Abbruch wird trotzdem markiert."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    proc = _MockPopen(["warning: ::: hint\n"], returncode=0)

    def _bad_killer(p):
        raise OSError("simulated kill failure")

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=safe_script,
        on_colon_warning=lambda _l: True,
        should_abort_on_colon_warning=lambda: True,
        has_structural_colon_occurrences=lambda: True,
        popen_factory=lambda *a, **k: proc,
        popen_killer=_bad_killer,
    )

    assert aborted is True


def test_run_safe_render_default_popen_killer_calls_terminate(tmp_path):
    """Default-Popen-Killer ruft proc.terminate() auf."""
    safe_script = tmp_path / "quarto_render_safe.py"
    safe_script.write_text("# stub", encoding="utf-8")

    proc = _MockPopen(["warning: ::: hint\n"], returncode=0)

    rc, aborted = RenderService().run_safe_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        book=tmp_path,
        safe_script=safe_script,
        on_colon_warning=lambda _l: True,
        should_abort_on_colon_warning=lambda: True,
        has_structural_colon_occurrences=lambda: True,
        popen_factory=lambda *a, **k: proc,
    )

    assert aborted is True
    assert proc.terminated is True
