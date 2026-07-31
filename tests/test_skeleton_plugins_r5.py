"""Tests für R5: Off-by-one Pfadauflösung in Skeleton-Plugins.

Quelle: implementation_plan.md, Abschnitt 3.5 (R5).

Diese Tests validieren, dass:
1. `plugins/skeleton_editor/__init__.py::is_available()` True zurückgibt
   (weil `tools/skeleton/editor.py` existiert).
2. `plugins/skeleton_populate/__init__.py::is_available()` True zurückgibt
   (weil `tools/skeleton/populate.py` existiert).
3. `_ensure_repo_on_path()` das Projekt-Root zurückgibt (enthält book_studio.py).
4. Der Bug: `parents[1]` statt `parents[2]` führt dazu, dass die Funktionen
   das falsche Verzeichnis suchen.

Dieser Test wird RED sein, bis der Code auf `parents[2]` korrigiert ist.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_skeleton_editor_is_available():
    """R5-Test 1: `plugins.skeleton_editor.is_available()` sollte True sein.

    Dies ist derzeit RED, weil der Code `parents[1]` statt `parents[2]`
    verwendet, was auf das `plugins`-Verzeichnis statt auf das Projekt-Root
    zeigt. `tools/skeleton/editor.py` liegt aber unter Projekt-Root.
    """
    try:
        from plugins.skeleton_editor import is_available as editor_available

        result = editor_available()
        assert result is True, (
            "is_available() sollte True sein, wenn tools/skeleton/editor.py existiert"
        )
    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


def test_skeleton_populate_is_available():
    """R5-Test 2: `plugins.skeleton_populate.is_available()` sollte True sein.

    Dies ist derzeit RED, weil der Code `parents[1]` statt `parents[2]`
    verwendet. `tools/skeleton/populate.py` liegt aber unter Projekt-Root.
    """
    try:
        from plugins.skeleton_populate import is_available as populate_available

        result = populate_available()
        assert result is True, (
            "is_available() sollte True sein, wenn tools/skeleton/populate.py existiert"
        )
    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


def test_skeleton_editor_ensure_repo_on_path_returns_project_root():
    """R5-Test 3: `_ensure_repo_on_path()` gibt das Projekt-Root zurück.

    Das Ergebnis sollte `book_studio.py` und `plugins/` enthalten.
    """
    try:
        from plugins.skeleton_editor import _ensure_repo_on_path

        root = _ensure_repo_on_path()

        # Projekt-Root sollte book_studio.py enthalten
        assert (
            root / "book_studio.py"
        ).is_file(), f"Projekt-Root sollte book_studio.py enthalten, root={root}"

        # Projekt-Root sollte plugins-Verzeichnis enthalten
        assert (
            root / "plugins"
        ).is_dir(), f"Projekt-Root sollte plugins-Verzeichnis enthalten, root={root}"

        # Projekt-Root sollte tools/skeleton enthalten
        assert (
            root / "tools" / "skeleton"
        ).is_dir(), f"Projekt-Root sollte tools/skeleton enthalten, root={root}"

    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


def test_skeleton_populate_ensure_repo_on_path_returns_project_root():
    """R5-Test 4: Analoger Test für `skeleton_populate._ensure_repo_on_path()`."""
    try:
        from plugins.skeleton_populate import _ensure_repo_on_path

        root = _ensure_repo_on_path()

        # Projekt-Root sollte book_studio.py enthalten
        assert (
            root / "book_studio.py"
        ).is_file(), f"Projekt-Root sollte book_studio.py enthalten, root={root}"

        # Projekt-Root sollte plugins-Verzeichnis enthalten
        assert (
            root / "plugins"
        ).is_dir(), f"Projekt-Root sollte plugins-Verzeichnis enthalten, root={root}"

        # Projekt-Root sollte tools/skeleton enthalten
        assert (
            root / "tools" / "skeleton"
        ).is_dir(), f"Projekt-Root sollte tools/skeleton enthalten, root={root}"

    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


def test_editor_and_populate_use_same_project_root():
    """R5-Test 5: Beide Plugins sollten das gleiche Projekt-Root haben."""
    try:
        from plugins.skeleton_editor import _ensure_repo_on_path as editor_root
        from plugins.skeleton_populate import _ensure_repo_on_path as populate_root

        root_editor = editor_root()
        root_populate = populate_root()

        assert root_editor == root_populate, (
            f"Beide Plugins sollten das gleiche Projekt-Root haben, "
            f"aber editor={root_editor}, populate={root_populate}"
        )

    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


def test_file_indexer_consistency():
    """R5-Test 6: Vergleich mit dem bereits korrekten `file_indexer`-Plugin.

    Das file_indexer-Plugin verwendet `parents[3]` (oder parent.parent.parent),
    was für Dateien unter `plugins/file_indexer/__init__.py` das Projekt-Root ist.
    skeleton_editor/populate sollten dasselbe Ergebnis liefern.
    """
    try:
        from plugins.file_indexer import _ensure_repo_on_path as file_indexer_root
        from plugins.skeleton_editor import _ensure_repo_on_path as editor_root

        root_fi = file_indexer_root()
        root_editor = editor_root()

        assert root_fi == root_editor, (
            f"skeleton_editor sollte denselben Root wie file_indexer haben, "
            f"aber file_indexer={root_fi}, editor={root_editor}"
        )

    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


def test_skeleton_editor_path_calculation_detail(monkeypatch, tmp_path):
    """R5-Test 7: Detaillierte Pfad-Berechnung für skeleton_editor.

    Dieser Test überprüft die exakte Berechnung von __file__.parents[?].
    Für __init__.py unter plugins/skeleton_editor/:
    - parents[0] = plugins/skeleton_editor
    - parents[1] = plugins  (FALSCH)
    - parents[2] = project_root  (RICHTIG)
    """
    try:
        from plugins.skeleton_editor import _ensure_repo_on_path

        root = _ensure_repo_on_path()

        # Das sollte Projekt-Root sein, nicht 'plugins'
        assert root.name != "plugins", (
            f"Root sollte nicht 'plugins' sein, root.name={root.name}"
        )

        # Es sollte Projekt-Root sein (enthält book_studio.py)
        assert (
            root / "book_studio.py"
        ).is_file(), f"Root sollte book_studio.py enthalten"

    except ImportError as e:
        pytest.skip(f"Plugin konnte nicht importiert werden: {e}")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
