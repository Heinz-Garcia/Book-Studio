"""Tests für Skeleton Phase 3 (Diff, Config, missing_only)."""

from __future__ import annotations

from pathlib import Path

from tools.skeleton.config import read_skeleton_settings, set_default_profile, write_skeleton_settings
from tools.skeleton.diff import build_diff_map, compute_file_diff
from tools.skeleton.manifest import delete_profile, duplicate_profile
from tools.skeleton.populate import build_populate_plan, populate_book, resolve_populate_plan
from tools.skeleton.manifest import load_manifest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _standard_profile() -> Path:
    return _repo_root() / "tools" / "skeleton" / "library" / "standard"


def _create_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n\n# Index\n", encoding="utf-8")
    return book


def test_compute_file_diff_detects_changes(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    rel = "content/required/Einleitung.md"
    target = book / rel
    target.parent.mkdir(parents=True)
    target.write_text("# Alt\n", encoding="utf-8")
    info = compute_file_diff(rel, skeleton_root=_standard_profile(), book_root=book)
    assert info.exists_in_book
    assert info.changed
    assert info.added_lines > 0


def test_build_diff_map_has_all_paths(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    manifest = load_manifest(_standard_profile())
    diff_map = build_diff_map(
        [e.path for e in manifest.files],
        skeleton_root=_standard_profile(),
        book_root=book,
    )
    assert len(diff_map) == len(manifest.files)


def test_missing_only_skips_existing(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    existing = book / "content/required/Einleitung.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# Alt\n", encoding="utf-8")
    manifest = load_manifest(_standard_profile())
    plan = build_populate_plan(
        manifest,
        book,
        conflict_mode="replace",
        populate_mode="missing_only",
        include_diff=False,
    )
    einleitung = next(line for line in plan if line.rel_path.endswith("Einleitung.md"))
    assert einleitung.exists
    assert einleitung.will_copy is False


def test_resolve_populate_plan_missing_only(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    manifest = load_manifest(_standard_profile())
    base = build_populate_plan(manifest, book, include_diff=False)
    resolved = resolve_populate_plan(base, conflict_choice="replace", missing_only=True)
    assert all(not line.will_copy for line in resolved if line.exists)


def test_populate_missing_only_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    existing = book / "content/required/Einleitung.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# Alt\n", encoding="utf-8")
    result = populate_book(
        book,
        profile_dir=_standard_profile(),
        conflict_mode="skip",
        populate_mode="missing_only",
        skip_dialog=True,
    )
    assert result.ok
    assert "content/required/Einleitung.md" in result.skipped
    assert "# Alt" in existing.read_text(encoding="utf-8")


def test_skeleton_settings_roundtrip(tmp_path: Path) -> None:
    cfg = tmp_path / "app_config.json"
    cfg.write_text("{}", encoding="utf-8")
    write_skeleton_settings(tmp_path, default_profile="custom", populate_mode="missing_only")
    settings = read_skeleton_settings(tmp_path)
    assert settings["default_profile"] == "custom"
    assert settings["populate_mode"] == "missing_only"


def test_set_default_profile_updates_config(tmp_path: Path) -> None:
    cfg = tmp_path / "app_config.json"
    cfg.write_text('{"skeleton_default_profile": "standard"}', encoding="utf-8")
    set_default_profile(tmp_path, "mein_profil")
    settings = read_skeleton_settings(tmp_path)
    assert settings["default_profile"] == "mein_profil"


def test_delete_profile_removes_directory(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    import shutil

    shutil.copytree(_standard_profile(), library / "copy_me")
    delete_profile(library, "copy_me")
    assert not (library / "copy_me").exists()


def test_delete_profile_protects_standard(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    import shutil

    shutil.copytree(_standard_profile(), library / "standard")
    try:
        delete_profile(library, "standard")
        assert False, "expected ValueError"
    except ValueError:
        pass
