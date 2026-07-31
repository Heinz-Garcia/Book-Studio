"""Tests für production paths (Phase 0 — Klassifikation, Inventar, Legacy)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.production_paths.inventory import (
    is_legacy_import_under_publish_hub,
    scan_inventory,
)
from tools.production_paths.paths import (
    ProductionPathKind,
    classify_path,
    is_legacy_grammargraph_publish_path,
    legacy_publish_hubs_from_content_roots,
    resolve_legacy_publish_run,
    target_books_dir,
    target_inbox_dir,
)
from tools.publish_map.store import create_import_snapshot


def _minimal_quarto_book(path: Path, *, chapters: list[str] | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    ch = chapters or ["index.md"]
    yml = "project:\n  type: book\nbook:\n  chapters:\n"
    for item in ch:
        yml += f"    - {item}\n"
    (path / "_quarto.yml").write_text(yml, encoding="utf-8")
    (path / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")


def test_target_layout_paths(tmp_path: Path) -> None:
    root = tmp_path / "production"
    assert target_books_dir(root) == root / "books"
    assert target_inbox_dir(root) == root / "inbox"


def test_classify_legacy_publish_hub(tmp_path: Path) -> None:
    hub = tmp_path / "Publish"
    hub.mkdir()
    (hub / "Publish_A").mkdir()
    (hub / "Publish_B").mkdir()
    result = classify_path(hub)
    assert result.kind is ProductionPathKind.LEGACY_GG_PUBLISH_HUB


def test_classify_legacy_publish_run(tmp_path: Path) -> None:
    run = tmp_path / "Publish" / "Publish_Test_01.01.2026_12.00"
    run.mkdir(parents=True)
    (run / "publish_meta.json").write_text("{}", encoding="utf-8")
    (run / "payload.md").write_text("# Hi\n", encoding="utf-8")
    result = classify_path(run)
    assert result.kind is ProductionPathKind.LEGACY_GG_PUBLISH_RUN


def test_classify_legacy_publish_clone_book(tmp_path: Path) -> None:
    run = tmp_path / "Publish" / "Publish_IFJN_01.01.2026_12.00"
    _minimal_quarto_book(run, chapters=["index.md", "content/a.md"])
    (run / "bookconfig").mkdir()
    (run / "bookconfig" / "gui_state.json").write_text("{}", encoding="utf-8")
    result = classify_path(run)
    assert result.kind is ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK


def test_classify_working_book_outside_publish(tmp_path: Path) -> None:
    book = tmp_path / "Band_MeinBuch"
    _minimal_quarto_book(book)
    result = classify_path(book)
    assert result.kind is ProductionPathKind.WORKING_BOOK


def test_classify_target_books_and_inbox(tmp_path: Path) -> None:
    prod = tmp_path / "production"
    book = prod / "books" / "MeinBuch"
    _minimal_quarto_book(book)
    delivery = prod / "inbox" / "MeinBuch" / "2026-07-27"
    delivery.mkdir(parents=True)
    (delivery / "publish_meta.json").write_text("{}", encoding="utf-8")

    assert classify_path(book).kind is ProductionPathKind.TARGET_BOOKS
    assert classify_path(delivery).kind is ProductionPathKind.TARGET_INBOX


def test_is_legacy_grammargraph_publish_path() -> None:
    path = Path("C:/IDE/GrammarGraph/Publish/Publish_X")
    assert is_legacy_grammargraph_publish_path(path)
    assert not is_legacy_grammargraph_publish_path(Path("C:/production/books/X"))


def test_resolve_legacy_publish_run_from_md_file(tmp_path: Path) -> None:
    run = tmp_path / "Publish" / "Publish_ABC_01.01.2026_10.00"
    md = run / "content" / "kapitel.md"
    md.parent.mkdir(parents=True)
    md.write_text("# x\n", encoding="utf-8")
    resolved = resolve_legacy_publish_run(md)
    assert resolved == run.resolve()


def test_legacy_publish_hubs_from_content_roots(tmp_path: Path) -> None:
    gg_publish = tmp_path / "GrammarGraph" / "Publish"
    gg_publish.mkdir(parents=True)
    (gg_publish / "Publish_A").mkdir()
    roots = [tmp_path / "GrammarGraph" / "Publish"]
    hubs = legacy_publish_hubs_from_content_roots(tmp_path, content_roots=roots)
    assert gg_publish.resolve() in [h.resolve() for h in hubs]


def test_scan_inventory_finds_books_and_legacy_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "Studio"
    repo.mkdir()
    (repo / "app_config.json").write_text(
        json.dumps({"content_root_path": [".", str(tmp_path / "GG" / "Publish")]}),
        encoding="utf-8",
    )

    book = repo / "Band_Arbeitsbuch"
    _minimal_quarto_book(book)

    hub = tmp_path / "GG" / "Publish"
    hub.mkdir(parents=True)
    run_only = hub / "Publish_Lauf_01.01.2026_11.00"
    run_only.mkdir()
    (run_only / "publish_meta.json").write_text("{}", encoding="utf-8")

    clone = hub / "Publish_Klon_02.01.2026_12.00"
    _minimal_quarto_book(clone)
    (clone / "bookconfig").mkdir()

    def _fake_list_books(repo_path=None):
        del repo_path
        from tools.book_projects.catalog import BookInfo

        return [
            BookInfo(path=book, name=book.name, root=repo, display_name="Arbeitsbuch"),
            BookInfo(path=clone, name=clone.name, root=hub, display_name=""),
        ]

    monkeypatch.setattr("tools.production_paths.inventory.list_books", _fake_list_books)

    inv = scan_inventory(repo)
    assert len(inv.discovered_books) == 2
    assert any(e.kind == ProductionPathKind.LEGACY_PUBLISH_CLONE_BOOK.value for e in inv.discovered_books)
    assert any(e.path.resolve() == run_only.resolve() for e in inv.legacy_publish_runs)
    assert any("Legacy-Publish" in issue for issue in inv.issues)


def test_scan_inventory_publish_map_missing_import_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "Studio"
    book = repo / "MeinBuch"
    _minimal_quarto_book(book)
    missing = tmp_path / "gone" / "Publish_Old"
    create_import_snapshot(book, import_path=str(missing))

    def _fake_list_books(repo_path=None):
        del repo_path
        from tools.book_projects.catalog import BookInfo

        return [BookInfo(path=book, name=book.name, root=repo, display_name="")]

    monkeypatch.setattr("tools.production_paths.inventory.list_books", _fake_list_books)

    inv = scan_inventory(repo)
    assert len(inv.publish_map_refs) == 1
    assert inv.publish_map_refs[0].import_path_exists is False
    assert any("import_path fehlt" in issue for issue in inv.issues)


def test_is_legacy_import_under_publish_hub(tmp_path: Path) -> None:
    hub = tmp_path / "Publish"
    hub.mkdir()
    run = hub / "Publish_X"
    run.mkdir()
    assert is_legacy_import_under_publish_hub(str(run), [hub])
    assert not is_legacy_import_under_publish_hub(str(tmp_path / "books" / "X"), [hub])
