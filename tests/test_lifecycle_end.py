"""Tests: services.lifecycle_end — orchestriertes Lebensende."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from services.lifecycle_end import plan_lifecycle_end, run_lifecycle_end


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


def _make_book(repo: Path, name: str, *, uid: str | None = None) -> Path:
    book = repo / "production" / "books" / name
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    if uid:
        (book / "_book_studio.toml").write_text(
            f'[book]\ntitle = "{name}"\nuuid = "{uid}"\n',
            encoding="utf-8",
        )
    return book


def _make_delivery(repo: Path, slug: str, run: str, *, uid: str | None = None) -> Path:
    path = repo / "production" / "inbox" / slug / run
    path.mkdir(parents=True)
    meta: dict = {"book_title": slug, "name": slug}
    if uid:
        meta["uuid"] = uid
    (path / "publish_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (path / f"{slug}.md").write_text("# x\n", encoding="utf-8")
    return path


def test_plan_without_band_run_warns_and_defaults_off(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    book = _make_book(repo, "Prosa_X", uid=uid)
    _make_delivery(repo, "Prosa_X", "01.01.2026_12.00", uid=uid)

    plan = plan_lifecycle_end(book, repo=repo)
    assert plan.warning
    assert plan.has_band_run is False
    assert plan.default_include_inbox is False
    assert len(plan.inbox_paths) >= 1


def test_run_wrong_name_cancels(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    book = _make_book(repo, "Prosa_X")
    result = run_lifecycle_end(
        book, repo=repo, confirm_name="Falsch", include_inbox=False, include_gg=False
    )
    assert result.status == "cancelled"
    assert book.is_dir()


def test_run_blocks_active_book(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    book = _make_book(repo, "Prosa_X")
    result = run_lifecycle_end(
        book,
        repo=repo,
        confirm_name="Prosa_X",
        include_inbox=False,
        include_gg=False,
        active_book=book,
    )
    assert result.status == "blocked"
    assert book.is_dir()


def test_run_trashes_book_and_inbox_writes_tombstone(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    book = _make_book(repo, "Prosa_X", uid=uid)
    delivery = _make_delivery(repo, "Prosa_X", "01.01.2026_12.00", uid=uid)

    from services.band_run import empty_band_run, write_band_run

    data = empty_band_run(uid, updated_by="bs")
    data["paths"]["book"] = str(book)
    data["paths"]["delivery"] = str(delivery)
    write_band_run(data, production_root=repo / "production", repo=repo)

    result = run_lifecycle_end(
        book,
        repo=repo,
        confirm_name="Prosa_X",
        include_inbox=True,
        include_gg=False,
    )
    assert result.status == "ok"
    assert result.tombstone_written
    assert not book.exists()
    assert not delivery.exists()

    from services.band_run import read_band_run

    band = read_band_run(uid, production_root=repo / "production")
    assert band is not None
    assert band["lifecycle"] == "tombstoned"
    assert isinstance(band.get("tombstone"), dict)
    assert any("Cover-Registry" in x for x in band["tombstone"]["left_behind"])
    assert str(book.resolve()) in band["tombstone"]["deleted"]


def test_inbox_foreign_uuid_not_matched(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    other = str(uuid4())
    book = _make_book(repo, "Prosa_X", uid=uid)
    foreign = _make_delivery(repo, "Prosa_X", "01.01.2026_12.00", uid=other)

    plan = plan_lifecycle_end(book, repo=repo)
    assert foreign.resolve() not in plan.inbox_paths


def test_quellen_nie_vorbelegt_nur_ausdruecklich(tmp_path: Path, monkeypatch) -> None:
    """B-05 (Nutzer, 2026-09-29): Quellen werden nie automatisch entsorgt --
    auch bei 1:1-Bindung und vorhandenem band_run sind die Häkchen aus; wer
    sie ausdrücklich setzt, entsorgt sie."""
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    book = _make_book(repo, "Prosa_X", uid=uid)

    gg = tmp_path / "GrammarGraph"
    proj = gg / "projects" / "Prosa_X"
    proj.mkdir(parents=True)
    (proj / "production_uuid.json").write_text(
        json.dumps({"production_uuid": uid}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tools.path_favorites.placeholders.discover_grammargraph_root",
        lambda **_k: gg,
    )

    from services.band_run import empty_band_run, write_band_run

    data = empty_band_run(uid, updated_by="bs")
    data["paths"]["book"] = str(book)
    data["paths"]["gg_project"] = str(proj)
    write_band_run(data, production_root=repo / "production", repo=repo)

    lieferung = _make_delivery(repo, "Prosa_X", "01.01.2026_12.00", uid=uid)
    plan = plan_lifecycle_end(book, repo=repo)
    assert plan.gg_bound_1to1
    assert plan.default_include_gg is False  # nie vorbelegt
    assert plan.has_band_run and lieferung.resolve() in plan.inbox_paths
    assert plan.default_include_inbox is False  # auch mit band_run nicht
    assert plan.gg_project == proj.resolve()

    result = run_lifecycle_end(
        book,
        repo=repo,
        confirm_name="Prosa_X",
        include_inbox=False,
        include_gg=True,
    )
    assert result.status == "ok"
    assert not proj.exists()
    assert str(proj.resolve()) in result.deleted
    assert lieferung.exists()  # nicht angehakt -> bleibt


def test_ohne_haekchen_bleiben_quellen_stehen(tmp_path: Path) -> None:
    """Aufruf ohne include_*: Die Vorgabe entsorgt keine Quelle (B-05)."""
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    book = _make_book(repo, "Prosa_Y", uid=uid)
    lieferung = _make_delivery(repo, "Prosa_Y", "01.01.2026_12.00", uid=uid)
    result = run_lifecycle_end(book, repo=repo, confirm_name="Prosa_Y")
    assert result.status == "ok"
    assert not book.exists()
    assert lieferung.exists()
