"""Tests für Batch B8: Studio-Adapter und Service-Stubs.

Stellt sicher, dass:
- `StudioAdapter` die gängigen Manager→Studio-Delegations bündelt.
- Alle 6 Service-Stubs (`services/*_service.py`) importierbar sind und
  ihre dokumentierte Public-API haben.
- `ExportManager._current_book` über den Adapter läuft und weiterhin
  Fallback-Verhalten zeigt, wenn die `get_*`-Methoden fehlen.

Referenz: .doc/refactoring-master.md, Batch B8.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.studio_adapter import StudioAdapter
from services.workspace_service import WorkspaceService
from services.book_session_service import BookSessionService
from services.render_service import RenderService
from services.diagnostics_service import DiagnosticsService
from services.backup_service import BackupService
from services.ui_state_service import UiStateService


# --- StudioAdapter ----------------------------------------------------------


def test_adapter_reads_current_book_via_getter():
    studio = SimpleNamespace(get_current_book=lambda: Path("/tmp/book"))
    adapter = StudioAdapter(studio)
    assert adapter.current_book == Path("/tmp/book")


def test_adapter_falls_back_to_attribute():
    studio = SimpleNamespace(current_book=Path("/tmp/book"))
    adapter = StudioAdapter(studio)
    assert adapter.current_book == Path("/tmp/book")


def test_adapter_returns_none_when_neither_getter_nor_attr():
    studio = SimpleNamespace()
    adapter = StudioAdapter(studio)
    assert adapter.current_book is None


def test_adapter_log_delegates():
    seen = []
    studio = SimpleNamespace(log=lambda msg, lvl: seen.append((msg, lvl)))
    StudioAdapter(studio).log("hi", "warning")
    assert seen == [("hi", "warning")]


def test_adapter_title_for_path_uses_registry_fallback():
    studio = SimpleNamespace(
        title_registry={"foo.md": "Foo Title"},
    )
    adapter = StudioAdapter(studio)
    assert adapter.title_for_path("foo.md") == "Foo Title"
    assert adapter.title_for_path("missing.md") == "missing.md"


def test_adapter_set_last_export_options_falls_back_to_attribute():
    studio = SimpleNamespace()
    StudioAdapter(studio).set_last_export_options({"format": "typst"})
    assert studio.last_export_options == {"format": "typst"}


def test_adapter_save_project_returns_false_when_missing():
    studio = SimpleNamespace()
    assert StudioAdapter(studio).save_project() is False


# --- Phase 2: Coverage-Lücken für StudioAdapter ----------------------------
# Tests für Property-Branches, Fallback-Pfade und Methoden, die bisher
# nicht direkt abgedeckt waren.


def test_adapter_current_profile_name_via_getter():
    studio = SimpleNamespace(get_current_profile_name=lambda: "main")
    assert StudioAdapter(studio).current_profile_name == "main"


def test_adapter_current_profile_name_fallback_attribute():
    studio = SimpleNamespace(current_profile_name="alt")
    assert StudioAdapter(studio).current_profile_name == "alt"


def test_adapter_current_profile_name_none_when_missing():
    assert StudioAdapter(SimpleNamespace()).current_profile_name is None


def test_adapter_available_templates_via_getter():
    studio = SimpleNamespace(get_available_templates=lambda: ["T1", "T2"])
    assert StudioAdapter(studio).available_templates == ["T1", "T2"]


def test_adapter_available_templates_getter_returns_none():
    """Wenn der Getter `None` oder Falsy liefert, fällt der Adapter auf `["Standard"]` zurück."""
    studio = SimpleNamespace(get_available_templates=lambda: None)
    assert StudioAdapter(studio).available_templates == ["Standard"]


def test_adapter_available_templates_fallback_attribute():
    studio = SimpleNamespace(available_templates=["A", "B"])
    assert StudioAdapter(studio).available_templates == ["A", "B"]


def test_adapter_available_templates_default_when_missing():
    assert StudioAdapter(SimpleNamespace()).available_templates == ["Standard"]


def test_adapter_last_export_options_via_getter():
    studio = SimpleNamespace(get_last_export_options=lambda: {"format": "pdf"})
    assert StudioAdapter(studio).last_export_options == {"format": "pdf"}


def test_adapter_last_export_options_getter_returns_none():
    """Wenn der Getter `None` oder `{}` liefert, fällt der Adapter auf `{}` zurück."""
    studio = SimpleNamespace(get_last_export_options=lambda: None)
    assert StudioAdapter(studio).last_export_options == {}


def test_adapter_last_export_options_fallback_attribute():
    studio = SimpleNamespace(last_export_options={"k": 1})
    assert StudioAdapter(studio).last_export_options == {"k": 1}


def test_adapter_title_registry_returns_copy():
    """`title_registry` darf keine Referenz auf das Studio-Objekt durchreichen."""
    original = {"foo.md": "Foo"}
    studio = SimpleNamespace(title_registry=original)
    out = StudioAdapter(studio).title_registry
    assert out == original
    # Kopie, nicht dieselbe Dict-Referenz
    out["bar.md"] = "Bar"
    assert "bar.md" not in original


def test_adapter_title_registry_missing():
    assert StudioAdapter(SimpleNamespace()).title_registry == {}


def test_adapter_root_returns_studio_root():
    studio = SimpleNamespace(root="ROOT_OBJ")
    assert StudioAdapter(studio).root == "ROOT_OBJ"


def test_adapter_root_missing():
    assert StudioAdapter(SimpleNamespace()).root is None


def test_adapter_log_no_method_is_silent():
    """Wenn das Studio keine `log`-Methode hat, darf der Adapter nicht crashen."""
    StudioAdapter(SimpleNamespace()).log("hi")  # kein Fehler


def test_adapter_schedule_ui_via_studio():
    seen = []
    studio = SimpleNamespace(schedule_ui=lambda cb, delay=0: seen.append(delay) or "X")
    out = StudioAdapter(studio).schedule_ui(lambda: None, delay=10)
    assert out == "X"
    assert seen == [10]


def test_adapter_schedule_ui_falls_back_to_root_after():
    """Ohne `schedule_ui` am Studio, aber mit Tk-`root` mit `after`."""
    called = []
    root = SimpleNamespace(after=lambda delay, cb: called.append((delay, cb)) or "after-id")
    studio = SimpleNamespace(root=root)
    out = StudioAdapter(studio).schedule_ui(lambda: None, delay=5)
    assert out == "after-id"
    assert called and called[0][0] == 5


def test_adapter_schedule_ui_falls_back_to_direct_call():
    """Ohne `schedule_ui` und ohne Tk-`root.after`: Callback wird direkt aufgerufen."""
    called = []
    adapter = StudioAdapter(SimpleNamespace())
    out = adapter.schedule_ui(lambda: called.append(1), delay=0)
    assert out is None
    assert called == [1]


def test_adapter_update_status_via_studio():
    seen = []
    studio = SimpleNamespace(update_status=lambda text, fg: seen.append((text, fg)))
    StudioAdapter(studio).update_status("OK", "green")
    assert seen == [("OK", "green")]


def test_adapter_update_status_falls_back_to_status_widget():
    seen = []
    status = SimpleNamespace(config=lambda text, fg: seen.append((text, fg)))
    studio = SimpleNamespace(status=status)
    StudioAdapter(studio).update_status("X", "red")
    assert seen == [("X", "red")]


def test_adapter_copy_text_via_studio():
    seen = []
    studio = SimpleNamespace(copy_text_to_clipboard=lambda text: seen.append(text))
    StudioAdapter(studio).copy_text_to_clipboard("hello")
    assert seen == ["hello"]


def test_adapter_copy_text_falls_back_to_root_clipboard():
    cleared, appended = [], []

    class _FakeRoot:
        def clipboard_clear(self):
            cleared.append(True)

        def clipboard_append(self, text):
            appended.append(text)

    studio = SimpleNamespace(root=_FakeRoot())
    StudioAdapter(studio).copy_text_to_clipboard("payload")
    assert cleared == [True]
    assert appended == ["payload"]


def test_adapter_copy_text_without_root_is_silent():
    """Ohne Studio-`copy_text_to_clipboard` und ohne `root`: kein Fehler."""
    StudioAdapter(SimpleNamespace()).copy_text_to_clipboard("x")


def test_adapter_copy_text_swallows_tk_errors():
    """Tk-Fehler beim Clipboard-Zugriff werden still übergehen."""

    class _BoomRoot:
        def clipboard_clear(self):
            raise RuntimeError("tk-error")

        def clipboard_append(self, text):
            raise RuntimeError("tk-error")

    studio = SimpleNamespace(root=_BoomRoot())
    StudioAdapter(studio).copy_text_to_clipboard("x")  # kein Crash


def test_adapter_title_for_path_via_getter():
    studio = SimpleNamespace(get_title_for_path=lambda p: f"title-for-{p}")
    assert StudioAdapter(studio).title_for_path("foo.md") == "title-for-foo.md"


def test_adapter_set_last_export_options_via_setter():
    seen = []
    studio = SimpleNamespace(set_last_export_options=lambda s: seen.append(s))
    StudioAdapter(studio).set_last_export_options({"format": "html"})
    assert seen == [{"format": "html"}]


def test_adapter_persist_app_state_via_studio():
    seen = []
    studio = SimpleNamespace(persist_app_state=lambda: seen.append(True))
    StudioAdapter(studio).persist_app_state()
    assert seen == [True]


def test_adapter_persist_app_state_missing_is_silent():
    """Ohne `persist_app_state` am Studio: kein Fehler."""
    StudioAdapter(SimpleNamespace()).persist_app_state()


def test_adapter_get_tree_data_for_engine_via_getter():
    studio = SimpleNamespace(get_tree_data_for_engine=lambda: [{"id": 1}, {"id": 2}])
    data = list(StudioAdapter(studio).get_tree_data_for_engine())
    assert data == [{"id": 1}, {"id": 2}]


def test_adapter_get_tree_data_for_engine_missing_returns_empty():
    assert list(StudioAdapter(SimpleNamespace()).get_tree_data_for_engine()) == []


def test_adapter_run_doctor_preflight_via_studio():
    studio = SimpleNamespace(
        run_doctor_preflight=lambda label, emit_success_log=False: (True, [label, emit_success_log])
    )
    ok, payload = StudioAdapter(studio).run_doctor_preflight("ctx", emit_success_log=True)
    assert ok is True
    assert payload == ["ctx", True]


def test_adapter_run_doctor_preflight_fallback_returns_false_none():
    """Ohne `run_doctor_preflight` am Studio: `(False, None)`."""
    ok, payload = StudioAdapter(SimpleNamespace()).run_doctor_preflight("ctx")
    assert ok is False
    assert payload is None


# --- Service-Stubs ----------------------------------------------------------


def test_workspace_service_basic():
    """Smoke: WorkspaceService antwortet auf die drei Pflicht-Aufrufe.

    Die echte Discovery-Logik wird in `tests/test_workspace_service.py`
    separat gegen ein `tmp_path` getestet, weil `rglob("_quarto.yml")`
    ein echtes Dateisystem braucht.
    """
    studio = SimpleNamespace(base_path=Path("/x"), projects_root_path=Path("/x"))
    svc = WorkspaceService(studio)
    # Ohne `read_config` fällt get_projects_root_path auf `base_path` zurück.
    assert svc.get_projects_root_path() == Path("/x")
    # `discover_projects` braucht ein echtes Wurzelverzeichnis; ohne eines
    # liefert sie eine leere Liste. Wird in test_workspace_service.py getestet.
    assert svc.discover_projects() == []
    # `is_within_project` ist ein reiner relativer Pfad-Vergleich.
    assert svc.is_within_project(Path("/x/b1/foo.md")) is True
    assert svc.is_within_project(Path("/y/foo.md")) is False


def test_book_session_service_basic():
    studio = SimpleNamespace(
        current_book=Path("/b"),
        current_profile_name="default",
        yaml_engine=object(),
    )
    svc = BookSessionService(studio)
    assert svc.current_book == Path("/b")
    assert svc.current_profile_name == "default"
    assert svc.profile_path("default") == Path("/b/bookconfig/default.json")
    assert svc.profile_path("") is None


def test_book_session_service_no_current_book():
    studio = SimpleNamespace(current_book=None, current_profile_name=None, yaml_engine=None)
    svc = BookSessionService(studio)
    assert svc.current_book is None
    assert svc.profile_path("x") is None


def test_render_service_calls_exporter():
    called = []
    exporter = SimpleNamespace(run_quarto_render=lambda: called.append(True) or True)
    svc = RenderService(exporter)
    assert svc.run_render() is True
    assert called == [True]


def test_render_service_no_method():
    exporter = SimpleNamespace()
    svc = RenderService(exporter)
    assert svc.run_render() is False


def test_diagnostics_service_preflight():
    studio = SimpleNamespace(
        run_doctor_preflight=lambda label, emit_success_log=False: (True, {"ok": 1})
    )
    svc = DiagnosticsService(studio)
    ok, payload = svc.run_preflight("ctx")
    assert ok is True
    assert payload == {"ok": 1}


def test_backup_service_structure_backup():
    seen = []
    studio = SimpleNamespace(
        current_book=Path("/b"),
        backup_mgr=SimpleNamespace(create_structure_backup=lambda data: seen.append(data) or "bk"),
    )
    svc = BackupService(studio)
    name = svc.create_structure_backup([{"a": 1}])
    assert name == "bk"
    assert seen == [[{"a": 1}]]


def test_backup_service_sanitizer_dir():
    studio = SimpleNamespace(current_book=Path("/b/mybook"))
    svc = BackupService(studio)
    assert svc.get_sanitizer_backup_dir() == Path("/b/_Sanitizer_Backups_mybook")


def test_ui_state_service_search_text():
    from tkinter import StringVar
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display für Tk")
    try:
        var = StringVar(value="hello")
        studio = SimpleNamespace(search_var=var)
        svc = UiStateService(studio)
        assert svc.search_text == "hello"
        svc.invalidate_content_search_cache()  # smoke-call
    finally:
        root.destroy()


# --- Phase 2: Coverage-Lücken für UiStateService ---------------------------
# Tests für die Exception-Fallbacks in den Properties und für den
# Cache-Invalidator mit und ohne Studio-Methode.


def test_ui_state_service_search_text_returns_empty_on_exception():
    """Wenn `search_var.get()` wirft (z. B. Tcl-Error), liefert die Property
    einen leeren String."""

    class _BoomVar:
        def get(self):
            raise RuntimeError("tcl-error")

    studio = SimpleNamespace(search_var=_BoomVar())
    assert UiStateService(studio).search_text == ""


def test_ui_state_service_search_text_handles_missing_var():
    """Wenn `search_var` gar nicht existiert, liefert die Property einen leeren String."""
    assert UiStateService(SimpleNamespace()).search_text == ""


def test_ui_state_service_file_state_filter_default():
    from tkinter import StringVar
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display für Tk")
    try:
        var = StringVar(value="Alle")
        studio = SimpleNamespace(file_state_filter_var=var)
        assert UiStateService(studio).file_state_filter == "Alle"
    finally:
        root.destroy()


def test_ui_state_service_file_state_filter_custom_value():
    from tkinter import StringVar
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display für Tk")
    try:
        var = StringVar(value="Fehlende Bilder")
        studio = SimpleNamespace(file_state_filter_var=var)
        assert UiStateService(studio).file_state_filter == "Fehlende Bilder"
    finally:
        root.destroy()


def test_ui_state_service_file_state_filter_returns_alle_on_exception():
    """Wenn `file_state_filter_var.get()` wirft, fällt der Service auf `Alle` zurück."""

    class _BoomVar:
        def get(self):
            raise RuntimeError("tcl-error")

    studio = SimpleNamespace(file_state_filter_var=_BoomVar())
    assert UiStateService(studio).file_state_filter == "Alle"


def test_ui_state_service_file_state_filter_handles_missing_var():
    """Wenn `file_state_filter_var` gar nicht existiert, liefert der Service `Alle`."""
    assert UiStateService(SimpleNamespace()).file_state_filter == "Alle"


def test_ui_state_service_invalidate_cache_via_studio():
    """Wenn das Studio eine `invalidate_content_search_cache`-Methode hat,
    wird sie vom Service aufgerufen."""
    seen = []
    studio = SimpleNamespace(invalidate_content_search_cache=lambda: seen.append(True))
    UiStateService(studio).invalidate_content_search_cache()
    assert seen == [True]


def test_ui_state_service_invalidate_cache_missing_method_is_silent():
    """Ohne `invalidate_content_search_cache` am Studio: kein Fehler."""
    UiStateService(SimpleNamespace()).invalidate_content_search_cache()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
