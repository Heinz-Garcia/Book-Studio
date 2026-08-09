"""Tests für Asset-Manager Reverse-Index und Pool-Pfade."""

from __future__ import annotations

from pathlib import Path

import app_config
from markdown_asset_scanner import collect_typst_image_refs, collect_typst_image_targets
from tools.asset_manager.pool import (
    DEFAULT_POOL_REL,
    ensure_pool_dir,
    list_image_files,
    list_pool_subdirs,
    read_configured_pool_path,
    resolve_pool_path,
    write_configured_pool_path,
)
from tools.asset_manager.refs import (
    build_image_ref_index,
    can_delete_book_image,
    list_book_images,
)
from ui_qt.editor_image import import_image_for_markdown


def test_collect_typst_image_refs_lines():
    text = 'prefix\n#image("/img/cover.png", width: 100%)\n'
    refs = collect_typst_image_refs(text)
    assert refs == [("/img/cover.png", 2)]
    assert collect_typst_image_targets(text) == ["/img/cover.png"]


def test_build_image_ref_index_md_and_typst(tmp_path: Path):
    book = tmp_path / "book"
    img = book / "img"
    content = book / "content"
    img.mkdir(parents=True)
    content.mkdir()
    (img / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (img / "orphan.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (content / "chapter.md").write_text(
        "![x](/img/cover.png)\n",
        encoding="utf-8",
    )
    (book / "page.typ").write_text(
        '#image("/img/cover.png")\n',
        encoding="utf-8",
    )

    index = build_image_ref_index(book)
    cover = (img / "cover.png").resolve()
    orphan = (img / "orphan.png").resolve()

    assert cover in index
    assert len(index[cover]) == 2
    paths = {hit.relative_path for hit in index[cover]}
    assert "content/chapter.md" in paths
    assert "page.typ" in paths
    assert orphan not in index
    assert can_delete_book_image(img / "orphan.png", index) is True
    assert can_delete_book_image(img / "cover.png", index) is False
    assert [p.name for p in list_book_images(book)] == ["cover.png", "orphan.png"]


def test_pool_resolve_and_persist(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app_config.json").write_text("{}", encoding="utf-8")

    resolved = resolve_pool_path(repo, DEFAULT_POOL_REL)
    assert resolved == (repo / "assets" / "pool").resolve()

    custom = tmp_path / "custom_pool"
    ensure_pool_dir(custom)
    (custom / "a.png").write_bytes(b"x")
    assert [p.name for p in list_image_files(custom)] == ["a.png"]

    saved = write_configured_pool_path(custom, repo)
    assert saved == custom.resolve()
    cfg = app_config.load_validated_config(repo / "app_config.json")
    assert Path(cfg["asset_pool_path"]).name == "custom_pool"
    assert read_configured_pool_path(repo) == custom.resolve()


def test_list_pool_subdirs_recursive_sorted_no_hidden(tmp_path: Path):
    pool = tmp_path / "pool"
    (pool / "charaktere" / "nebenfiguren").mkdir(parents=True)
    (pool / "orte").mkdir(parents=True)
    (pool / ".git").mkdir(parents=True)
    (pool / "orte" / "a.png").write_bytes(b"x")

    subdirs = [p.as_posix() for p in list_pool_subdirs(pool)]
    assert subdirs == ["charaktere", "charaktere/nebenfiguren", "orte"]
    assert list_pool_subdirs(tmp_path / "missing") == []


def test_import_image_for_markdown_from_pool(tmp_path: Path):
    book = tmp_path / "book"
    pool = tmp_path / "pool"
    book.mkdir()
    pool.mkdir()
    source = pool / "foto.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n")

    ref, dest = import_image_for_markdown(source, book)
    assert ref == "/img/foto.png"
    assert dest == book / "img" / "foto.png"
    assert dest.is_file()
