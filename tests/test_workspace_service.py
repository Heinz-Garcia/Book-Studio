"""Tests fuer Phase 2 / Schritt 2.1: WorkspaceService (echte Implementierung).

Stellt sicher, dass:
- `WorkspaceService.get_projects_root_path` Config-Lesung, Pfad-Validierung
  und Fallbacks konsistent zu `BookStudio._get_projects_root_path` verhaelt.
- `WorkspaceService.discover_projects` Projekte unter `_quarto.yml` findet
  und ausgeschlossene Pfad-Segmente (`.venv`, `_book`, ...) ignoriert.
- `WorkspaceService.is_within_project` korrekt funktioniert.

Diese Tests wurden hinzugefuegt, als der Service vom Stub zur echten
Implementierung migriert wurde (Phase 2 / Schritt 2.1).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.workspace_service import (
    EXCLUDED_PATH_SEGMENTS,
    WorkspaceService,
    normalize_content_root_paths,
)


# --- Helpers ---------------------------------------------------------------


def _make_studio(base: Path, root: Path) -> SimpleNamespace:
    return SimpleNamespace(base_path=base, projects_root_path=root)


def _touch_yml(root: Path, rel_path: str) -> Path:
    """Legt `_quarto.yml` unter `root/rel_path` an und gibt den vollen Pfad zurueck."""
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("project:\n  type: book\n", encoding="utf-8")
    return target


# --- get_projects_root_path: Config-Lesung ---------------------------------


def test_get_projects_root_path_uses_configured_absolute_path(tmp_path: Path):
    configured = tmp_path / "configured_books"
    configured.mkdir()
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": str(configured)},
    )
    assert svc.get_projects_root_path() == configured.resolve()


def test_get_projects_root_path_uses_configured_relative_path(tmp_path: Path):
    relative = tmp_path / "relative_books"
    relative.mkdir()
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": "relative_books"},
    )
    assert svc.get_projects_root_path() == relative.resolve()


def test_get_projects_root_path_falls_back_to_base_when_config_missing(tmp_path: Path):
    """Ohne `read_config`-Backdoor faellt der Service auf `base_path` zurueck."""
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=None)
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_to_base_on_config_error(tmp_path: Path):
    """Wenn `read_config` eine Exception wirft, faellt der Service zurueck."""

    def _boom():
        raise OSError("disk error")

    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=_boom)
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_on_json_decode_error(tmp_path: Path):
    def _boom():
        raise ValueError("json kaputt")  # json.JSONDecodeError erbt von ValueError

    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=_boom)
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_on_empty_string(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=lambda: {"content_root_path": "   "})
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_on_non_string_value(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=lambda: {"content_root_path": 42})
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_on_missing_key(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=lambda: {})
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_when_path_does_not_exist(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": str(tmp_path / "nope")},
    )
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_falls_back_when_path_is_a_file(tmp_path: Path):
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("x", encoding="utf-8")
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=lambda: {"content_root_path": str(file_path)})
    assert svc.get_projects_root_path() == tmp_path


def test_get_projects_root_path_expands_user(tmp_path: Path, monkeypatch):
    """Pfade mit `~` werden korrekt expandiert."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio, read_config=lambda: {"content_root_path": "~/books"})
    target = home / "books"
    target.mkdir()
    assert svc.get_projects_root_path() == target.resolve()


def test_get_projects_root_path_reports_nonfatal_error(tmp_path: Path):
    """Bei ungueltigem Pfad wird `report_error` aufgerufen."""
    seen = []
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": str(tmp_path / "nope")},
        report_error=lambda ctx, err: seen.append((ctx, err)),
    )
    svc.get_projects_root_path()
    assert len(seen) == 1
    assert "ungueltig" in seen[0][0] or "ungültig" in seen[0][0]


def test_get_projects_root_path_swallows_report_error_exception(tmp_path: Path):
    """Eine kaputte `report_error`-Backdoor darf den Service nicht crashen."""

    def _boom_report(_ctx, _err):
        raise RuntimeError("report kaputt")

    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": str(tmp_path / "nope")},
        report_error=_boom_report,
    )
    # Kein Crash
    assert svc.get_projects_root_path() == tmp_path


