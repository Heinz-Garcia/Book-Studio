"""Tests: Cover ↔ Production-UUID registry."""

from __future__ import annotations

from pathlib import Path

from tools.kdp_cover.cover_registry import (
    list_covers_for_uuid,
    load_registry,
    resolve_primary_cover,
    upsert_cover_link,
)
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout


def test_upsert_primary_demotes_previous(tmp_path: Path) -> None:
    reg = tmp_path / "cover_uuid_registry.json"
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    a = tmp_path / "a_kdp_cover.json"
    b = tmp_path / "b_kdp_cover.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")

    upsert_cover_link(
        production_uuid=uid,
        cover_path=a,
        cover_label="A",
        cover_role="primary",
        path=reg,
    )
    upsert_cover_link(
        production_uuid=uid,
        cover_path=b,
        cover_label="B",
        cover_role="primary",
        path=reg,
    )
    covers = list_covers_for_uuid(uid, path=reg)
    assert len(covers) == 2
    primary = resolve_primary_cover(uid, path=reg)
    assert primary is not None
    assert Path(primary.cover_path).resolve() == b.resolve()
    assert primary.cover_role == "primary"
    other = [c for c in covers if Path(c.cover_path).resolve() == a.resolve()][0]
    assert other.cover_role == "alternative"


def test_cover_layout_roundtrip_uuid_fields(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    layout = CoverLayout(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        production_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        cover_label="Variante A",
        cover_role="alternative",
    )
    save_layout(layout, path)
    loaded = load_layout(path)
    assert loaded.production_uuid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert loaded.cover_label == "Variante A"
    assert loaded.cover_role == "alternative"


def test_load_registry_empty_missing_file(tmp_path: Path) -> None:
    data = load_registry(tmp_path / "missing.json")
    assert data["entries"] == []
    assert data["schema_version"] == 1


def test_resolve_primary_ohne_primary_gibt_none(tmp_path: Path) -> None:
    """P2.3: Nur Alternativen → None, kein stiller covers[0]-Fallback."""
    reg = tmp_path / "cover_uuid_registry.json"
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    alt = tmp_path / "alt_kdp_cover.json"
    alt.write_text("{}", encoding="utf-8")
    upsert_cover_link(
        production_uuid=uid,
        cover_path=alt,
        cover_label="Nur Alt",
        cover_role="alternative",
        path=reg,
    )
    covers = list_covers_for_uuid(uid, path=reg)
    assert len(covers) == 1
    assert covers[0].cover_role == "alternative"
    assert resolve_primary_cover(uid, path=reg) is None
