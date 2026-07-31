"""Phase-1-Tests: Dual-Read Discovery, books/inbox Config, Filter."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.workspace_service import WorkspaceService
from tools.book_projects.catalog import (
    default_new_book_parent,
    ensure_book_discoverable,
    list_books,
)
from tools.production_paths.config import (
    ensure_books_workspace_dir,
    resolve_books_workspace_roots,
    resolve_grammargraph_inbox_roots,
)
from tools.production_paths.paths import (
    ProductionPathKind,
    classify_path,
    is_book_discovery_candidate,
)


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


def test_resolve_books_workspace_roots_includes_legacy_and_books(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    books = repo / "production" / "books"
    books.mkdir(parents=True)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    _write_cfg(repo, content_root_path=[str(legacy)])

    cfg = json.loads((repo / "app_config.json").read_text(encoding="utf-8"))
    roots = resolve_books_workspace_roots(cfg, repo)
    assert books.resolve() in roots
    assert legacy.resolve() in roots


def test_resolve_grammargraph_inbox_roots_legacy_publish_hub(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hub = tmp_path / "GG" / "Publish"
    (hub / "Publish_A").mkdir(parents=True)
    (hub / "Publish_B").mkdir()
    inbox = repo / "production" / "inbox"
    inbox.mkdir(parents=True)
    _write_cfg(repo, content_root_path=[str(hub)])

    cfg = json.loads((repo / "app_config.json").read_text(encoding="utf-8"))
    roots = resolve_grammargraph_inbox_roots(cfg, repo)
    assert inbox.resolve() in roots
    assert hub.resolve() in roots


def test_default_new_book_parent_creates_books_dir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_cfg(repo)
    parent = default_new_book_parent(repo)
    assert parent.is_dir()
    assert parent.name == "books"
    assert parent.parent.name == "production"


def test_discover_projects_filters_pure_publish_runs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    hub = tmp_path / "Publish"
    hub.mkdir()
    repo.mkdir()
    _write_cfg(repo, content_root_path=[str(hub)])

    pure = hub / "Publish_Lauf_01.01.2026_12.00"
    _minimal_quarto_book(pure)
    (pure / "publish_meta.json").write_text("{}", encoding="utf-8")

    clone = hub / "Publish_Klon_02.01.2026_12.00"
    _minimal_quarto_book(clone, with_bookconfig=True)

    host = SimpleNamespace(
        base_path=repo,
        projects_root_path=hub,
        projects_root_paths=[hub],
        books=[],
    )

    def _read() -> dict:
        return json.loads((repo / "app_config.json").read_text(encoding="utf-8"))

    ws = WorkspaceService(host, read_config=_read)
    host.projects_root_paths = ws.get_projects_root_paths()
    found = {p.resolve() for p in ws.discover_projects()}

    assert pure.resolve() not in found
    assert clone.resolve() in found
    assert not is_book_discovery_candidate(pure)
    assert is_book_discovery_candidate(clone)


def test_ensure_book_discoverable_under_books_skips_content_root_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_cfg(repo, content_root_path=str(tmp_path / "only_legacy"))
    (tmp_path / "only_legacy").mkdir()

    books = ensure_books_workspace_dir(
        json.loads((repo / "app_config.json").read_text(encoding="utf-8")),
        repo,
    )
    book = books / "Neu"
    _minimal_quarto_book(book)

    ensure_book_discoverable(book, repo=repo)
    entries = json.loads((repo / "app_config.json").read_text(encoding="utf-8"))["content_root_path"]
    if isinstance(entries, list):
        paths = {Path(e).resolve() for e in entries}
    else:
        paths = {Path(entries).resolve()}
    assert book.parent.resolve() not in paths


def test_classify_and_filter_kinds() -> None:
    assert ProductionPathKind.LEGACY_GG_PUBLISH_RUN not in {
        ProductionPathKind.TARGET_BOOKS,
        ProductionPathKind.WORKING_BOOK,
        ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK,
    }
