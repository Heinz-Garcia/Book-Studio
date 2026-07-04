"""Tests fuer Phase 2 / Schritt 2.3c-Mini: RenderService.execute_render.

Deckt die synchrone Render-Orchestrierung im Service ab:

- Pre-Log ueber `after_cb(0, ...)`
- Subprocess-Aufruf ueber injiziertes `run_safe_render`-Callable
- Pfad-Auswahl: abort_on_colon, success, failure
- Finalize-Log-Aufrufe (Status-Werte + Returncodes)
- `on_failure`-Callback im Failure-Pfad
- Rueckgabewert: `(returncode, aborted_on_colon_warning)`

Threading bleibt in `ExportManager`; die Service-Methode ist
rein synchron und ohne I/O.
"""

from __future__ import annotations

import pytest

from services.render_service import (
    RENDER_STATUS_ABORTED_ON_COLON,
    RENDER_STATUS_FAILED,
    RENDER_STATUS_SUCCESS,
    RenderService,
)


# --- Helpers ---------------------------------------------------------------


def _make_recorder():
    """Baut ein Dict zum Aufzeichnen der Callback-Aufrufe.

    Plus passende Callables, die in den Service gesteckt werden.
    """
    recorder = {
        "log": [],
        "after": [],
        "set_status": [],
        "finalize": [],
        "handle_success": [],
        "on_failure": [],
        "run_safe_render_args": None,
    }

    def log_cb(message, level):
        recorder["log"].append((message, level))

    def after_cb(delay, callback):
        recorder["after"].append((delay, callback))
        # Im Render-Pfad wird der Callback direkt ausgefuehrt; in
        # Tests emulieren wir das, um die Pre-Log-Nachricht zu
        # erfassen.
        callback()

    def run_safe_render(target_fmt, profile_name=None, extra_format_options=None):
        recorder["run_safe_render_args"] = (
            target_fmt,
            profile_name,
            extra_format_options,
        )
        return recorder.get("run_safe_render_result", (0, False))

    def finalize_render_log(status, primary_returncode=None, fallback_returncode=None):
        recorder["finalize"].append((status, primary_returncode, fallback_returncode))

    def handle_render_success(target_fmt):
        recorder["handle_success"].append(target_fmt)

    def on_failure(returncode):
        recorder["on_failure"].append(returncode)

    return recorder, {
        "log_cb": log_cb,
        "after_cb": after_cb,
        "run_safe_render": run_safe_render,
        "finalize_render_log": finalize_render_log,
        "handle_render_success": handle_render_success,
        "on_failure": on_failure,
    }


# --- Erfolgs-Pfad ---------------------------------------------------------


def test_execute_render_success_path():
    recorder, cbs = _make_recorder()
    recorder["run_safe_render_result"] = (0, False)
    return_code, aborted = RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **cbs,
    )
    assert return_code == 0
    assert aborted is False
    # Finalize-Log: success
    assert len(recorder["finalize"]) == 1
    status, primary_rc, fallback_rc = recorder["finalize"][0]
    assert status == RENDER_STATUS_SUCCESS
    assert primary_rc == 0
    assert fallback_rc is None
    # handle_render_success wurde gerufen
    assert recorder["handle_success"] == ["html"]
    # on_failure wurde NICHT gerufen
    assert recorder["on_failure"] == []
    # Pre-Log wurde geschrieben
    assert any(
        "Render startet" in msg and level == "dim"
        for msg, level in recorder["log"]
    )


def test_execute_render_passes_profile_and_extra_options():
    recorder, cbs = _make_recorder()
    recorder["run_safe_render_result"] = (0, False)
    RenderService.execute_render(
        target_fmt="pdf",
        profile_name="MyProfile",
        extra_format_options={"pdf": {"keep-tex": True}},
        **cbs,
    )
    target_fmt, profile_name, extra_opts = recorder["run_safe_render_args"]
    assert target_fmt == "pdf"
    assert profile_name == "MyProfile"
    assert extra_opts == {"pdf": {"keep-tex": True}}


# --- Failure-Pfad --------------------------------------------------------


