"""Tests fuer Phase 2 / Schritt 2.4a: DiagnosticsService.

Deckt die *reinen Daten-Pfade* des Buch-Doktors ab:
- Issue-Registry-Management (set/clear/has)
- Reine Navigations-Logik (paths_in_tree_order, pick_next_issue_path)
- Convenience-Accessoren (issues_for_path, first_issue_line_for_path)

Tree-Manipulation, Status- und Log-Calls bleiben in `BookStudio`
(Schritt 2.4b).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.diagnostics_service import DiagnosticsService


# --- Helpers ---------------------------------------------------------------


def _make_studio(issue_reg=None, line_reg=None) -> SimpleNamespace:
    return SimpleNamespace(
        doctor_issue_registry=issue_reg if issue_reg is not None else {},
        doctor_issue_line_registry=line_reg if line_reg is not None else {},
    )


# --- set_issues_from_analysis ---------------------------------------------


def test_set_issues_writes_both_registries():
    studio = _make_studio()
    svc = DiagnosticsService(studio)
    svc.set_issues_from_analysis(
        {
            "issues_by_path": {"a.md": ["Issue 1"]},
            "issue_first_line_by_path": {"a.md": 42},
        }
    )
    assert studio.doctor_issue_registry == {"a.md": ["Issue 1"]}
    assert studio.doctor_issue_line_registry == {"a.md": 42}


def test_set_issues_handles_missing_keys():
    """Wenn das Analysis-Dict leer ist oder Keys fehlen, gibt es leere Dicts."""
    studio = _make_studio()
    svc = DiagnosticsService(studio)
    svc.set_issues_from_analysis({})
    assert studio.doctor_issue_registry == {}
    assert studio.doctor_issue_line_registry == {}


def test_set_issues_handles_none_analysis():
    """Wenn `None` uebergeben wird, gibt es leere Dicts (kein Crash)."""
    studio = _make_studio()
    svc = DiagnosticsService(studio)
    svc.set_issues_from_analysis(None)  # type: ignore[arg-type]
    assert studio.doctor_issue_registry == {}


def test_set_issues_overwrites_existing():
    """Ein neuer Analysis-Lauf ueberschreibt das alte Ergebnis komplett."""
    studio = _make_studio(
        issue_reg={"old.md": ["alt"]},
        line_reg={"old.md": 1},
    )
    svc = DiagnosticsService(studio)
    svc.set_issues_from_analysis(
        {
            "issues_by_path": {"new.md": ["neu"]},
            "issue_first_line_by_path": {"new.md": 2},
        }
    )
    assert studio.doctor_issue_registry == {"new.md": ["neu"]}
    assert "old.md" not in studio.doctor_issue_registry


# --- clear_issues ---------------------------------------------------------


def test_clear_issues_resets_both_registries():
    studio = _make_studio(
        issue_reg={"a.md": ["x"]},
        line_reg={"a.md": 10},
    )
    svc = DiagnosticsService(studio)
    svc.clear_issues()
    assert studio.doctor_issue_registry == {}
    assert studio.doctor_issue_line_registry == {}


def test_clear_issues_idempotent():
    studio = _make_studio()
    svc = DiagnosticsService(studio)
    svc.clear_issues()
    svc.clear_issues()  # kein Fehler


# --- has_issues -----------------------------------------------------------


def test_has_issues_true_when_registry_non_empty():
    studio = _make_studio(issue_reg={"a.md": ["x"]})
    svc = DiagnosticsService(studio)
    assert svc.has_issues() is True


def test_has_issues_false_when_empty():
    studio = _make_studio()
    svc = DiagnosticsService(studio)
    assert svc.has_issues() is False


def test_has_issues_true_when_values_are_empty_lists():
    """Wenn die Registry ein Mapping mit leeren Listen enthaelt, ist
    `has_issues` True. Die Semantik prueft das Dict, nicht die Inhalte;
    Aufrufer, die "wirkliche" Issues wollen, muessen `issues_for_path`
    bemuehen."""
    studio = _make_studio(issue_reg={"a.md": []})
    svc = DiagnosticsService(studio)
    assert svc.has_issues() is True


# --- issues_for_path ------------------------------------------------------


def test_issues_for_path_returns_issues():
    studio = _make_studio(issue_reg={"a.md": ["x", "y"]})
    svc = DiagnosticsService(studio)
    assert svc.issues_for_path("a.md") == ["x", "y"]


def test_issues_for_path_returns_empty_for_unknown_path():
    studio = _make_studio(issue_reg={"a.md": ["x"]})
    svc = DiagnosticsService(studio)
    assert svc.issues_for_path("b.md") == []


def test_issues_for_path_handles_none_value_in_registry():
    """Wenn der Registry-Eintrag `None` ist, gibt es eine leere Liste."""
    studio = _make_studio(issue_reg={"a.md": None})
    svc = DiagnosticsService(studio)
    assert svc.issues_for_path("a.md") == []


# --- first_issue_line_for_path -------------------------------------------


def test_first_issue_line_returns_int():
    studio = _make_studio(line_reg={"a.md": 42})
    svc = DiagnosticsService(studio)
    assert svc.first_issue_line_for_path("a.md") == 42


def test_first_issue_line_returns_none_when_missing():
    studio = _make_studio()
    svc = DiagnosticsService(studio)
    assert svc.first_issue_line_for_path("a.md") is None


# --- paths_in_tree_order -------------------------------------------------


def test_paths_in_tree_order_preserves_order_of_all_paths():
    all_paths = ["a.md", "b.md", "c.md", "d.md"]
    registry = {"c.md": ["x"], "a.md": ["y"]}
    assert DiagnosticsService.paths_in_tree_order(all_paths, registry) == ["a.md", "c.md"]


def test_paths_in_tree_order_empty_registry():
    assert DiagnosticsService.paths_in_tree_order(["a.md", "b.md"], {}) == []


def test_paths_in_tree_order_empty_paths():
    assert DiagnosticsService.paths_in_tree_order([], {"a.md": ["x"]}) == []


def test_paths_in_tree_order_no_match():
    assert DiagnosticsService.paths_in_tree_order(["a.md"], {"b.md": ["x"]}) == []


def test_paths_in_tree_order_accepts_iterable():
    """Funktioniert mit beliebigem Iterable, nicht nur Liste."""
    all_paths = iter(["a.md", "b.md"])
    registry = {"a.md": ["x"]}
    assert DiagnosticsService.paths_in_tree_order(all_paths, registry) == ["a.md"]


# --- pick_next_issue_path ------------------------------------------------


def test_pick_next_simple_step_forward():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "a.md", 1) == "b.md"


def test_pick_next_simple_step_backward():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "b.md", -1) == "a.md"


def test_pick_next_wraps_around_forward():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "c.md", 1) == "a.md"


def test_pick_next_wraps_around_backward():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "a.md", -1) == "c.md"


def test_pick_next_with_unknown_current_path_step_positive():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "z.md", 1) == "a.md"


def test_pick_next_with_unknown_current_path_step_negative():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "z.md", -1) == "c.md"


def test_pick_next_with_none_current_path_step_positive():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, None, 1) == "a.md"


def test_pick_next_with_none_current_path_step_negative():
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, None, -1) == "c.md"


def test_pick_next_empty_paths_returns_none():
    assert DiagnosticsService.pick_next_issue_path([], "x.md", 1) is None
    assert DiagnosticsService.pick_next_issue_path([], None, -1) is None


def test_pick_next_single_path_always_returns_it():
    paths = ["only.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "only.md", 1) == "only.md"
    assert DiagnosticsService.pick_next_issue_path(paths, "only.md", -1) == "only.md"
    assert DiagnosticsService.pick_next_issue_path(paths, None, 1) == "only.md"


def test_pick_next_step_zero_behaves_like_step_one():
    """B-Fix (Code-Review 2026-07-03): der Docstring verspricht 'step = 0
    verhaelt sich wie step = 1', der Code liess den Index vorher aber bei
    step = 0 unveraendert (kein Fortschritt)."""
    paths = ["a.md", "b.md", "c.md"]
    assert DiagnosticsService.pick_next_issue_path(paths, "a.md", 0) == "b.md"
    assert DiagnosticsService.pick_next_issue_path(paths, "c.md", 0) == "a.md"
    assert DiagnosticsService.pick_next_issue_path(paths, "z.md", 0) == "a.md"
    assert DiagnosticsService.pick_next_issue_path(paths, None, 0) == "a.md"


# --- pick_first_issue_path -----------------------------------------------


def test_pick_first_returns_first_in_tree_order():
    all_paths = ["a.md", "b.md", "c.md"]
    registry = {"c.md": ["x"], "a.md": ["y"]}
    assert DiagnosticsService.pick_first_issue_path(all_paths, registry) == "a.md"


def test_pick_first_returns_none_when_empty():
    assert DiagnosticsService.pick_first_issue_path([], {}) is None
    assert DiagnosticsService.pick_first_issue_path(["a.md"], {}) is None


# --- run_full_health_check (Phase 2 / Schritt 2.4b) ---------------------


def _make_doctor(analysis):
    """Hilfs-Studio mit `doctor`, der `analyze_health` simuliert."""
    return SimpleNamespace(doctor=SimpleNamespace(analyze_health=lambda *a, **k: analysis))


def test_run_full_health_check_no_book_returns_false_none():
    studio = SimpleNamespace(current_book=None, doctor=SimpleNamespace())
    calls = {"status": 0, "log": 0, "refresh": 0, "select": 0, "log_an": 0}
    svc = DiagnosticsService(
        studio,
        on_status=lambda *a: calls.__setitem__("status", calls["status"] + 1),
        on_log=lambda *a: calls.__setitem__("log", calls["log"] + 1),
        on_refresh_tree=lambda: calls.__setitem__("refresh", calls["refresh"] + 1),
        on_select_first_issue=lambda: calls.__setitem__("select", calls["select"] + 1),
        on_log_analysis=lambda *a: calls.__setitem__("log_an", calls["log_an"] + 1),
    )
    is_healthy, analysis = svc.run_full_health_check(
        "X", ["a.md"], 3, emit_success_log=False
    )
    assert is_healthy is False
    assert analysis is None
    assert calls == {"status": 0, "log": 0, "refresh": 0, "select": 0, "log_an": 0}


def test_run_full_health_check_no_doctor_returns_false_none():
    studio = SimpleNamespace(current_book=Path("c:/book"), doctor=None)
    svc = DiagnosticsService(studio)
    is_healthy, analysis = svc.run_full_health_check("X", ["a.md"], 3)
    assert is_healthy is False
    assert analysis is None


def test_run_full_health_check_healthy_calls_status_success():
    analysis = {"is_healthy": True, "error_count": 0, "warning_count": 0}
    studio = _make_doctor(analysis)
    studio.current_book = Path("c:/book")
    status_calls = []
    log_calls = []
    refresh_calls = []
    select_calls = []
    svc = DiagnosticsService(
        studio,
        on_status=lambda t, fg: status_calls.append((t, fg)),
        on_log=lambda m, lv: log_calls.append((m, lv)),
        on_refresh_tree=lambda: refresh_calls.append(True),
        on_select_first_issue=lambda: select_calls.append(True),
        on_log_analysis=lambda *a: None,
    )
    is_healthy, out = svc.run_full_health_check(
        "Buch-Doktor", ["a.md", "b.md"], 2, emit_success_log=False
    )
    assert is_healthy is True
    assert out is analysis
    assert len(status_calls) == 1
    assert status_calls[0] == ("Buch-Doktor: keine kritischen Befunde", "success")
    assert refresh_calls == [True]
    assert select_calls == [True]
    assert log_calls == []  # emit_success_log=False, has_findings=False


def test_run_full_health_check_emit_success_log_triggers_log_analysis():
    analysis = {"is_healthy": True, "error_count": 0, "warning_count": 0}
    studio = _make_doctor(analysis)
    studio.current_book = Path("c:/book")
    log_an_calls = []
    svc = DiagnosticsService(
        studio,
        on_log_analysis=lambda an, lbl: log_an_calls.append((an, lbl)),
    )
    is_healthy, _ = svc.run_full_health_check(
        "Buch-Doktor", ["a.md"], 1, emit_success_log=True
    )
    assert is_healthy is True
    assert log_an_calls == [(analysis, "Buch-Doktor")]


def test_run_full_health_check_warnings_trigger_log_analysis():
    analysis = {"is_healthy": True, "error_count": 0, "warning_count": 2}
    studio = _make_doctor(analysis)
    studio.current_book = Path("c:/book")
    log_an_calls = []
    status_calls = []
    svc = DiagnosticsService(
        studio,
        on_status=lambda t, fg: status_calls.append((t, fg)),
        on_log_analysis=lambda an, lbl: log_an_calls.append((an, lbl)),
    )
    is_healthy, _ = svc.run_full_health_check("Vorabcheck", ["a.md"], 1)
    assert is_healthy is True
    assert len(log_an_calls) == 1
    assert status_calls[0] == ("Vorabcheck: keine kritischen Befunde", "success")


def test_run_full_health_check_errors_set_status_danger():
    analysis = {
        "is_healthy": False,
        "error_count": 3,
        "warning_count": 1,
        "issues_by_path": {"a.md": [1, 2, 3]},
    }
    studio = _make_doctor(analysis)
    studio.current_book = Path("c:/book")
    status_calls = []
    log_an_calls = []
    svc = DiagnosticsService(
        studio,
        on_status=lambda t, fg: status_calls.append((t, fg)),
        on_log_analysis=lambda *a: log_an_calls.append(a),
    )
    is_healthy, out = svc.run_full_health_check("Buch-Doktor", ["a.md"], 1)
    assert is_healthy is False
    assert out is analysis
    assert status_calls == [("Buch-Doktor: 3 kritische Befunde - siehe Log", "danger")]
    assert len(log_an_calls) == 1


def test_run_full_health_check_writes_registries():
    analysis = {
        "is_healthy": False,
        "error_count": 1,
        "warning_count": 0,
        "issues_by_path": {"a.md": ["X"]},
        "issue_first_line_by_path": {"a.md": 42},
    }
    studio = _make_doctor(analysis)
    studio.current_book = Path("c:/book")
    svc = DiagnosticsService(studio)
    svc.run_full_health_check("X", ["a.md"], 1)
    assert studio.doctor_issue_registry == {"a.md": ["X"]}
    assert studio.doctor_issue_line_registry == {"a.md": 42}


def test_run_full_health_check_default_callbacks_are_noop():
    analysis = {"is_healthy": True, "error_count": 0, "warning_count": 0}
    studio = _make_doctor(analysis)
    studio.current_book = Path("c:/book")
    svc = DiagnosticsService(studio)  # alle Callbacks = noop
    # Darf nicht werfen.
    is_healthy, out = svc.run_full_health_check("X", ["a.md"], 1)
    assert is_healthy is True
    assert out is analysis


# --- analyze_single_file (Phase 2 / Schritt 2.4b) -----------------------


def _make_single_file_doctor(analysis, current_book=Path("c:/book")):
    return SimpleNamespace(
        doctor=SimpleNamespace(analyze_health=lambda *a, **k: analysis),
        current_book=current_book,
        title_registry={},
        doctor_issue_registry={},
        doctor_issue_line_registry={},
    )


def test_analyze_single_file_no_saved_path():
    studio = _make_single_file_doctor({})
    svc = DiagnosticsService(studio)
    had, issues, valid = svc.analyze_single_file(None)
    assert (had, issues, valid) == (False, [], False)


def test_analyze_single_file_no_current_book():
    studio = SimpleNamespace(
        doctor=SimpleNamespace(analyze_health=lambda *a, **k: {}),
        current_book=None,
        title_registry={},
        doctor_issue_registry={},
        doctor_issue_line_registry={},
    )
    svc = DiagnosticsService(studio)
    had, issues, valid = svc.analyze_single_file("c:/x/y.md")
    assert (had, issues, valid) == (False, [], False)


def test_analyze_single_file_no_doctor():
    studio = SimpleNamespace(
        doctor=None,
        current_book=Path("c:/book"),
        title_registry={},
        doctor_issue_registry={},
        doctor_issue_line_registry={},
    )
    svc = DiagnosticsService(studio)
    had, issues, valid = svc.analyze_single_file("c:/book/x.md")
    assert (had, issues, valid) == (False, [], False)


def test_analyze_single_file_path_outside_book(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("# X", encoding="utf-8")
    book = tmp_path / "book"
    book.mkdir()
    studio = _make_single_file_doctor({}, current_book=book)
    svc = DiagnosticsService(studio)
    had, issues, valid = svc.analyze_single_file(str(outside))
    assert (had, issues, valid) == (False, [], False)


def test_analyze_single_file_non_md_path(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    txt = book / "notes.txt"
    txt.write_text("x", encoding="utf-8")
    studio = _make_single_file_doctor({}, current_book=book)
    svc = DiagnosticsService(studio)
    had, issues, valid = svc.analyze_single_file(str(txt))
    assert (had, issues, valid) == (False, [], False)


def test_analyze_single_file_writes_issues_and_line(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    md = book / "kap.md"
    md.write_text("# X", encoding="utf-8")
    analysis = {
        "issues_by_path": {"kap.md": ["issue-1"]},
        "issue_details_by_path": {"kap.md": [{"line_number": 7, "message": "boom"}]},
        "issue_first_line_by_path": {"kap.md": 7},
    }
    studio = _make_single_file_doctor(analysis, current_book=book)
    svc = DiagnosticsService(studio)
    had, details, valid = svc.analyze_single_file(str(md))
    assert valid is True
    assert had is False
    assert details == [{"line_number": 7, "message": "boom"}]
    assert studio.doctor_issue_registry == {"kap.md": ["issue-1"]}
    assert studio.doctor_issue_line_registry == {"kap.md": 7}


def test_analyze_single_file_clears_issue_when_no_issues(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    md = book / "kap.md"
    md.write_text("# X", encoding="utf-8")
    analysis = {
        "issues_by_path": {"kap.md": []},
        "issue_details_by_path": {"kap.md": []},
        "issue_first_line_by_path": {},
    }
    studio = _make_single_file_doctor(analysis, current_book=book)
    # Pre-condition: ein Issue war vorher da.
    studio.doctor_issue_registry["kap.md"] = ["old"]
    studio.doctor_issue_line_registry["kap.md"] = 5
    svc = DiagnosticsService(studio)
    had, details, valid = svc.analyze_single_file(str(md))
    assert valid is True
    assert had is True
    assert details == []
    assert "kap.md" not in studio.doctor_issue_registry
    assert "kap.md" not in studio.doctor_issue_line_registry


def test_analyze_single_file_drops_first_line_when_invalid(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    md = book / "kap.md"
    md.write_text("# X", encoding="utf-8")
    analysis = {
        "issues_by_path": {"kap.md": ["X"]},
        "issue_details_by_path": {"kap.md": []},
        "issue_first_line_by_path": {"kap.md": -3},  # ungueltig
    }
    studio = _make_single_file_doctor(analysis, current_book=book)
    studio.doctor_issue_line_registry["kap.md"] = 5
    svc = DiagnosticsService(studio)
    svc.analyze_single_file(str(md))
    assert studio.doctor_issue_registry == {"kap.md": ["X"]}
    # first_line war -3 -> pop statt write
    assert "kap.md" not in studio.doctor_issue_line_registry


def test_analyze_single_file_does_not_touch_other_paths(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    md = book / "kap.md"
    md.write_text("# X", encoding="utf-8")
    analysis = {
        "issues_by_path": {"kap.md": ["X"]},
        "issue_details_by_path": {"kap.md": []},
        "issue_first_line_by_path": {"kap.md": 1},
    }
    studio = _make_single_file_doctor(analysis, current_book=book)
    studio.doctor_issue_registry["other.md"] = ["preserved"]
    studio.doctor_issue_line_registry["other.md"] = 99
    svc = DiagnosticsService(studio)
    svc.analyze_single_file(str(md))
    assert studio.doctor_issue_registry["other.md"] == ["preserved"]
    assert studio.doctor_issue_line_registry["other.md"] == 99


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
