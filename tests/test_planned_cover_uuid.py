"""Tests for planned Cover-first production UUIDs."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.kdp_cover.cover_registry import load_registry
from tools.kdp_cover.planned_uuid import (
    SOURCE_KIND_PLANNED,
    create_planned_cover_uuid,
    list_planned_cover_uuids,
)
from tools.kdp_cover.uuid_choices import ORIGIN_PLANNED, list_production_uuid_choices


def test_create_planned_cover_uuid_makes_dir_and_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.kdp_cover import cover_registry as reg_mod

    reg = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(reg_mod, "registry_path", lambda: reg)

    planned = create_planned_cover_uuid(
        title_hint="IFJN_Andalusien",
        series_id="ABC",
        repo=tmp_path,
        registry_file=reg,
    )
    assert planned.production_uuid
    assert planned.title_hint == "IFJN_Andalusien"
    assert planned.series_id == "ABC"
    assert planned.cover_dir.is_dir()
    assert planned.production_uuid in str(planned.cover_dir)
    assert planned.entry.series_id == "ABC"
    assert SOURCE_KIND_PLANNED in planned.entry.source_kinds
    assert not planned.entry.book_path

    data = load_registry(reg)
    assert len(data["entries"]) == 1
    assert data["entries"][0]["title_hint"] == "IFJN_Andalusien"
    assert data["entries"][0]["series_id"] == "ABC"

    listed = list_planned_cover_uuids(registry_file=reg)
    assert len(listed) == 1
    assert listed[0]["production_uuid"] == planned.production_uuid
    assert listed[0]["title_hint"] == "IFJN_Andalusien"


def test_bound_entry_leaves_planned_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.kdp_cover import cover_registry as reg_mod
    from tools.kdp_cover.bind_book import bind_cover_to_book

    reg = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(reg_mod, "registry_path", lambda: reg)
    planned = create_planned_cover_uuid(
        title_hint="Band", repo=tmp_path, registry_file=reg
    )
    book = tmp_path / "Buch"
    book.mkdir()
    bind_cover_to_book(book, planned.production_uuid, registry_file=reg)
    listed = list_planned_cover_uuids(registry_file=reg)
    assert listed == []


def test_create_planned_requires_title(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Arbeitstitel"):
        create_planned_cover_uuid(title_hint="  ", repo=tmp_path)


def test_list_production_uuid_choices_includes_planned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.kdp_cover import cover_registry as reg_mod
    from tools.kdp_cover import uuid_choices as choices_mod

    reg = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(reg_mod, "registry_path", lambda: reg)
    monkeypatch.setattr(
        choices_mod,
        "collect_uuid_records",
        lambda **_kwargs: [],
    )

    planned = create_planned_cover_uuid(
        title_hint="Band_X",
        repo=tmp_path,
        registry_file=reg,
    )
    choices = list_production_uuid_choices(
        book_studio_repo=tmp_path,
        grammargraph_repo=None,
        registry_path=reg,
    )
    assert any(c.uuid == planned.production_uuid for c in choices)
    hit = next(c for c in choices if c.uuid == planned.production_uuid)
    assert ORIGIN_PLANNED in hit.origins
    assert "Geplantes Cover" in hit.origin_label
    assert "Band_X" in hit.title