def test_execute_render_failure_path():
    recorder, cbs = _make_recorder()
    recorder["run_safe_render_result"] = (3, False)
    return_code, aborted = RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **cbs,
    )
    assert return_code == 3
    assert aborted is False
    # Finalize-Log: failed
    assert len(recorder["finalize"]) == 1
    status, primary_rc, _fallback = recorder["finalize"][0]
    assert status == RENDER_STATUS_FAILED
    assert primary_rc == 3
    # handle_render_success wurde NICHT gerufen
    assert recorder["handle_success"] == []
    # on_failure wurde gerufen
    assert recorder["on_failure"] == [3]
    # Fehler-Log wurde geschrieben
    assert any("Code 3" in msg and level == "error" for msg, level in recorder["log"])


def test_execute_render_failure_calls_on_failure_with_returncode():
    recorder, cbs = _make_recorder()
    recorder["run_safe_render_result"] = (7, False)
    RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **cbs,
    )
    assert recorder["on_failure"] == [7]


# --- Abort-on-Colon-Pfad --------------------------------------------------


def test_execute_render_abort_on_colon_path():
    recorder, cbs = _make_recorder()
    recorder["run_safe_render_result"] = (None, True)  # type: ignore[arg-type]
    return_code, aborted = RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **cbs,
    )
    assert aborted is True
    # Finalize-Log: aborted
    assert len(recorder["finalize"]) == 1
    status, primary_rc, _fallback = recorder["finalize"][0]
    assert status == RENDER_STATUS_ABORTED_ON_COLON
    # weder handle_render_success noch on_failure wurden gerufen
    assert recorder["handle_success"] == []
    assert recorder["on_failure"] == []


# --- Reihenfolge-Invariante ----------------------------------------------


def test_execute_render_pre_log_happens_before_run_safe_render():
    """Der Pre-Log soll *vor* dem Subprocess-Aufruf erfolgen."""
    order = []
    recorder, cbs = _make_recorder()
    recorder["run_safe_render_result"] = (0, False)

    def log_cb(message, level):
        recorder["log"].append((message, level))
        order.append(f"log:{level}")

    def after_cb(delay, callback):
        recorder["after"].append((delay, callback))
        order.append("after:0")
        callback()
        order.append("after:done")

    def run_safe_render(*args, **kwargs):
        order.append("run_safe_render")
        return 0, False

    # Uebrige Callbacks beibehalten, aber die drei relevanten ersetzen.
    new_cbs = dict(cbs)
    new_cbs["log_cb"] = log_cb
    new_cbs["after_cb"] = after_cb
    new_cbs["run_safe_render"] = run_safe_render

    RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **new_cbs,
    )
    # Pre-Log via after_cb(0, ...) erscheint *vor* run_safe_render
    assert order.index("after:0") < order.index("run_safe_render")
    assert order.count("run_safe_render") == 1


def test_execute_render_finalize_happens_after_run_safe_render():
    """Finalize wird *nach* dem Subprocess-Aufruf gerufen."""
    recorder, cbs = _make_recorder()
    order = []

    def run_safe_render(*args, **kwargs):
        order.append("run")
        return 0, False

    def finalize_render_log(status, **kwargs):
        recorder["finalize"].append((status, kwargs.get("primary_returncode")))
        order.append(f"finalize:{status}")

    new_cbs = dict(cbs)
    new_cbs["run_safe_render"] = run_safe_render
    new_cbs["finalize_render_log"] = finalize_render_log

    RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **new_cbs,
    )
    assert order[0] == "run"
    assert order[1] == f"finalize:{RENDER_STATUS_SUCCESS}"


def test_execute_render_success_calls_handle_after_finalize():
    """Reihenfolge: Finalize-Log *vor* handle_render_success."""
    recorder, cbs = _make_recorder()
    order = []

    def finalize_render_log(status, **kwargs):
        order.append(f"finalize:{status}")

    def handle_render_success(target_fmt):
        order.append(f"handle:{target_fmt}")

    new_cbs = dict(cbs)
    new_cbs["finalize_render_log"] = finalize_render_log
    new_cbs["handle_render_success"] = handle_render_success

    RenderService.execute_render(
        target_fmt="html",
        profile_name=None,
        extra_format_options=None,
        **new_cbs,
    )
    assert order[0] == f"finalize:{RENDER_STATUS_SUCCESS}"
    assert order[1] == "handle:html"


# --- Konstanten ----------------------------------------------------------


def test_render_status_constants_have_expected_values():
    """Sanity-Check: Konstantenwerte, die der Service an `finalize_render_log` uebergibt."""
    assert RENDER_STATUS_SUCCESS == "success"
    assert RENDER_STATUS_FAILED == "failed"
    assert RENDER_STATUS_ABORTED_ON_COLON == "aborted_on_first_colon_warning"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
