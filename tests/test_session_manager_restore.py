"""Tests fuer `SessionManager.restore()`: Pfad-Traversal-Schutz bei Profilnamen.

B-Fix (Code-Review 2026-07-03): `current_profile_name` wird aus der
(potenziell manipulierbaren) `session_state.json` gelesen und war zuvor
unvalidiert Teil des Pfads `<book>/bookconfig/<name>.json`. Ein Profilname
mit `..`-Segmenten (oder ein absoluter Pfad) konnte theoretisch aus
`bookconfig/` herausfuehren, sodass beim Programmstart eine beliebige
JSON-Datei als Profil geladen wird. `restore()` nutzt jetzt
`sanitize_profile_name`, um solche Namen zu verwerfen.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import session_manager
from session_manager import SessionManager, MAX_RECENT_BOOKS


def _make_studio(tmp_path: Path, profile_name):
    book = tmp_path / "mybook"
    (book / "bookconfig").mkdir(parents=True)

    calls = {"loaded_profile_path": None}

    def _load_profile_from_file(path, show_message=False, track_undo=False):
        calls["loaded_profile_path"] = path

    studio = SimpleNamespace(
        base_path=tmp_path,
        books=[book],
        book_combo=SimpleNamespace(current=lambda idx: None),
        load_book=lambda evt: None,
        restored_session_state={
            "active_book_name": "mybook",
            "current_profile_name": profile_name,
        },
        last_export_options={},
        current_book=book,
        current_profile_name=None,
        load_profile_from_file=_load_profile_from_file,
        is_restoring_session=False,
        on_title_search_change=lambda: None,
        apply_status_filter=lambda: None,
        refresh_log_view=lambda: None,
        list_avail=SimpleNamespace(selection_set=lambda x: None, selection=lambda: ()),
        tree_book=SimpleNamespace(selection_set=lambda x: None, selection=lambda: ()),
        log_filter_var=SimpleNamespace(set=lambda v: None),
        log_filter_labels={"Alle"},
        log_auto_clear_var=SimpleNamespace(set=lambda v: None),
        log_max_lines_var=SimpleNamespace(set=lambda v: None, get=lambda: "500"),
    )
    return studio, calls, book


def test_restore_rejects_path_traversal_profile_name(tmp_path):
    """Ein boesartiger Profilname mit `..`-Segmenten darf keine Datei laden."""
    outside_secret = tmp_path / "secret.json"
    outside_secret.write_text("{}", encoding="utf-8")

    studio, calls, book = _make_studio(tmp_path, "../secret")
    mgr = SessionManager(studio)
    mgr.restore()

    assert calls["loaded_profile_path"] is None


def test_restore_rejects_absolute_profile_name(tmp_path):
    studio, calls, book = _make_studio(tmp_path, "C:/Windows/evil")
    mgr = SessionManager(studio)
    mgr.restore()

    assert calls["loaded_profile_path"] is None


def test_restore_loads_valid_profile_name(tmp_path):
    """Ein normaler, unverdaechtiger Profilname funktioniert weiterhin."""
    studio, calls, book = _make_studio(tmp_path, "default")
    profile_file = book / "bookconfig" / "default.json"
    profile_file.write_text("{}", encoding="utf-8")

    mgr = SessionManager(studio)
    mgr.restore()

    assert calls["loaded_profile_path"] == profile_file


def test_restore_handles_missing_profile_name(tmp_path):
    studio, calls, book = _make_studio(tmp_path, None)
    mgr = SessionManager(studio)
    mgr.restore()

    assert calls["loaded_profile_path"] is None


# --- save(): Fehler werden geloggt statt verschluckt (Code-Review 2026-07-03) -


def test_save_logs_via_studio_report_nonfatal_error_on_write_failure(tmp_path):
    """Wenn das Studio `_report_nonfatal_error` anbietet, wird es genutzt."""
    reported = []
    studio = SimpleNamespace(
        _session_state_path=tmp_path / "session_state.json",
        current_book=None,
        current_profile_name=None,
        last_export_options={},
        _report_nonfatal_error=lambda context, error: reported.append((context, error)),
    )
    mgr = SessionManager(studio)

    with patch.object(
        session_manager._session_state_service,
        "write_session_state",
        side_effect=OSError("disk full"),
    ):
        mgr.save()

    assert len(reported) == 1
    assert "Sitzung" in reported[0][0]


def test_save_falls_back_to_module_logger_without_studio_hook(tmp_path):
    """Ohne `_report_nonfatal_error` auf dem Studio wird der Modul-Logger genutzt."""
    studio = SimpleNamespace(
        _session_state_path=tmp_path / "session_state.json",
        current_book=None,
        current_profile_name=None,
        last_export_options={},
    )
    mgr = SessionManager(studio)

    with patch.object(
        session_manager._session_state_service,
        "write_session_state",
        side_effect=OSError("disk full"),
    ), patch.object(session_manager.logger, "warning") as mock_warn:
        mgr.save()

    mock_warn.assert_called_once()


# --- "Letzte aktive Projekte": recent_books wird gepflegt/aufgeloest -------


def _make_recent_studio(tmp_path: Path, current_book=None):
    root = tmp_path
    return SimpleNamespace(
        _session_state_path=tmp_path / "session_state.json",
        base_path=root,
        projects_root_path=root,
        current_book=current_book,
        current_profile_name=None,
        last_export_options={},
    )


def _make_book(tmp_path: Path, name: str) -> Path:
    book = tmp_path / name
    (book / "_quarto.yml").parent.mkdir(parents=True, exist_ok=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    return book


def test_save_adds_active_book_to_recent_books(tmp_path: Path):
    book = _make_book(tmp_path, "Band_A")
    studio = _make_recent_studio(tmp_path, current_book=book)
    mgr = SessionManager(studio)

    mgr.save()

    state = json.loads(studio._session_state_path.read_text(encoding="utf-8"))
    assert state["recent_books"] == ["Band_A"]


def test_save_moves_reopened_book_to_front_without_duplicating(tmp_path: Path):
    book_a = _make_book(tmp_path, "Band_A")
    book_b = _make_book(tmp_path, "Band_B")
    studio = _make_recent_studio(tmp_path, current_book=book_a)
    mgr = SessionManager(studio)
    mgr.save()
    studio.current_book = book_b
    mgr.save()
    studio.current_book = book_a
    mgr.save()

    state = json.loads(studio._session_state_path.read_text(encoding="utf-8"))
    assert state["recent_books"] == ["Band_A", "Band_B"]


def test_save_caps_recent_books_at_max(tmp_path: Path):
    studio = _make_recent_studio(tmp_path, current_book=None)
    mgr = SessionManager(studio)
    for i in range(MAX_RECENT_BOOKS + 5):
        book = _make_book(tmp_path, f"Band_{i}")
        studio.current_book = book
        mgr.save()

    state = json.loads(studio._session_state_path.read_text(encoding="utf-8"))
    assert len(state["recent_books"]) == MAX_RECENT_BOOKS
    # Neuestes zuerst.
    assert state["recent_books"][0] == f"Band_{MAX_RECENT_BOOKS + 4}"


def test_get_recent_books_excludes_current_and_missing_folders(tmp_path: Path):
    book_a = _make_book(tmp_path, "Band_A")
    book_b = _make_book(tmp_path, "Band_B")
    studio = _make_recent_studio(tmp_path, current_book=book_a)
    mgr = SessionManager(studio)

    session_manager._session_state_service.write_session_state(
        studio._session_state_path,
        {"recent_books": ["Band_A", "Band_B", "Band_Deleted"]},
    )

    entries = mgr.get_recent_books()

    keys = [e["key"] for e in entries]
    assert "Band_A" not in keys  # aktuell aktives Buch wird ausgeblendet
    assert "Band_Deleted" not in keys  # Ordner existiert nicht mehr
    assert keys == ["Band_B"]
    assert entries[0]["path"] == book_b
    assert entries[0]["label"] == "Band_B"


def test_get_recent_books_returns_empty_without_session_path(tmp_path: Path):
    studio = SimpleNamespace(current_book=None)
    mgr = SessionManager(studio)
    assert mgr.get_recent_books() == []


def test_get_recent_books_survives_corrupt_session_state(tmp_path: Path):
    studio = _make_recent_studio(tmp_path, current_book=None)
    studio._session_state_path.write_text("not json{{{", encoding="utf-8")
    mgr = SessionManager(studio)
    assert mgr.get_recent_books() == []
