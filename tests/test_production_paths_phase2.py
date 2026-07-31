"""Phase-2-Tests: Migration dry-run, apply, publish_map, rollback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.production_paths.migrate import (
    build_migration_plan,
    derive_book_folder_name,
    execute_migration_plan,
    rollback_migration,
)
from tools.production_paths.paths import ProductionPathKind, classify_path
from tools.publish_map.store import create_import_snapshot, read_map


def _minimal_quarto_book(path: Path, *, with_bookconfig: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (path / "index.md").write_text("---\ntitle: T\n---\n", encoding="utf-8")
    if with_bookconfig:
        (path / "bookconfig").mkdir()
        (path / "bookconfig" / "gui_state.json").write_text("{}", encoding="utf-8")


def _write_cfg(repo: Path, **overrides: object) -> None:
    data = {
        "content_root_path": ".",
        "production_root_path": "production",
        "books_workspace_path": "",
        "grammargraph_inbox_path": "",
    }
    data.update(overrides)
    (repo / "app_config.json").write_text(json.dumps(data), encoding="utf-8")


def test_derive_book_folder_name_from_publish() -> None:
    assert (
        derive_book_folder_name("Publish_IFJN_Brustkrebs_24.07.26_27.07.2026_22.53")
        == "IFJN_Brustkrebs_24.07.26_27.07.2026_22.53"
    )
    assert derive_book_folder_name("Publish_X", display_name="Brustkrebs") == "Brustkrebs"


def test_plan_migrate_clone_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hub = tmp_path / "Publish"
    hub.mkdir()
    clone = hub / "Publish_IFJN_Brustkrebs_24.07.26_27.07.2026_22.53"
    _minimal_quarto_book(clone, with_bookconfig=True)
    _write_cfg(repo, content_root_path=[str(hub)])

    def _fake_list_books(repo_path=None):
        del repo_path
        from tools.book_projects.catalog import BookInfo

        return [BookInfo(path=clone, name=clone.name, root=hub, display_name="Brustkrebs")]

    monkeypatch.setattr("tools.production_paths.inventory.list_books", _fake_list_books)

    plan = build_migration_plan(repo, migrate_deliveries=False)
    move_steps = [s for s in plan.steps if s.kind.value == "move_book"]
    assert len(move_steps) == 1
    assert move_steps[0].target.parent.name == "books"
    assert move_steps[0].target.name == "Brustkrebs"


def test_apply_migrate_clone_book_and_publish_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hub = tmp_path / "Publish"
    hub.mkdir()
    delivery = hub / "Publish_IFJN_Brustkrebs_24.07.26_27.07.2026_22.53"
    _minimal_quarto_book(delivery, with_bookconfig=True)
    (delivery / "publish_meta.json").write_text("{}", encoding="utf-8")
    _write_cfg(repo, content_root_path=[str(hub)])

    create_import_snapshot(delivery, import_path=str(delivery))

    def _fake_list_books(repo_path=None):
        del repo_path
        from tools.book_projects.catalog import BookInfo

        return [BookInfo(path=delivery, name=delivery.name, root=hub, display_name="")]

    monkeypatch.setattr("tools.production_paths.inventory.list_books", _fake_list_books)

    plan = build_migration_plan(repo, migrate_deliveries=False)
    result = execute_migration_plan(plan, apply=True, manifest_path=repo / "migration.json")
    assert not result.errors
    assert len(result.moved) == 1
    new_book = result.moved[0][1]
    assert new_book.is_dir()
    assert classify_path(new_book).kind is ProductionPathKind.TARGET_BOOKS
    data = read_map(new_book)
    assert data is not None
    snap = data["snapshots"][0]
    assert snap.get("migrated_from", {}).get("import_path") == str(delivery)
    assert Path(str(snap.get("import_path"))).resolve() == new_book.resolve()


def test_apply_migrate_delivery_to_inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hub = tmp_path / "Publish"
    hub.mkdir()
    run = hub / "Publish_IFJN_Brustkrebs_24.07.26_27.07.2026_22.53"
    run.mkdir()
    (run / "publish_meta.json").write_text("{}", encoding="utf-8")
    (run / "payload.md").write_text("# Hi\n", encoding="utf-8")
    _write_cfg(repo, content_root_path=[str(hub)])

    def _fake_list_books(repo_path=None):
        del repo_path
        return []

    monkeypatch.setattr("tools.production_paths.inventory.list_books", _fake_list_books)

    plan = build_migration_plan(repo, migrate_books=False)
    result = execute_migration_plan(plan, apply=True)
    assert not result.errors
    assert len(result.moved) == 1
    target = result.moved[0][1]
    assert "inbox" in target.parts
    assert target.name.startswith("27.07.2026")


def test_rollback_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hub = tmp_path / "Publish"
    hub.mkdir()
    clone = hub / "Publish_Test_01.01.2026_12.00"
    _minimal_quarto_book(clone, with_bookconfig=True)
    _write_cfg(repo, content_root_path=[str(hub)])

    def _fake_list_books(repo_path=None):
        del repo_path
        from tools.book_projects.catalog import BookInfo

        return [BookInfo(path=clone, name=clone.name, root=hub, display_name="")]

    monkeypatch.setattr("tools.production_paths.inventory.list_books", _fake_list_books)

    plan = build_migration_plan(repo, migrate_deliveries=False)
    manifest = repo / "migration.json"
    execute_migration_plan(plan, apply=True, manifest_path=manifest)
    assert not clone.exists()
    rollback_migration(manifest, apply=True)
    assert clone.is_dir()
    assert not (repo / "production" / "books" / "Test").exists()
