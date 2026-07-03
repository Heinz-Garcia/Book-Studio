"""Tests fuer Phase 2 / Schritt 2.2: BookSessionService (echte Implementierung).

Stellt sicher, dass:
- `BookSessionService.set_active_book` nur akzeptiert, wenn der Pfad in der
  Buecher-Liste ist; sonst `False`.
- `reset_profile` setzt `current_profile_name` auf `None`.
- `clear_search_cache` leert den Cache.
- `pick_target_index` waehlt nach Heuristik (gleiches Buch, Namens-Match, Default 0).
- `initialize_engines_for_book` setzt Engines aus injizierten Factories.
- Die Properties `current_book`, `current_profile_name`, `profile_path` weiter
  funktionieren.

Diese Tests wurden hinzugefuegt, als der Service vom Stub zur echten
Implementierung migriert wurde (Phase 2 / Schritt 2.2).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.book_session_service import BookSessionService


# --- Helpers ---------------------------------------------------------------


def _make_studio(books=None, current_book=None, current_profile_name=None) -> SimpleNamespace:
    return SimpleNamespace(
        books=list(books or []),
        current_book=current_book,
        current_profile_name=current_profile_name,
        yaml_engine=None,
        doctor=None,
        backup_mgr=None,
        _content_search_cache={"a": 1, "b": 2},
    )


# --- set_active_book -------------------------------------------------------


def test_set_active_book_accepts_known_book(tmp_path: Path):
    book = tmp_path / "alpha"
    book.mkdir()
    studio = _make_studio(books=[book])
    svc = BookSessionService(studio)
    assert svc.set_active_book(book) is True
    assert studio.current_book == book


def test_set_active_book_rejects_unknown_book(tmp_path: Path):
    book = tmp_path / "alpha"
    book.mkdir()
    other = tmp_path / "beta"
    other.mkdir()
    studio = _make_studio(books=[book])
    svc = BookSessionService(studio)
    assert svc.set_active_book(other) is False
    assert studio.current_book is None


def test_set_active_book_rejects_none(tmp_path: Path):
    book = tmp_path / "alpha"
    book.mkdir()
    studio = _make_studio(books=[book], current_book=book)
    svc = BookSessionService(studio)
    # `None` darf das aktuelle Buch nicht ueberschreiben.
    assert svc.set_active_book(None) is False
    assert studio.current_book == book


def test_set_active_book_with_empty_books_list(tmp_path: Path):
    studio = _make_studio(books=[])
    svc = BookSessionService(studio)
    assert svc.set_active_book(tmp_path / "x") is False


# --- reset_profile ---------------------------------------------------------


def test_reset_profile_clears_current(tmp_path: Path):
    studio = _make_studio(current_profile_name="manuell")
    svc = BookSessionService(studio)
    svc.reset_profile()
    assert studio.current_profile_name is None


def test_reset_profile_is_idempotent(tmp_path: Path):
    studio = _make_studio(current_profile_name=None)
    svc = BookSessionService(studio)
    svc.reset_profile()
    assert studio.current_profile_name is None


# --- clear_search_cache ----------------------------------------------------


def test_clear_search_cache_empties_dict(tmp_path: Path):
    studio = _make_studio()
    svc = BookSessionService(studio)
    assert len(studio._content_search_cache) == 2
    svc.clear_search_cache()
    assert studio._content_search_cache == {}


def test_clear_search_cache_handles_missing_attr():
    """Wenn `search_cache_getter` ueberschrieben wird und ein leeres Dict liefert."""
    studio = SimpleNamespace(books=[])

    def _get_empty():
        return {}

    svc = BookSessionService(studio, search_cache_getter=_get_empty)
    svc.clear_search_cache()  # kein Fehler


# --- pick_target_index -----------------------------------------------------


def test_pick_target_index_prefers_exact_book_match(tmp_path: Path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    a.mkdir(), b.mkdir(), c.mkdir()
    books = [a, b, c]
    # `previous_book` ist immer noch in der Liste -> Index des Match
    assert BookSessionService.pick_target_index(books, b, "x-irrelevant") == 1


def test_pick_target_index_falls_back_to_name_match(tmp_path: Path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    a.mkdir(), b.mkdir(), c.mkdir()
    books = [a, b, c]
    # `previous_book` ist nicht mehr in der Liste, aber Name passt zu `c`
    assert BookSessionService.pick_target_index(books, None, "c") == 2


def test_pick_target_index_returns_zero_without_match(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    books = [a, b]
    # Kein previous_book, kein Name -> 0
    assert BookSessionService.pick_target_index(books, None, None) == 0


def test_pick_target_index_returns_zero_when_name_unknown(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    books = [a, b]
    assert BookSessionService.pick_target_index(books, None, "nope") == 0


def test_pick_target_index_empty_books_returns_zero():
    assert BookSessionService.pick_target_index([], None, "x") == 0


def test_pick_target_index_prefers_book_over_name(tmp_path: Path):
    """Wenn sowohl `previous_book` als auch `previous_name` matchen,
    hat der direkte Buch-Match Vorrang."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    books = [a, b]
    # `previous_book` ist `a` (Index 0), `previous_name` ist `"b"` (Index 1).
    # Direkter Match gewinnt -> 0.
    assert BookSessionService.pick_target_index(books, a, "b") == 0