# --- discover_projects -----------------------------------------------------


def test_discover_projects_finds_simple_book(tmp_path: Path):
    _touch_yml(tmp_path, "mybook/_quarto.yml")
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    assert svc.discover_projects() == [(tmp_path / "mybook").resolve()]


def test_discover_projects_finds_multiple_books(tmp_path: Path):
    _touch_yml(tmp_path, "alpha/_quarto.yml")
    _touch_yml(tmp_path, "beta/_quarto.yml")
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    found = {p.name for p in svc.discover_projects()}
    assert found == {"alpha", "beta"}


def test_discover_projects_excludes_venv(tmp_path: Path):
    """Buecher unter `.venv/...` werden ignoriert."""
    _touch_yml(tmp_path, "mybook/_quarto.yml")
    _touch_yml(tmp_path, ".venv/some_dep/_quarto.yml")
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    found = {p.name for p in svc.discover_projects()}
    assert "mybook" in found
    assert "some_dep" not in found
    assert ".venv" not in found


@pytest.mark.parametrize(
    "excluded_segment",
    sorted(EXCLUDED_PATH_SEGMENTS),
)
def test_discover_projects_excludes_all_known_segments(tmp_path: Path, excluded_segment: str):
    """Jedes Segment in `EXCLUDED_PATH_SEGMENTS` wird bei der Discovery ueberprungen."""
    _touch_yml(tmp_path, f"{excluded_segment}/_quarto.yml")
    _touch_yml(tmp_path, "visible/_quarto.yml")
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    found = {p.name for p in svc.discover_projects()}
    assert "visible" in found
    assert excluded_segment not in found


