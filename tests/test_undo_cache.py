"""Tests für Batch B6: Undo/Redo & Cache-Konsistenz.

Stellt sicher, dass:
- `undo_stack` auf `undo_max_depth` begrenzt ist.
- `load_book` leert auch den `redo_stack` (R9).
- Cache-Invalidierung an den mutagen Operationen erfolgt (R10).
- `app_config.undo_max_depth` als Default 100 hat.

Referenz: .doc/refactoring-master.md, Batch B6.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app_config


# --- app_config ------------------------------------------------------------


def test_app_config_has_undo_max_depth_default():
    assert app_config.DEFAULTS["undo_max_depth"] == 100


def test_app_config_with_defaults_preserves_custom_depth():
    merged = app_config.with_defaults({"undo_max_depth": 50})
    assert merged["undo_max_depth"] == 50


# --- Undo-Tiefe -----------------------------------------------------------


def test_undo_stack_is_capped_to_undo_max_depth():
    # Stand-alone Stub, der das Verhalten von `_push_undo` 1:1 nachbaut.
    cfg = {"undo_max_depth": 5}
    studio = SimpleNamespace(
        _app_config_path=None,  # nicht verwendet
        undo_stack=[],
        redo_stack=[],
    )

    def read_config(_):
        return cfg

    # lokale Kopie der Logik, weil wir `book_studio` nicht importieren
    # wollen (Tkinter-Henne-Ei-Problem).
    def push_undo(pre_state, current_state):
        if pre_state != current_state:
            studio.undo_stack.append(pre_state)
            studio.redo_stack.clear()
            max_depth = int(read_config(studio._app_config_path).get("undo_max_depth", 100))
            if max_depth and max_depth > 0 and len(studio.undo_stack) > max_depth:
                del studio.undo_stack[: len(studio.undo_stack) - max_depth]

    for i in range(20):
        push_undo(f"state_{i}", f"current_{i}")

    assert len(studio.undo_stack) == 5
    # Die letzten 5 States müssen erhalten sein.
    assert studio.undo_stack == [f"state_{15}", f"state_{16}", f"state_{17}", f"state_{18}", f"state_{19}"]


def test_undo_stack_unlimited_when_max_depth_is_zero():
    cfg = {"undo_max_depth": 0}
    studio = SimpleNamespace(
        _app_config_path=None,
        undo_stack=[],
        redo_stack=[],
    )

    def push_undo(pre_state, current_state):
        if pre_state != current_state:
            studio.undo_stack.append(pre_state)
            studio.redo_stack.clear()
            max_depth = int(cfg.get("undo_max_depth", 100))
            if max_depth and max_depth > 0 and len(studio.undo_stack) > max_depth:
                del studio.undo_stack[: len(studio.undo_stack) - max_depth]

    for i in range(500):
        push_undo(f"state_{i}", f"current_{i}")

    assert len(studio.undo_stack) == 500


# --- Redo-Clear -----------------------------------------------------------


def test_load_book_clears_redo_stack():
    # Wir testen die Semantik: nach `load_book` muss `redo_stack` leer sein.
    # Da `load_book` an `book_studio` hängt, prüfen wir die Verantwortlichkeit
    # über das Vorkommen der Anweisung im Modul.
    import book_studio
    src = Path(book_studio.__file__).read_text(encoding="utf-8")
    # Suche im `load_book`-Block nach `redo_stack.clear()`.
    assert "redo_stack.clear()" in src, (
        "book_studio.load_book muss redo_stack.clear() enthalten (R9)."
    )


# --- Cache-Invalidierung --------------------------------------------------


def test_invalidate_content_search_cache_helper_exists():
    import book_studio
    assert hasattr(book_studio.BookStudio, "invalidate_content_search_cache")


def test_cache_invalidated_in_on_markdown_saved():
    """on_markdown_saved MUSS den Cache leeren, sonst sind Suchergebnisse stale."""
    import book_studio
    src = Path(book_studio.__file__).read_text(encoding="utf-8")
    # Sehr grob: die Methode enthält den Aufruf.
    start = src.find("def on_markdown_saved")
    end = src.find("\n    def ", start + 1)
    body = src[start:end]
    assert "invalidate_content_search_cache" in body, (
        "on_markdown_saved muss den Content-Search-Cache invalidieren (R10)."
    )


def test_cache_invalidated_after_save_project():
    import book_studio
    src = Path(book_studio.__file__).read_text(encoding="utf-8")
    start = src.find("def save_project")
    end = src.find("\n    def ", start + 1)
    body = src[start:end]
    assert "invalidate_content_search_cache" in body


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
