"""Tests for Wrap-PDF ↔ Cover-Layout provenance (cover_link)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.kdp_cover.cover_link import (
    cover_link_path_for_pdf,
    enrich_validation_payload,
    read_cover_link,
    resolve_wrap_source,
    sibling_layout_path_for_wrap,
    uuid_from_covers_path,
    write_cover_link,
)
from tools.kdp_cover.model import CoverLayout
from tools.kdp_cover.export_pdf import export_wrap_pdf


def _minimal_layout(**kwargs) -> CoverLayout:
    data = dict(
        page_count=120,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        front_color="#112233",
        mode="safe",
    )
    data.update(kwargs)
    return CoverLayout(**data)


def test_sibling_and_uuid_from_path(tmp_path: Path):
    uid = "6fe531b5-bbda-46b3-9d6d-2137a0adcdb0"
    pdf = (
        tmp_path
        / "production"
        / "covers"
        / uid
        / "primary"
        / "Band_kdp_wrap.pdf"
    )
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    sibling = sibling_layout_path_for_wrap(pdf)
    assert sibling is not None
    assert sibling.name == "Band_kdp_cover.json"
    assert uuid_from_covers_path(pdf) == uid


def test_write_read_cover_link_and_resolve_sidecar(tmp_path: Path):
    pdf = tmp_path / "deploy" / "Band_kdp_wrap.pdf"
    layout = tmp_path / "canonical" / "Band_kdp_cover.json"
    layout.parent.mkdir(parents=True)
    layout.write_text('{"page_count": 100}\n', encoding="utf-8")
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    link_path = write_cover_link(
        pdf,
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
        layout_path=layout,
    )
    assert link_path == cover_link_path_for_pdf(pdf)
    link = read_cover_link(link_path)
    assert link is not None
    assert link.production_uuid == "6fe531b5-bbda-46b3-9d6d-2137a0adcdb0"
    assert Path(link.layout_path) == layout.resolve()
    resolved = resolve_wrap_source(pdf)
    assert resolved == layout.resolve()


def test_resolve_prefers_sibling_layout(tmp_path: Path):
    pdf = tmp_path / "Book_kdp_wrap.pdf"
    layout = tmp_path / "Book_kdp_cover.json"
    pdf.write_bytes(b"%PDF-1.4")
    layout.write_text(
        json.dumps(
            {
                "page_count": 120,
                "paper_type_id": "white_bw",
                "trim_width_mm": 135.0,
                "trim_height_mm": 215.0,
            }
        ),
        encoding="utf-8",
    )
    # Sidecar points elsewhere — sibling must win
    other = tmp_path / "other_kdp_cover.json"
    other.write_text("{}", encoding="utf-8")
    write_cover_link(
        pdf,
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
        layout_path=other,
    )
    assert resolve_wrap_source(pdf) == layout.resolve()


def test_resolve_missing_raises(tmp_path: Path):
    pdf = tmp_path / "orphan_kdp_wrap.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="Kein Cover-Layout"):
        resolve_wrap_source(pdf)


def test_enrich_validation_and_export_payload(tmp_path: Path):
    front = tmp_path / "front.png"
    from PIL import Image

    Image.new("RGB", (900, 1200), (10, 20, 30)).save(front)
    layout = _minimal_layout(
        front_image=str(front),
        front_image_mode="full",
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
    )
    out_pdf = tmp_path / "primary" / "Band_kdp_wrap.pdf"
    validation = tmp_path / "primary" / "Band_kdp_wrap_validation.json"
    layout_json = tmp_path / "primary" / "Band_kdp_cover.json"
    layout_json.parent.mkdir(parents=True)
    export_wrap_pdf(
        layout,
        out_pdf,
        dpi=72,
        resolve_base=tmp_path,
        validation_json=validation,
        require_safe=False,
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
        layout_path=layout_json,
    )
    assert out_pdf.is_file()
    payload = json.loads(validation.read_text(encoding="utf-8"))
    assert payload["production_uuid"] == "6fe531b5-bbda-46b3-9d6d-2137a0adcdb0"
    assert payload["layout_path"] == str(layout_json)


def test_enrich_validation_payload_helper():
    enriched = enrich_validation_payload(
        {"ok": True},
        production_uuid="6fe531b5-bbda-46b3-9d6d-2137a0adcdb0",
        layout_path=Path("C:/covers/a_kdp_cover.json"),
    )
    assert enriched["production_uuid"] == "6fe531b5-bbda-46b3-9d6d-2137a0adcdb0"
    assert "a_kdp_cover.json" in enriched["layout_path"]
