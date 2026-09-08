"""Regression: Skeleton-/Kapitelliste-Plugins loesen Repo-Root korrekt auf.

Historisch: Off-by-one bei ``__file__.parents[n]`` (R5). Heute ist
``services.plugin_runtime.ensure_repo_on_path`` die SSOT — die Adapter
halten nur noch ``_REPO_ROOT = ensure_repo_on_path(__file__)``.
"""

from __future__ import annotations

from pathlib import Path

from services.plugin_runtime import ensure_repo_on_path


def test_skeleton_editor_is_available():
    from plugins.skeleton_editor import is_available

    assert is_available() is True


def test_skeleton_populate_is_available():
    from plugins.skeleton_populate import is_available

    assert is_available() is True


def test_file_indexer_is_available():
    from plugins.file_indexer import is_available

    assert is_available() is True


def test_skeleton_editor_repo_root_is_project_root():
    import plugins.skeleton_editor as mod

    root = mod._REPO_ROOT
    assert (root / "book_studio.py").is_file()
    assert (root / "plugins").is_dir()
    assert (root / "tools" / "skeleton").is_dir()
    assert root.name != "plugins"


def test_skeleton_populate_repo_root_is_project_root():
    import plugins.skeleton_populate as mod

    root = mod._REPO_ROOT
    assert (root / "book_studio.py").is_file()
    assert (root / "plugins").is_dir()
    assert (root / "tools" / "skeleton" / "populate.py").is_file()


def test_file_indexer_repo_root_matches_skeleton_editor():
    import plugins.file_indexer as fi
    import plugins.skeleton_editor as ed

    assert fi._REPO_ROOT == ed._REPO_ROOT


def test_ensure_repo_on_path_ssot_matches_adapters():
    """Adapter und Runtime-Helper muessen denselben Root liefern."""
    import plugins.skeleton_editor as ed

    adapter_file = Path(ed.__file__).resolve()
    assert ensure_repo_on_path(adapter_file) == ed._REPO_ROOT
