"""Tests: Cover aus Vorlage klonen (Texte + neue geplante UUID)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.kdp_cover.clone_cover import (
    CoverTextOverrides,
    apply_text_overrides,
    clone_cover_from_template,
    extract_text_snapshot,
)
from tools.kdp_cover.cover_registry import list_covers_for_uuid, load_registry
from tools.kdp_cover.model import CoverLayout, save_layout
from tools.kdp_cover.planned_uuid import SOURCE_KIND_PLANNED


def _minimal_layout(**kwargs: object) -> CoverLayout:
    data = {
        "page_count": 120,
        "paper_type_id": "white",
        "trim_width_mm": 135.0,
        "trim_height_mm": 215.0,
        "title": "Alt Titel",
        "author": "Alt Autor",
        "spine_text": "ALT",
        "spine_text_down": "",
        "production_uuid": "11111111-1111-4111-8111-111111111111",
        "front_compose": {
            "enabled": True,
            "titles": {
                "enabled": True,
                "series": {"text": "Serie Alt"},
                "main": {"text": "Haupt Alt"},
                "accent": {"text": "Claim Alt"},
                "author": {"text": "Autor Cover"},
                "subtitle": {
                    "enabled": True,
                    "line1": {"text": "Sub1"},
                    "line2": {"text": "Sub2"},
                },
            },
        },
    }
    data.update(kwargs)
    return CoverLayout.from_dict(data)


def test_apply_text_overrides_keeps_geometry() -> None:
    src = _minimal_layout()
    out = apply_text_overrides(
        src,
        CoverTextOverrides(
            title="Neu",
            author="Autorin",
            spine_text="NEU",
            compose_series="S",
            compose_main="M",
            compose_claim="C",
            compose_author="A",
            compose_sub1="1",
            compose_sub2="2",
        ),
    )
    assert out.page_count == 120
    assert out.trim_width_mm == pytest.approx(135.0)
    assert out.title == "Neu"
    assert out.author == "Autorin"
    assert out.spine_text == "NEU"
    titles = (out.front_compose or {})["titles"]
    assert titles["main"]["text"] == "M"
    assert titles["accent"]["text"] == "C"
    assert titles["subtitle"]["line1"]["text"] == "1"
    assert out.wrap_pdf == ""


def test_clone_cover_from_template_writes_new_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.kdp_cover import cover_registry as reg_mod

    reg = tmp_path / "cover_uuid_registry.json"
    monkeypatch.setattr(reg_mod, "registry_path", lambda: reg)

    src = tmp_path / "vorlage_kdp_cover.json"
    save_layout(_minimal_layout(), src)

    result = clone_cover_from_template(
        src,
        title_hint="IFJN_Neuer_Band",
        series_id="ABC",
        texts=CoverTextOverrides(
            title="IFJN Neuer Band",
            author="Autorin",
            compose_main="IFJN Neuer Band",
            compose_series="ABC",
            compose_claim="Neu",
        ),
        repo=tmp_path,
        registry_file=reg,
    )
    assert result.layout_path.is_file()
    assert result.planned.production_uuid != "11111111-1111-4111-8111-111111111111"
    assert result.layout.production_uuid == result.planned.production_uuid
    assert result.layout.title == "IFJN Neuer Band"
    assert (result.layout.front_compose or {})["titles"]["main"]["text"] == "IFJN Neuer Band"
    assert SOURCE_KIND_PLANNED in result.planned.entry.source_kinds
    covers = list_covers_for_uuid(result.planned.production_uuid, path=reg)
    assert len(covers) == 1
    assert "cloned_cover" in covers[0].source_kinds
    assert any(k.startswith("cloned_from:") for k in covers[0].source_kinds)
    data = load_registry(reg)
    assert data["entries"][0]["title_hint"] == "IFJN_Neuer_Band"


def test_extract_text_snapshot_roundtrip() -> None:
    snap = extract_text_snapshot(_minimal_layout())
    assert snap.compose_main == "Haupt Alt"
    assert snap.compose_claim == "Claim Alt"
    assert snap.compose_sub1 == "Sub1"