# --- initialize_engines_for_book ------------------------------------------


def test_initialize_engines_for_book_sets_all_three():
    """Der Service setzt yaml_engine, doctor und backup_mgr aus den Factories."""
    studio = _make_studio()
    svc = BookSessionService(studio)

    captured = {}

    def _eng_factory(book):
        captured["engine"] = book
        return "YAML_ENGINE_OBJ"

    def _doc_factory(book, treg):
        captured["doctor"] = (book, treg)
        return "DOCTOR_OBJ"

    def _bak_factory(root, book):
        captured["backup"] = (root, book)
        return "BACKUP_OBJ"

    book = Path("/x/mybook")
    svc.initialize_engines_for_book(
        book,
        engine_factory=_eng_factory,
        doctor_factory=_doc_factory,
        backup_factory=_bak_factory,
    )
    assert studio.yaml_engine == "YAML_ENGINE_OBJ"
    assert studio.doctor == "DOCTOR_OBJ"
    assert studio.backup_mgr == "BACKUP_OBJ"
    assert captured["engine"] == book
    assert captured["doctor"] == (book, {})
    assert captured["backup"] == (None, book)  # kein `root`-Attribut am Studio


def test_initialize_engines_for_book_passes_title_registry():
    studio = _make_studio()
    svc = BookSessionService(studio)
    captured = {}

    def _doc_factory(book, treg):
        captured["treg"] = treg
        return "X"

    svc.initialize_engines_for_book(
        Path("/x"),
        engine_factory=lambda b: "E",
        doctor_factory=_doc_factory,
        backup_factory=lambda r, b: "B",
        title_registry={"foo.md": "Foo"},
    )
    assert captured["treg"] == {"foo.md": "Foo"}


def test_initialize_engines_for_book_uses_studio_root_when_present():
    """Wenn das Studio ein `root`-Attribut hat, wird es an `backup_factory` weitergegeben."""
    studio = _make_studio()
    studio.root = "TK_ROOT"
    svc = BookSessionService(studio)
    captured = {}

    def _bak_factory(root, book):
        captured["root"] = root
        return "B"

    svc.initialize_engines_for_book(
        Path("/x"),
        engine_factory=lambda b: "E",
        doctor_factory=lambda b, t: "D",
        backup_factory=_bak_factory,
    )
    assert captured["root"] == "TK_ROOT"


def test_initialize_engines_for_book_title_registry_default_is_empty_dict():
    """Wenn `title_registry` nicht uebergeben wird, bekommt der Doctor ein leeres Dict."""
    studio = _make_studio()
    svc = BookSessionService(studio)
    captured = {}

    def _doc_factory(book, treg):
        captured["treg"] = treg
        return "D"

    svc.initialize_engines_for_book(
        Path("/x"),
        engine_factory=lambda b: "E",
        doctor_factory=_doc_factory,
        backup_factory=lambda r, b: "B",
    )
    assert captured["treg"] == {}


# --- Properties ------------------------------------------------------------


def test_current_book_property():
    book = Path("/x")
    studio = _make_studio(current_book=book)
    svc = BookSessionService(studio)
    assert svc.current_book == book


def test_current_profile_name_property():
    studio = _make_studio(current_profile_name="manuell")
    svc = BookSessionService(studio)
    assert svc.current_profile_name == "manuell"


def test_profile_path_returns_correct_path():
    book = Path("/x")
    studio = _make_studio(current_book=book)
    svc = BookSessionService(studio)
    assert svc.profile_path("default") == Path("/x/bookconfig/default.json")


def test_profile_path_returns_none_without_book():
    studio = _make_studio(current_book=None)
    svc = BookSessionService(studio)
    assert svc.profile_path("x") is None


def test_profile_path_returns_none_with_empty_name():
    book = Path("/x")
    studio = _make_studio(current_book=book)
    svc = BookSessionService(studio)
    assert svc.profile_path("") is None


# --- books_getter / search_cache_getter-Injektion --------------------------


def test_books_getter_injection_used():
    """Der Service nutzt den injizierten `books_getter`, nicht `self._studio.books` direkt."""
    studio = SimpleNamespace(books=[], current_book=None, current_profile_name=None)
    dynamic = [Path("/a")]

    def _get_books():
        return list(dynamic)

    svc = BookSessionService(studio, books_getter=_get_books)
    assert svc.set_active_book(Path("/a")) is True
    assert studio.current_book == Path("/a")


def test_books_getter_returns_copy_not_reference():
    """Der `books_getter` darf eine frische Liste liefern, ohne dass der Service
    sie mutiert."""
    studio = SimpleNamespace(books=[], current_book=None, current_profile_name=None)
    src = [Path("/a"), Path("/b")]

    def _get():
        return list(src)

    svc = BookSessionService(studio, books_getter=_get)
    # Service manipuliert `src` nicht
    assert src == [Path("/a"), Path("/b")]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
