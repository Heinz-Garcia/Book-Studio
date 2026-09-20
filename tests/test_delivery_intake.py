"""Tests für services.delivery_intake — F′ Lieferung übernehmen."""

from __future__ import annotations

import json
from pathlib import Path

from services.delivery_intake import (
    accept_delivery,
    gate_f_ok,
    has_actionable_deliveries,
    list_actionable_deliveries,
    list_delivery_candidates,
)
from services.work_path import read_book_run


def _write_cfg(repo: Path) -> None:
    (repo / "app_config.json").write_text(
        json.dumps(
            {
                "content_root_path": ".",
                "production_root_path": "production",
                "books_workspace_path": "",
                "grammargraph_inbox_path": "",
            }
        ),
        encoding="utf-8",
    )


def _make_delivery(inbox_run: Path, *, title: str = "Laurel und Hardy") -> None:
    inbox_run.mkdir(parents=True)
    (inbox_run / "publish_meta.json").write_text(
        json.dumps({"book_title": title, "name": "Prosa_Laurel_and_Hardy"}),
        encoding="utf-8",
    )
    (inbox_run / "_book_studio.toml").write_text(
        f'[book]\ntitle = "{title}"\nauthor = "Test"\n',
        encoding="utf-8",
    )
    (inbox_run / "Prosa_Laurel_and_Hardy.md").write_text(
        "# Kapitel\n\nInhalt Laurel.\n",
        encoding="utf-8",
    )


def test_list_candidates_finds_inbox_run(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "24.08.2026_19.08"
    _make_delivery(run)

    found = list_delivery_candidates(repo)
    assert len(found) == 1
    assert found[0].path == run.resolve()
    assert found[0].project_slug == "Prosa_Laurel_and_Hardy"


def test_accept_delivery_sets_gate_f_and_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "24.08.2026_19.08"
    _make_delivery(run)

    result = accept_delivery(run, repo=repo)
    assert result.book_path.name == "Prosa_Laurel_and_Hardy"
    assert (result.book_path / "_quarto.yml").is_file()
    assert gate_f_ok(result.book_path)
    data = read_book_run(result.book_path)
    assert data["gates"]["F"]["status"] == "pass"
    assert Path(data["artifacts"]["delivery"]).resolve() == run.resolve()


def test_actionable_empty_after_accept_same_delivery(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "24.08.2026_19.08"
    _make_delivery(run)

    result = accept_delivery(run, repo=repo)
    assert not has_actionable_deliveries(repo, result.book_path)
    assert list_actionable_deliveries(repo, result.book_path) == []


def test_actionable_without_book_lists_all(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    _make_delivery(run, title="X")
    assert has_actionable_deliveries(repo, None)
    assert len(list_actionable_deliveries(repo, None)) == 1


def test_accept_delivery_applies_bundle_on_existing_book(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    book = repo / "production" / "books" / "Prosa_Laurel_and_Hardy"
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters: []\n",
        encoding="utf-8",
    )
    (book / "Inhalt.md").write_text(
        "---\ntitle: Alt\nstatus: bookstudio\n---\n\nalt body\n",
        encoding="utf-8",
    )
    (book / "bookconfig").mkdir()

    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "25.08.2026_10.00"
    _make_delivery(run, title="Laurel Neu")
    # Payload-Name muss für Bundle matchbar sein — große .md
    (run / "Inhalt_rev.md").write_text(
        "---\ntitle: Laurel Neu\n---\n\nneuer body aus Bundle\n",
        encoding="utf-8",
    )

    result = accept_delivery(run, repo=repo, apply_bundle=True)
    assert result.book_path == book.resolve()
    assert result.bundle_applied is True
    text = (book / "Inhalt.md").read_text(encoding="utf-8")
    assert "neuer body" in text
    data = read_book_run(book)
    assert data["artifacts"].get("bundle_swap") == "applied"


def test_happy_path_defaults_write_kdp_off(tmp_path: Path) -> None:
    from services.happy_path_defaults import ensure_happy_path_book_defaults
    from tools.kdp_cover.binding import resolve_cover_binding

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    out = ensure_happy_path_book_defaults(book, repo=tmp_path)
    assert out["kdp_default_off_written"] is True
    assert resolve_cover_binding(book).status == "off"
    # Idempotent
    out2 = ensure_happy_path_book_defaults(book, repo=tmp_path)
    assert out2["kdp_default_off_written"] is False
