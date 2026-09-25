"""Tests: Buch ↔ geplantes Cover binden."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.kdp_cover.bind_book import (
    bind_cover_to_book,
    planned_candidates_for_book,
    resolve_cover_book_binding,
)
from tools.kdp_cover.cover_registry import load_registry
from tools.kdp_cover.model import CoverLayout, save_layout
from tools.kdp_cover.planned_uuid import create_planned_cover_uuid


def _book_with_uuid(root: Path, name: str, uid: str) -> Path:
    book = root / name
    book.mkdir(parents=True)
    (book / "publish_meta.json").write_text(
        json.dumps({"uuid": uid}), encoding="utf-8"
    )
    return book


def _write_layout(path: Path, *, title: str = "Titel") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    layout = CoverLayout(
        page_count=100,
        paper_type_id="white",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        title=title,
        author="Autor",
    )
    save_layout(layout, path)


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from tools.kdp_cover import cover_registry as reg_mod

    reg = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(reg_mod, "registry_path", lambda: reg)
    return reg


def test_auto_bind_when_exactly_one_planned_matches(
    tmp_path: Path, registry: Path
) -> None:
    planned = create_planned_cover_uuid(
        title_hint="Wald",
        series_id="S1",
        repo=tmp_path,
        registry_file=registry,
    )
    _write_layout(Path(planned.cover_path), title="Wald")
    book = _book_with_uuid(tmp_path, "MeinBuch", planned.production_uuid)

    result = resolve_cover_book_binding(book, registry_file=registry, repo=tmp_path)
    assert result.status == "auto"
    assert result.production_uuid == planned.production_uuid
    assert result.mirrored_layout
    assert result.mirror_layout is not None
    assert result.mirror_layout.is_file()
    assert result.mirror_layout.parent.name == "kdp_cover"

    data = load_registry(registry)
    assert data["entries"][0]["book_path"]
    assert "MeinBuch" in data["entries"][0]["book_path"]
    assert "bound_book" in data["entries"][0]["source_kinds"]


def test_needs_choice_when_book_has_no_uuid_and_multiple_planned(
    tmp_path: Path, registry: Path
) -> None:
    create_planned_cover_uuid(
        title_hint="A", repo=tmp_path, registry_file=registry
    )
    create_planned_cover_uuid(
        title_hint="B", repo=tmp_path, registry_file=registry
    )
    book = tmp_path / "OhneUuid"
    book.mkdir()

    result = resolve_cover_book_binding(book, registry_file=registry)
    assert result.status == "needs_choice"
    assert len(result.candidates) == 2


def test_explicit_bind_from_choice(tmp_path: Path, registry: Path) -> None:
    a = create_planned_cover_uuid(
        title_hint="A", repo=tmp_path, registry_file=registry
    )
    b = create_planned_cover_uuid(
        title_hint="B", repo=tmp_path, registry_file=registry
    )
    _write_layout(Path(b.cover_path), title="B")
    book = tmp_path / "WahlBuch"
    book.mkdir()

    result = bind_cover_to_book(
        book, b.production_uuid, registry_file=registry, repo=tmp_path
    )
    assert result.status == "chosen"
    assert result.production_uuid == b.production_uuid
    assert result.mirrored_layout

    # A bleibt ungebunden
    cands = planned_candidates_for_book(book, registry_file=registry)
    # Nach dem Binden trägt das Buch B, und B ist nicht mehr „geplant“ —
    # für dieses Buch gibt es nichts mehr zu wählen (auch A nicht).
    assert [c.production_uuid for c in cands] == []
    from tools.kdp_cover.planned_uuid import list_planned_cover_uuids

    listed = list_planned_cover_uuids(registry_file=registry)
    uids = {r["production_uuid"] for r in listed}
    assert a.production_uuid in uids
    assert b.production_uuid not in uids


def test_no_match_when_book_uuid_unknown(tmp_path: Path, registry: Path) -> None:
    create_planned_cover_uuid(
        title_hint="Andere", repo=tmp_path, registry_file=registry
    )
    book = _book_with_uuid(
        tmp_path, "Buch", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )
    result = resolve_cover_book_binding(book, registry_file=registry)
    assert result.status == "no_match"


def test_book_without_uuid_is_never_auto_bound(tmp_path: Path, registry: Path) -> None:
    """Regression: EIN geplantes Cover in der Registry reichte, um jedes Buch
    ohne UUID automatisch daran zu binden."""
    create_planned_cover_uuid(title_hint="Einzig", repo=tmp_path, registry_file=registry)
    book = tmp_path / "OhneUuid"
    book.mkdir()

    result = resolve_cover_book_binding(book, registry_file=registry)
    assert result.status == "needs_choice"
    assert len(result.candidates) == 1
    assert not load_registry(registry)["entries"][0]["book_path"]


def test_binding_never_steals_a_cover_bound_to_another_book(
    tmp_path: Path, registry: Path
) -> None:
    planned = create_planned_cover_uuid(title_hint="A", repo=tmp_path, registry_file=registry)
    _write_layout(Path(planned.cover_path), title="A")
    first = _book_with_uuid(tmp_path, "Erstes", planned.production_uuid)
    second = tmp_path / "Zweites"
    second.mkdir()

    assert bind_cover_to_book(first, planned.production_uuid, registry_file=registry).status == "chosen"
    result = bind_cover_to_book(second, planned.production_uuid, registry_file=registry)

    assert result.status == "conflict"
    entry = load_registry(registry)["entries"][0]
    assert Path(entry["book_path"]).name == "Erstes"
    assert not (second / "export").exists()


def test_saving_in_the_designer_keeps_binding_series_and_origin(
    tmp_path: Path, registry: Path
) -> None:
    """Regression: ``upsert_cover_link`` (Speichern im Cover-Designer) ersetzte
    den Eintrag -- ohne aktives Buch war die Bindung weg, dazu series_id und
    die Herkunfts-Kennungen."""
    from tools.kdp_cover.cover_registry import upsert_cover_link

    planned = create_planned_cover_uuid(
        title_hint="Wald", series_id="S1", repo=tmp_path, registry_file=registry
    )
    _write_layout(Path(planned.cover_path), title="Wald")
    book = _book_with_uuid(tmp_path, "MeinBuch", planned.production_uuid)
    bind_cover_to_book(book, planned.production_uuid, registry_file=registry)

    # Designer ohne aktives Buch speichert dasselbe Layout
    upsert_cover_link(
        production_uuid=planned.production_uuid,
        cover_path=planned.cover_path,
        book_path=None,
        title_hint="Wald (neu)",
        source_kinds=["book_studio"],
        path=registry,
    )

    entries = load_registry(registry)["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert Path(entry["book_path"]).name == "MeinBuch"
    assert entry["series_id"] == "S1"
    assert entry["title_hint"] == "Wald (neu)"
    assert {"planned_cover", "bound_book", "book_studio"} <= set(entry["source_kinds"])