def test_discover_projects_empty_when_no_yml_files(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    assert svc.discover_projects() == []


def test_discover_projects_empty_when_root_missing(tmp_path: Path):
    """Wenn der konfigurierte Root nicht existiert, gibt der Service `[]` zurueck."""
    studio = _make_studio(tmp_path, tmp_path / "does_not_exist")
    svc = WorkspaceService(studio)
    assert svc.discover_projects() == []


def test_discover_projects_nested_books(tmp_path: Path):
    """Verschachtelte Buecher werden ebenfalls gefunden, solange kein Exclude-Segment im Pfad ist."""
    _touch_yml(tmp_path, "a/b/c/_quarto.yml")
    _touch_yml(tmp_path, "x/_quarto.yml")
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    found = sorted(p.name for p in svc.discover_projects())
    assert "c" in found
    assert "x" in found


# --- is_within_project -----------------------------------------------------


def test_is_within_project_true(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    assert svc.is_within_project(tmp_path / "sub" / "file.md") is True


def test_is_within_project_false(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    assert svc.is_within_project(Path("/elsewhere/file.md")) is False


def test_is_within_project_root_itself(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    # Der Root selbst ist eine Randbedingung: `relative_to` erlaubt das.
    assert svc.is_within_project(tmp_path) is True


def test_is_within_project_normalizes_dot_dot_segments(tmp_path: Path):
    """B-Fix (Code-Review 2026-07-03): ein Pfad mit `..`-Segmenten, der
    sich rechnerisch innerhalb des Projekt-Roots befindet, muss vor dem
    Vergleich aufgeloest werden."""
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    sibling_via_dotdot = tmp_path / "sub" / ".." / "sub" / "file.md"
    assert svc.is_within_project(sibling_via_dotdot) is True


def test_is_within_project_normalizes_root_with_dot_dot_segments(tmp_path: Path):
    """Auch wenn der konfigurierte Root selbst unnormalisiert ist (z. B.
    `.../sub/..`), muss der Vergleich funktionieren."""
    messy_root = tmp_path / "sub" / ".."
    studio = _make_studio(tmp_path, messy_root)
    svc = WorkspaceService(studio)
    assert svc.is_within_project(tmp_path / "file.md") is True


# --- Sanity: Service funktioniert auch ohne optionale Backdoors -----------


def test_service_works_without_any_backdoors(tmp_path: Path):
    """Konstruktor ohne `read_config`/`report_error` muss funktionieren."""
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(studio)
    assert svc.get_projects_root_path() == tmp_path
    assert svc.discover_projects() == []  # keine _quarto.yml im tmp_path
    assert svc.is_within_project(tmp_path / "x") is True


# --- Mehrere Projekt-Wurzeln (content_root_path als Liste) ----------------
# Regression: GrammarGraph legt Publish-Ordner in einem separaten Verzeichnis-
# baum ab (z.B. `IDE/GrammarGraph/Publish/...`), der nie unter dem
# Book-Studio-eigenen `content_root_path` liegt. Ohne Multi-Root-Unterstuetzung
# sind solche Projekte in der Dropdown-Liste nie auffindbar.


def test_normalize_content_root_paths_from_string():
    assert normalize_content_root_paths(".") == ["."]


def test_normalize_content_root_paths_from_list():
    assert normalize_content_root_paths([".", "../Other", "  ", 42]) == [".", "../Other"]


def test_normalize_content_root_paths_empty_cases():
    assert normalize_content_root_paths("") == []
    assert normalize_content_root_paths(None) == []
    assert normalize_content_root_paths([]) == []


def test_get_projects_root_paths_accepts_list(tmp_path: Path):
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": [str(root_a), str(root_b)]},
    )
    assert svc.get_projects_root_paths() == [root_a.resolve(), root_b.resolve()]
    # get_projects_root_path() bleibt abwärtskompatibel: erste Wurzel.
    assert svc.get_projects_root_path() == root_a.resolve()


def test_get_projects_root_paths_skips_invalid_entries_but_keeps_valid(tmp_path: Path):
    root_a = tmp_path / "root_a"
    root_a.mkdir()
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": [str(root_a), str(tmp_path / "nope")]},
    )
    assert svc.get_projects_root_paths() == [root_a.resolve()]


def test_get_projects_root_paths_falls_back_when_all_invalid(tmp_path: Path):
    studio = _make_studio(tmp_path, tmp_path)
    svc = WorkspaceService(
        studio,
        read_config=lambda: {"content_root_path": [str(tmp_path / "nope")]},
    )
    assert svc.get_projects_root_paths() == [tmp_path]


def test_discover_projects_scans_multiple_roots(tmp_path: Path):
    """Regression fuer den GrammarGraph-Publish-Bug: ein Buch ausserhalb des
    Haupt-Roots muss gefunden werden, wenn es als zweite Wurzel konfiguriert ist."""
    main_root = tmp_path / "book_studio_repo"
    external_root = tmp_path / "grammargraph_publish"
    main_root.mkdir()
    external_root.mkdir()
    _touch_yml(main_root, "Band_Dummy/_quarto.yml")
    _touch_yml(external_root, "Publish_Foo/_quarto.yml")

    studio = SimpleNamespace(
        base_path=tmp_path,
        projects_root_path=main_root,
        projects_root_paths=[main_root, external_root],
    )
    svc = WorkspaceService(studio)
    found = {p.name for p in svc.discover_projects()}
    assert found == {"Band_Dummy", "Publish_Foo"}


def test_discover_projects_dedupes_across_roots(tmp_path: Path):
    """Ueberlappende Wurzeln (z.B. ein Root ist Unterordner eines anderen)
    duerfen dasselbe Buch nicht doppelt liefern."""
    root = tmp_path / "root"
    root.mkdir()
    _touch_yml(root, "Band_Dummy/_quarto.yml")
    sub_root = root / "Band_Dummy"

    studio = SimpleNamespace(
        base_path=tmp_path,
        projects_root_path=root,
        projects_root_paths=[root, sub_root.parent],
    )
    svc = WorkspaceService(studio)
    found = [p.name for p in svc.discover_projects()]
    assert found == ["Band_Dummy"]


def test_is_within_project_checks_all_roots(tmp_path: Path):
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()
    studio = SimpleNamespace(
        base_path=tmp_path,
        projects_root_path=root_a,
        projects_root_paths=[root_a, root_b],
    )
    svc = WorkspaceService(studio)
    assert svc.is_within_project(root_b / "some_book" / "file.md") is True
    assert svc.is_within_project(tmp_path / "elsewhere" / "file.md") is False


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
