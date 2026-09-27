"""Tests: services.delivery_bridge — Brücke Lieferung→Buch(+Cover)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


from services.delivery_bridge import pick_delivery_for_bridge, run_delivery_bridge
from services.delivery_intake import gate_f_ok
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


def _make_delivery(
    inbox_run: Path,
    *,
    title: str = "Laurel und Hardy",
    slug: str = "Prosa_Laurel_and_Hardy",
    uid: str | None = None,
) -> None:
    inbox_run.mkdir(parents=True)
    meta: dict = {"book_title": title, "name": slug}
    if uid:
        meta["uuid"] = uid
    (inbox_run / "publish_meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    toml = f'[book]\ntitle = "{title}"\nauthor = "Test"\n'
    if uid:
        toml += f'uuid = "{uid}"\n'
    (inbox_run / "_book_studio.toml").write_text(toml, encoding="utf-8")
    (inbox_run / f"{slug}.md").write_text("# Kapitel\n\nInhalt.\n", encoding="utf-8")


def test_pick_one_delivery_is_ok(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    run = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    _make_delivery(run, slug="Prosa_X", title="X")
    pick = pick_delivery_for_bridge(repo)
    assert pick.status == "ok"
    assert pick.delivery_path == run.resolve()


def test_pick_multiple_needs_choice(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    a = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    b = repo / "production" / "inbox" / "Prosa_X" / "02.01.2026_12.00"
    _make_delivery(a, slug="Prosa_X", title="X")
    _make_delivery(b, slug="Prosa_X", title="X")
    # touch b newer
    b.joinpath("x.md").write_text("n", encoding="utf-8")
    pick = pick_delivery_for_bridge(repo)
    assert pick.status == "need_pick"
    assert len(pick.candidates) >= 2
    assert pick.recommended is not None


def test_bridge_happy_path_sets_gate_and_band_run(tmp_path: Path) -> None:
    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    run = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    _make_delivery(run, slug="Prosa_X", title="X", uid=uid)

    result = run_delivery_bridge(repo, delivery=run)
    assert result.status == "ok"
    assert result.book_path is not None
    assert gate_f_ok(result.book_path)
    data = read_book_run(result.book_path)
    assert data["gates"]["F"]["status"] == "pass"

    from services.band_run import read_band_run

    band = read_band_run(uid, production_root=repo / "production")
    assert band is not None
    assert Path(band["paths"]["book"]).resolve() == result.book_path.resolve()
    assert Path(band["paths"]["delivery"]).resolve() == run.resolve()


def test_bridge_interrupt_without_primary_cover(tmp_path: Path, monkeypatch) -> None:
    """Nur Alternativen in der Registry → interrupt, kein Auto-Fallback."""
    from tools.kdp_cover.cover_registry import CoverRegistryEntry

    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    run = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    _make_delivery(run, slug="Prosa_X", title="X", uid=uid)

    alt = CoverRegistryEntry(
        production_uuid=uid,
        cover_path=str(tmp_path / "alt.json"),
        cover_role="alternative",
        cover_label="Alt",
    )
    (tmp_path / "alt.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "tools.kdp_cover.cover_registry.resolve_primary_cover",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "tools.kdp_cover.cover_registry.list_covers_for_uuid",
        lambda *_a, **_k: [alt],
    )

    result = run_delivery_bridge(repo, delivery=run)
    assert result.status == "interrupt"
    assert "Primary" in result.message
    assert result.book_path is not None
    assert gate_f_ok(result.book_path)


def test_bridge_cover_conflict(tmp_path: Path, monkeypatch) -> None:
    from tools.kdp_cover.bind_book import BindResult

    repo = tmp_path / "BS"
    repo.mkdir()
    _write_cfg(repo)
    uid = str(uuid4())
    run = repo / "production" / "inbox" / "Prosa_X" / "01.01.2026_12.00"
    _make_delivery(run, slug="Prosa_X", title="X", uid=uid)

    class _Primary:
        cover_path = str(tmp_path / "p.json")
        cover_role = "primary"

    (tmp_path / "p.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "tools.kdp_cover.cover_registry.resolve_primary_cover",
        lambda *_a, **_k: _Primary(),
    )
    monkeypatch.setattr(
        "tools.kdp_cover.cover_registry.list_covers_for_uuid",
        lambda *_a, **_k: [_Primary()],
    )
    monkeypatch.setattr(
        "tools.kdp_cover.bind_book.bind_cover_to_book",
        lambda *_a, **_k: BindResult(
            status="conflict",
            production_uuid=uid,
            message="UUID-Konflikt Test",
        ),
    )

    result = run_delivery_bridge(repo, delivery=run)
    assert result.status == "conflict"
    assert "Konflikt" in result.message or "Konflikt" in result.cover_bind_message
