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

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import session_manager
from session_manager import SessionManager


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
