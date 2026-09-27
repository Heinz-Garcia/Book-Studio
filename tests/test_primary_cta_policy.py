"""Tests: Primär-CTA laut Mehrdeutigkeits-Policy (Batch D)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from services.work_path import assess_work_path, primary_cta_short


def _cfg(repo: Path) -> None:
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


def _book(repo: Path, name: str = "Prosa_X") -> Path:
    book = repo / "production" / "books" / name
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    return book


def _delivery(repo: Path, slug: str, run: str, *, uid: str | None = None) -> Path:
    path = repo / "production" / "inbox" / slug / run
    path.mkdir(parents=True)
    meta: dict = {"name": slug}
    if uid:
        meta["uuid"] = uid
    (path / "publish_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (path / f"{slug}.md").write_text("#\n", encoding="utf-8")
    return path


def test_cta_no_book_is_buch_waehlen(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _cfg(repo)
    _delivery(repo, "Prosa_X", "01.01.2026_12.00")
    state = assess_work_path(None, repo_root=repo)
    assert primary_cta_short(state) == "Buch wählen"


def test_cta_one_delivery_uebernehmen(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _cfg(repo)
    book = _book(repo)
    uid = str(uuid4())
    (book / "_book_studio.toml").write_text(
        f'[book]\ntitle = "X"\nuuid = "{uid}"\n', encoding="utf-8"
    )
    run = _delivery(repo, "Prosa_X", "01.01.2026_12.00", uid=uid)
    state = assess_work_path(book, repo_root=repo)
    assert state.next_action_id == "delivery_intake"
    label = primary_cta_short(state)
    assert label.startswith("Lieferung übernehmen")
    assert run.name in label
    assert "wählen" not in label


def test_cta_multiple_deliveries_waehlen(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _cfg(repo)
    book = _book(repo)
    uid = str(uuid4())
    (book / "_book_studio.toml").write_text(
        f'[book]\ntitle = "X"\nuuid = "{uid}"\n', encoding="utf-8"
    )
    _delivery(repo, "Prosa_X", "01.01.2026_12.00", uid=uid)
    _delivery(repo, "Prosa_X", "02.01.2026_12.00", uid=uid)
    state = assess_work_path(book, repo_root=repo)
    assert state.next_action_id == "delivery_intake"
    assert primary_cta_short(state) == "Lieferung wählen…"
