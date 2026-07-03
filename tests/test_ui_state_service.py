"""Tests fuer Phase 2 / Schritt 2.6a: UiStateService.

Deckt die *reinen Berechnungs-Pfade* des UI-State ab:
- is_fulltext_search_enabled
- path_matches_file_state_filter (mit Spezialfiltern)
- should_persist_app_state
- is_right_side_search_scope
- resolve_active_search_term

Tree-Manipulation (`_apply_tree_filters`, `_update_avail_list`),
UI-Refresh (`search_var.set`, `persist_app_state`) und das
Re-Binding der Tree-Items bleiben in `BookStudio` (Schritt 2.6b).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.ui_state_service import (
    DEFAULT_FILE_STATE_FILTER,
    DEFAULT_SEARCH_MODE,
    DEFAULT_SEARCH_SCOPE,
    RIGHT_SIDE_SEARCH_SCOPES,
    UiStateService,
)


# --- Helpers ---------------------------------------------------------------


def _make_studio(search_var_value="", file_state_value="Alle", **extras):
    """Baut ein Studio-`SimpleNamespace` mit Tk-artigen StringVars."""
    search_var = SimpleNamespace(get=lambda: search_var_value)
    file_state_filter_var = SimpleNamespace(get=lambda: file_state_value)
    kwargs = dict(
        search_var=search_var,
        file_state_filter_var=file_state_filter_var,
    )
    kwargs.update(extras)
    return SimpleNamespace(**kwargs)


# --- search_text Property -------------------------------------------------


def test_search_text_returns_var_value():
    studio = _make_studio(search_var_value="Quarto")
    svc = UiStateService(studio)
    assert svc.search_text == "Quarto"


def test_search_text_returns_empty_when_get_raises():
    """Defensive: wenn die Tk-Var noch nicht da ist, gibt es einen leeren String."""
    studio = SimpleNamespace(
        search_var=SimpleNamespace(get=lambda: (_ for _ in ()).throw(RuntimeError("nope")))
    )
    svc = UiStateService(studio)
    assert svc.search_text == ""


# --- file_state_filter Property -------------------------------------------


def test_file_state_filter_returns_var_value():
    studio = _make_studio(file_state_value="Verwaiste Fußnoten")
    svc = UiStateService(studio)
    assert svc.file_state_filter == "Verwaiste Fußnoten"


def test_file_state_filter_returns_default_when_get_raises():
    studio = SimpleNamespace(
        file_state_filter_var=SimpleNamespace(
            get=lambda: (_ for _ in ()).throw(RuntimeError("nope"))
        )
    )
    svc = UiStateService(studio)
    assert svc.file_state_filter == DEFAULT_FILE_STATE_FILTER == "Alle"


# --- invalidate_content_search_cache -------------------------------------


def test_invalidate_calls_studio_method():
    called = []

    studio = SimpleNamespace(
        invalidate_content_search_cache=lambda: called.append("x")
    )
    svc = UiStateService(studio)
    svc.invalidate_content_search_cache()
    assert called == ["x"]


def test_invalidate_handles_missing_method():
    """Wenn `invalidate_content_search_cache` am Studio fehlt, kein Crash."""
    studio = SimpleNamespace()  # kein Attribut
    svc = UiStateService(studio)
    svc.invalidate_content_search_cache()  # kein Fehler


def test_invalidate_handles_non_callable_attribute():
    """Wenn das Attribut existiert, aber nicht callable ist, kein Crash."""
    studio = SimpleNamespace(invalidate_content_search_cache="nope")
    svc = UiStateService(studio)
    svc.invalidate_content_search_cache()  # kein Fehler


# --- is_fulltext_search_enabled ------------------------------------------


def test_is_fulltext_true_when_volltext():
    assert UiStateService.is_fulltext_search_enabled("Volltext") is True


def test_is_fulltext_false_for_other_modes():
    assert UiStateService.is_fulltext_search_enabled(DEFAULT_SEARCH_MODE) is False
    assert UiStateService.is_fulltext_search_enabled("") is False
    assert UiStateService.is_fulltext_search_enabled("v") is False


def test_is_fulltext_false_for_none():
    assert UiStateService.is_fulltext_search_enabled(None) is False


# --- path_matches_file_state_filter --------------------------------------


def test_match_returns_true_for_default_filter():
    state = {"orphan_footnotes": True, "pdf_pagebreak_end": False}
    assert UiStateService.path_matches_file_state_filter(state, "Alle") is True


def test_match_returns_true_for_none_filter():
    state = {"orphan_footnotes": True}
    assert UiStateService.path_matches_file_state_filter(state, None) is True


def test_match_orphan_filter_true_when_flag_set():
    state = {"orphan_footnotes": True}
    assert UiStateService.path_matches_file_state_filter(state, "Verwaiste Fußnoten") is True


def test_match_orphan_filter_false_when_flag_unset():
    state = {"orphan_footnotes": False}
    assert UiStateService.path_matches_file_state_filter(state, "Verwaiste Fußnoten") is False


def test_match_orphan_filter_false_when_state_empty():
    assert UiStateService.path_matches_file_state_filter({}, "Verwaiste Fußnoten") is False


def test_match_orphan_filter_false_when_state_none():
    assert UiStateService.path_matches_file_state_filter(None, "Verwaiste Fußnoten") is False


def test_match_pagebreak_filter_true_when_flag_set():
    state = {"pdf_pagebreak_end": True}
    assert UiStateService.path_matches_file_state_filter(state, "PDF-Seitenumbruch am Dateiende") is True


def test_match_pagebreak_filter_false_when_flag_unset():
    state = {"pdf_pagebreak_end": False}
    assert UiStateService.path_matches_file_state_filter(state, "PDF-Seitenumbruch am Dateiende") is False


def test_match_missing_images_filter_true_when_flag_set():
    state = {"missing_images": True}
    assert UiStateService.path_matches_file_state_filter(state, "Fehlende Bilder") is True


def test_match_missing_images_filter_false_when_flag_unset():
    state = {"missing_images": False}
    assert UiStateService.path_matches_file_state_filter(state, "Fehlende Bilder") is False


def test_match_unknown_filter_value_returns_true():
    """Rueckfall auf das alte Verhalten: unbekannte Filter passieren alle."""
    state = {"orphan_footnotes": True}
    assert UiStateService.path_matches_file_state_filter(state, "Unbekannter Filter") is True


def test_match_unknown_filter_with_none_state_returns_true():
    assert UiStateService.path_matches_file_state_filter(None, "Unbekannter Filter") is True


# --- should_persist_app_state --------------------------------------------


def test_should_persist_returns_true_when_not_restoring():
    assert UiStateService.should_persist_app_state(False) is True


def test_should_persist_returns_false_when_restoring():
    assert UiStateService.should_persist_app_state(True) is False


# --- is_right_side_search_scope ------------------------------------------


def test_right_side_scopes_constant():
    assert RIGHT_SIDE_SEARCH_SCOPES == frozenset({"Rechts", "Beide"})


def test_is_right_side_true_for_rechts():
    assert UiStateService.is_right_side_search_scope("Rechts") is True


def test_is_right_side_true_for_beide():
    assert UiStateService.is_right_side_search_scope("Beide") is True


def test_is_right_side_false_for_links():
    assert UiStateService.is_right_side_search_scope(DEFAULT_SEARCH_SCOPE) is False


def test_is_right_side_false_for_none():
    assert UiStateService.is_right_side_search_scope(None) is False


def test_is_right_side_false_for_unknown_scope():
    assert UiStateService.is_right_side_search_scope("Oben") is False


# --- resolve_active_search_term -----------------------------------------


def test_resolve_term_returns_term_for_rechts():
    assert UiStateService.resolve_active_search_term("Quarto", "Rechts") == "Quarto"


def test_resolve_term_returns_term_for_beide():
    assert UiStateService.resolve_active_search_term("Quarto", "Beide") == "Quarto"


def test_resolve_term_returns_empty_for_links():
    assert UiStateService.resolve_active_search_term("Quarto", "Links") == ""


def test_resolve_term_returns_empty_for_none_scope():
    assert UiStateService.resolve_active_search_term("Quarto", None) == ""


def test_resolve_term_handles_empty_term():
    assert UiStateService.resolve_active_search_term("", "Rechts") == ""


def test_resolve_term_handles_none_term():
    assert UiStateService.resolve_active_search_term(None, "Rechts") == ""  # type: ignore[arg-type]


# --- Konstanten ----------------------------------------------------------


def test_default_constants_have_expected_values():
    """Sanity-Check: Konstantenwerte, die das Studio erwartet."""
    assert DEFAULT_FILE_STATE_FILTER == "Alle"
    assert DEFAULT_SEARCH_SCOPE == "Links"
    assert DEFAULT_SEARCH_MODE == "Titel"


# --- evaluate_node_visibility (Phase 2 / Schritt 2.6b) ----------------


def test_evaluate_node_visibility_all_passes():
    s_ok, st_ok, sr_ok, self_match, visible = (
        UiStateService.evaluate_node_visibility(
            target_status="Alle",
            actual_status="irgendwas",
            path="x.md",
            file_state=None,
            file_state_filter="Alle",
            search_term="",
            is_fulltext=False,
            child_visible=False,
        )
    )
    assert s_ok is True
    assert st_ok is True
    assert sr_ok is True
    assert self_match is False
    assert visible is True


def test_evaluate_node_visibility_status_filter_rejects():
    s_ok, _, _, _, visible = UiStateService.evaluate_node_visibility(
        target_status="Entwurf",
        actual_status="Veröffentlicht",
        path="x.md",
        file_state=None,
        file_state_filter="Alle",
        search_term="",
        is_fulltext=False,
        child_visible=False,
    )
    assert s_ok is False
    assert visible is False


def test_evaluate_node_visibility_status_match():
    s_ok, _, _, _, visible = UiStateService.evaluate_node_visibility(
        target_status="Entwurf",
        actual_status="Entwurf",
        path="x.md",
        file_state=None,
        file_state_filter="Alle",
        search_term="",
        is_fulltext=False,
        child_visible=False,
    )
    assert s_ok is True
    assert visible is True


def test_evaluate_node_visibility_state_filter():
    s_ok, st_ok, _, _, visible = UiStateService.evaluate_node_visibility(
        target_status="Alle",
        actual_status="x",
        path="x.md",
        file_state={"orphan_footnotes": True},
        file_state_filter="Verwaiste Fußnoten",
        search_term="",
        is_fulltext=False,
        child_visible=False,
    )
    assert s_ok is True
    assert st_ok is True
    assert visible is True


def test_evaluate_node_visibility_state_filter_mismatch():
    _, st_ok, _, _, visible = UiStateService.evaluate_node_visibility(
        target_status="Alle",
        actual_status="x",
        path="x.md",
        file_state={"orphan_footnotes": False},
        file_state_filter="Verwaiste Fußnoten",
        search_term="",
        is_fulltext=False,
        child_visible=False,
    )
    assert st_ok is False
    assert visible is False


def test_evaluate_node_visibility_search_term_no_match():
    s_ok, _, sr_ok, self_match, visible = UiStateService.evaluate_node_visibility(
        target_status="Alle",
        actual_status="x",
        path="x.md",
        file_state=None,
        file_state_filter="Alle",
        search_term="Quarto",
        is_fulltext=False,
        child_visible=False,
        node_text="kapitel eins",
        raw_title="kapitel eins",
    )
    assert s_ok is True
    assert sr_ok is False
    assert self_match is False
    assert visible is False


def test_evaluate_node_visibility_search_match_in_path():
    _, _, sr_ok, self_match, visible = UiStateService.evaluate_node_visibility(
        target_status="Alle",
        actual_status="x",
        path="quarto-intro.md",
        file_state=None,
        file_state_filter="Alle",
        search_term="quarto",
        is_fulltext=False,
        child_visible=False,
        node_text="",
        raw_title="",
    )
    assert sr_ok is True
    assert self_match is True
    assert visible is True


def test_evaluate_node_visibility_search_match_in_fulltext_content():
    _, _, sr_ok, self_match, visible = UiStateService.evaluate_node_visibility(
        target_status="Alle",
        actual_status="x",
        path="x.md",
        file_state=None,
        file_state_filter="Alle",
        search_term="magie",
        is_fulltext=True,
        child_visible=False,
        node_text="leeres node",
        raw_title="leerer titel",
        content_text="und es war magie",
    )
    assert sr_ok is True
    assert self_match is True
    assert visible is True


def test_evaluate_node_visibility_child_visible_keeps_parent():
    _, _, sr_ok, self_match, visible = UiStateService.evaluate_node_visibility(
        target_status="Alle",
        actual_status="x",
        path="x.md",
        file_state=None,
        file_state_filter="Alle",
        search_term="foo",
        is_fulltext=False,
        child_visible=True,
    )
    # Kein Self-Match, aber Kind sichtbar -> search_ok True
    # (wegen OR child_visible), und visible True.
    assert self_match is False
    assert sr_ok is True
    assert visible is True


def test_evaluate_node_visibility_empty_path():
    s_ok, st_ok, sr_ok, self_match, visible = (
        UiStateService.evaluate_node_visibility(
            target_status="Alle",
            actual_status="x",
            path="",
            file_state=None,
            file_state_filter="Alle",
            search_term="",
            is_fulltext=False,
            child_visible=False,
        )
    )
    assert s_ok is True
    assert st_ok is True
    assert sr_ok is True
    assert self_match is False
    assert visible is True


# --- build_left_list_entries (Phase 2 / Schritt 2.6b) ----------------


def test_build_left_list_entries_filters_used_paths():
    title_reg = {"a.md": "A", "b.md": "B", "c.md": "C"}
    out = UiStateService.build_left_list_entries(
        title_reg, ["a.md", "c.md"]
    )
    assert out == [("b.md", "B")]


def test_build_left_list_entries_sorts_by_title():
    title_reg = {"x.md": "Charlie", "y.md": "Alpha", "z.md": "Bravo"}
    out = UiStateService.build_left_list_entries(title_reg, [])
    assert out == [("y.md", "Alpha"), ("z.md", "Bravo"), ("x.md", "Charlie")]


def test_build_left_list_entries_no_used_filter():
    out = UiStateService.build_left_list_entries({}, [])
    assert out == []


def test_build_left_list_entries_applies_state_filter():
    title_reg = {"a.md": "A", "b.md": "B"}
    out = UiStateService.build_left_list_entries(
        title_reg,
        [],
        file_state_filter="Verwaiste Fußnoten",
        file_state_for_path=lambda p: {"orphan_footnotes": p == "a.md"},
    )
    assert out == [("a.md", "A")]


def test_build_left_list_entries_no_state_filter():
    title_reg = {"a.md": "A", "b.md": "B"}
    out = UiStateService.build_left_list_entries(
        title_reg,
        [],
        file_state_filter="Alle",
        file_state_for_path=lambda p: {"orphan_footnotes": False},
    )
    assert len(out) == 2


def test_build_left_list_entries_applies_left_search():
    title_reg = {"a.md": "Alpha", "b.md": "Bravo"}
    out = UiStateService.build_left_list_entries(
        title_reg, [], search_term="bravo", apply_left_search=True
    )
    assert out == [("b.md", "Bravo")]


def test_build_left_list_entries_left_search_no_apply():
    title_reg = {"a.md": "Alpha", "b.md": "Bravo"}
    out = UiStateService.build_left_list_entries(
        title_reg, [], search_term="bravo", apply_left_search=False
    )
    # Kein apply -> alles drin
    assert len(out) == 2


def test_build_left_list_entries_fulltext_via_lookup():
    title_reg = {"a.md": "Alpha", "b.md": "Bravo"}
    out = UiStateService.build_left_list_entries(
        title_reg,
        [],
        search_term="magie",
        apply_left_search=True,
        is_fulltext=True,
        content_lookup=lambda p: "magie im text" if p == "a.md" else "",
    )
    assert out == [("a.md", "Alpha")]


def test_build_left_list_entries_fulltext_no_lookup_falls_back_to_title():
    title_reg = {"a.md": "Alpha magic", "b.md": "Bravo"}
    out = UiStateService.build_left_list_entries(
        title_reg,
        [],
        search_term="magic",
        apply_left_search=True,
        is_fulltext=True,
        content_lookup=None,
    )
    # Ohne content_lookup wird der Content-Teil uebergangen, aber
    # Title-Match gilt -> a.md passt.
    assert out == [("a.md", "Alpha magic")]


def test_build_left_list_entries_path_match():
    title_reg = {"alpha-intro.md": "Einführung", "beta.md": "Beta"}
    out = UiStateService.build_left_list_entries(
        title_reg, [], search_term="alpha", apply_left_search=True
    )
    assert out == [("alpha-intro.md", "Einführung")]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
