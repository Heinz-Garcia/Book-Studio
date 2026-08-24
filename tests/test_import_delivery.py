"""Tests: Inbox-Lieferung → production/books/<Projekt>/ materialisieren."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.book_projects.import_delivery import (
    materialize_delivery_as_working_book,
    resolve_project_slug_for_delivery,
)


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
    (inbox_run / "Erstellungsprotokoll.md").write_text("# Protokoll\n", encoding="utf-8")


def test_resolve_slug_from_inbox_run_layout(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "24.08.2026_19.08"
    run.mkdir(parents=True)
    assert resolve_project_slug_for_delivery(run, repo=repo) == "Prosa_Laurel_and_Hardy"


def test_materialize_creates_books_project_not_timestamp(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "24.08.2026_19.08"
    _make_delivery(run)

    book = materialize_delivery_as_working_book(run, repo=repo)
    assert book.name == "Prosa_Laurel_and_Hardy"
    assert book.parent.name == "books"
    assert (book / "_quarto.yml").is_file()
    assert (book / "Prosa_Laurel_and_Hardy.md").is_file()
    assert "Laurel" in (book / "Prosa_Laurel_and_Hardy.md").read_text(encoding="utf-8")
    # Inbox bleibt Quelle
    assert (run / "Prosa_Laurel_and_Hardy.md").is_file()


def test_materialize_existing_book_syncs_payload(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    book = repo / "production" / "books" / "Prosa_Laurel_and_Hardy"
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters: []\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("# Alt\n", encoding="utf-8")
    (book / "bookconfig").mkdir()
    (book / "bookconfig" / "gui_state.json").write_text("{}", encoding="utf-8")

    run = repo / "production" / "inbox" / "Prosa_Laurel_and_Hardy" / "24.08.2026_19.08"
    _make_delivery(run, title="Laurel Neu")

    out = materialize_delivery_as_working_book(run, repo=repo)
    assert out == book.resolve()
    assert (book / "Prosa_Laurel_and_Hardy.md").is_file()
    assert (book / "bookconfig" / "gui_state.json").is_file()
    yml = (book / "_quarto.yml").read_text(encoding="utf-8")
    assert "Laurel Neu" in yml or "Laurel" in yml
