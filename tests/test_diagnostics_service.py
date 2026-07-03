"""Tests fuer Phase 2 / Schritt 2.4a: DiagnosticsService.

Deckt die *reinen Daten-Pfade* des Buch-Doktors ab:
- Issue-Registry-Management (set/clear/has)
- Reine Navigations-Logik (paths_in_tree_order, pick_next_issue_path)
- Convenience-Accessoren (issues_for_path, first_issue_line_for_path)

Tree-Manipulation, Status- und Log-Calls bleiben in `BookStudio`
(Schritt 2.4b).
"""

from __future__ import annotations

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


# --- pick_first_issue_path -----------------------------------------------


def test_pick_first_returns_first_in_tree_order():
    all_paths = ["a.md", "b.md", "c.md"]
    registry = {"c.md": ["x"], "a.md": ["y"]}
    assert DiagnosticsService.pick_first_issue_path(all_paths, registry) == "a.md"


def test_pick_first_returns_none_when_empty():
    assert DiagnosticsService.pick_first_issue_path([], {}) is None
    assert DiagnosticsService.pick_first_issue_path(["a.md"], {}) is None


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
